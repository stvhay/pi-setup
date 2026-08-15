#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
JITI="$ROOT/node_modules/@earendil-works/pi-coding-agent/node_modules/.bin/jiti"
[ -x "$JITI" ] || {
  echo "Missing Pi Jiti runtime; run npm ci --ignore-scripts" >&2
  exit 1
}

TMP=$(mktemp -d "${TMPDIR:-/tmp}/pi-archimedes-package-proof.XXXXXX")
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/packs" "$TMP/node_modules/@pi-archimedes"

pack_exact() {
  local spec=$1 expected_name=$2 expected_version=$3 expected_integrity=$4 metadata
  metadata="$TMP/$(printf '%s' "$expected_name" | tr '/@' '__').json"
  npm pack "$spec" --json --pack-destination "$TMP/packs" > "$metadata"
  python3 - "$metadata" "$TMP/packs" "$expected_name" "$expected_version" "$expected_integrity" <<'PY'
import base64
import hashlib
import json
import pathlib
import sys

metadata, packs, expected_name, expected_version, expected_integrity = sys.argv[1:]
entry = json.loads(pathlib.Path(metadata).read_text(encoding="utf-8"))[0]
if (entry.get("name"), entry.get("version"), entry.get("integrity")) != (
    expected_name,
    expected_version,
    expected_integrity,
):
    raise SystemExit(f"unexpected npm metadata: {entry}")
tarball = pathlib.Path(packs, entry["filename"])
actual = "sha512-" + base64.b64encode(hashlib.sha512(tarball.read_bytes()).digest()).decode()
if actual != expected_integrity:
    raise SystemExit(f"integrity mismatch for {tarball}: {actual}")
print(tarball)
PY
}

META_TGZ=$(pack_exact \
  "pi-archimedes@2.1.0" "pi-archimedes" "2.1.0" \
  "sha512-TitGWAXRE6W+3bXwg7pIhnoKR7w3PzXW417RGpGyUwHgFIqHi20eRDAs0TipBoDO/HAsQVcdpXjB//W9D/1zRQ==")
ASK_TGZ=$(pack_exact \
  "@pi-archimedes/ask@2.1.0" "@pi-archimedes/ask" "2.1.0" \
  "sha512-QMA0zdARYOQHVEZrZf5/310L3qWFLoBiKtQtFcgRXLfO5HAoYcye/gTfQLdjOth71DyPHJ5Bvhza/BVMjdjduA==")
CORE_TGZ=$(pack_exact \
  "@pi-archimedes/core@2.1.0" "@pi-archimedes/core" "2.1.0" \
  "sha512-TiZBNrhyk8trUw3J66J78HNUEVsgIWkzvDJUqGq2hxvwCDS32FcJWn0K2wX+0Og8lWawmsot2n7lsYUn0ysocw==")
FOOTER_TGZ=$(pack_exact \
  "@pi-archimedes/footer@2.1.0" "@pi-archimedes/footer" "2.1.0" \
  "sha512-Xs+5DCkRUmXabagwsR+J6UxhxK70VuEJcwq9wR72TRml0ZhZ3Ouc7cnjhxBZErAZx4Sgk8HY3QhPzKiSFZ24Og==")
SUBAGENT_TGZ=$(pack_exact \
  "@pi-archimedes/subagent@2.1.0" "@pi-archimedes/subagent" "2.1.0" \
  "sha512-Num0675GR2hWcp21r4epe7mqQDIgpMomUv55C9G1a96zv1mL9Gkv5eaSPe9iudI43j1lhdPEtcK3ObJs7tK9VA==")
LANGFUSE_TGZ=$(pack_exact \
  "pi-langfuse@1.5.14" "pi-langfuse" "1.5.14" \
  "sha512-zzQ40IMj7NrGrluzGAqB6zJ645MaqHfAMTdlsOK/fPlQywlTlgPb8Y/PyQc8asSkqWT55KMMDV+qNSKAG1zyTg==")

extract() {
  local tarball=$1 destination=$2
  mkdir -p "$destination"
  tar -xzf "$tarball" -C "$destination" --strip-components=1
}

extract "$META_TGZ" "$TMP/node_modules/pi-archimedes"
extract "$ASK_TGZ" "$TMP/node_modules/@pi-archimedes/ask"
extract "$CORE_TGZ" "$TMP/node_modules/@pi-archimedes/core"
extract "$FOOTER_TGZ" "$TMP/node_modules/@pi-archimedes/footer"
extract "$SUBAGENT_TGZ" "$TMP/node_modules/@pi-archimedes/subagent"
extract "$LANGFUSE_TGZ" "$TMP/node_modules/pi-langfuse"

PI_PACKAGE_ROOT="$TMP/node_modules" "$ROOT/scripts/apply-pi-package-patches.sh" --check
PI_PACKAGE_ROOT="$TMP/node_modules" "$ROOT/scripts/apply-pi-package-patches.sh"
PI_PACKAGE_ROOT="$TMP/node_modules" "$ROOT/scripts/apply-pi-package-patches.sh" --check
PI_PACKAGE_ROOT="$TMP/node_modules" "$ROOT/scripts/apply-pi-package-patches.sh"

for package in meta ask core footer subagent; do
  case "$package" in
    meta) package_dir="$TMP/node_modules/pi-archimedes" ;;
    *) package_dir="$TMP/node_modules/@pi-archimedes/$package" ;;
  esac
  reverse_output=$(patch --force --fuzz=0 --reverse --dry-run -p1 -d "$package_dir" \
    < "$ROOT/patches/pi-packages/pi-archimedes-$package-2.1.0.patch" 2>&1)
  if grep -Eiq 'offset|fuzz' <<<"$reverse_output"; then
    echo "$package reverse dry-run used offset or fuzz" >&2
    exit 1
  fi
done

ln -s "$ROOT/node_modules/@earendil-works" "$TMP/node_modules/@earendil-works"
ln -s "$ROOT/node_modules/typebox" "$TMP/node_modules/typebox"
cat > "$TMP/public-imports.ts" <<'TS'
import { mkdir, mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { resolveAgentModel } from "@pi-archimedes/subagent/agents";
import { SUBAGENT_OUTPUT_CONTRACTS } from "@pi-archimedes/subagent/types";
import { Events, getBus } from "@pi-archimedes/core/bus";

const agentDir = await mkdtemp(join(tmpdir(), "archimedes-public-ports-"));
process.env.PI_CODING_AGENT_DIR = agentDir;
await mkdir(join(agentDir, "agents"));
await writeFile(
  join(agentDir, "agents", "reviewer.md"),
  "---\nname: reviewer\ndescription: Review changes\nmodel: openai/frontmatter\n---\nReview.\n",
);
await writeFile(
  join(agentDir, "agents.local.json"),
  JSON.stringify({ reviewer: { model: "openai/local" } }),
);
if (resolveAgentModel("reviewer", process.cwd()) !== "openai/local") {
  throw new Error("public agent model resolution failed");
}
if (!SUBAGENT_OUTPUT_CONTRACTS.includes("artifact")) {
  throw new Error("public result types export failed");
}
const off = getBus().on(Events.COST_UPDATE, () => {});
off();
console.log("PASS: patched Archimedes npm packages and public imports verified");
TS

(cd "$TMP" && "$JITI" public-imports.ts)
