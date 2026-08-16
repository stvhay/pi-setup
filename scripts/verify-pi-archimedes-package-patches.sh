#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
FORK="$ROOT/forks/pi-archimedes"
VITEST="$FORK/node_modules/.bin/vitest"
TSC="$FORK/node_modules/.bin/tsc"
BASE_HEAD="2ed26aa1d3301cc01a927d9409778bbd13df4798"
LIMITS_HEAD="23d8fbf7381f2081806165e26d6b0962aef13ef9"
ONE_SHOT_HEAD="f277470d64d014b496efe7e4ae4d57275d8e1907"
REPEATED_ERRORS_HEAD="3576ddfd154fb274813a16e07607a15520ce73b7"
RESULT_PORTS_HEAD="a9efbf159ee8b2717aae1df8742bd7382e97c1a3"
FORK_HEAD="1c4750ddb844cd8579f3076922603915098e9f96"
FORK_BRANCH="vendor/pi-setup-210"
FORK_URL="https://github.com/stvhay/pi-archimedes.git"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

[ -x "$VITEST" ] || fail "missing fork test runtime; run corepack pnpm install --frozen-lockfile in forks/pi-archimedes"
[ -x "$TSC" ] || fail "missing fork TypeScript runtime; run corepack pnpm install --frozen-lockfile in forks/pi-archimedes"

read -r mode gitlink stage _ < <(git -C "$ROOT" ls-files --stage -- forks/pi-archimedes)
[ "$mode" = "160000" ] && [ "$stage" = "0" ] && [ "$gitlink" = "$FORK_HEAD" ] \
  || fail "forks/pi-archimedes gitlink does not match $FORK_HEAD"
[ "$(git -C "$FORK" rev-parse HEAD)" = "$FORK_HEAD" ] \
  || fail "forks/pi-archimedes checkout does not match $FORK_HEAD"
[ "$(git -C "$FORK" rev-parse 'v2.1.0^{}')" = "$BASE_HEAD" ] \
  || fail "v2.1.0 does not match npm base $BASE_HEAD"
[ "$(git config --file "$ROOT/.gitmodules" --get submodule.forks/pi-archimedes.url)" = "$FORK_URL" ] \
  || fail "unexpected pi-archimedes submodule URL"
[ "$(git config --file "$ROOT/.gitmodules" --get submodule.forks/pi-archimedes.branch)" = "$FORK_BRANCH" ] \
  || fail "unexpected pi-archimedes submodule branch"

verify_parent() {
  local head=$1 parent=$2
  [ "$(git -C "$FORK" show -s --format=%P "$head")" = "$parent" ] \
    || fail "$head is not exactly one commit on $parent"
}
verify_parent "$LIMITS_HEAD" "$BASE_HEAD"
verify_parent "$ONE_SHOT_HEAD" "$LIMITS_HEAD"
verify_parent "$REPEATED_ERRORS_HEAD" "$ONE_SHOT_HEAD"
verify_parent "$RESULT_PORTS_HEAD" "$REPEATED_ERRORS_HEAD"
verify_parent "$FORK_HEAD" "$RESULT_PORTS_HEAD"

remote_head=$(git ls-remote --heads "$FORK_URL" "refs/heads/$FORK_BRANCH" | awk 'NR == 1 {print $1}')
[ "$remote_head" = "$FORK_HEAD" ] \
  || fail "$FORK_BRANCH resolves to ${remote_head:-<missing>}, expected $FORK_HEAD"

python3 - "$ROOT/patches/pi-packages" <<'PY'
import hashlib
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
expected = {
    "pi-archimedes-meta-2.1.0.patch": "571e73ac589c03a256e802286b64f27c1869831fa1ca05f7f87c8b3369fb4a28",
    "pi-archimedes-ask-2.1.0.patch": "eaa4c814f481ef95c1a95866170ec59d9553a257ed96634a37422f065fa062cc",
    "pi-archimedes-core-2.1.0.patch": "520ff1888ffe785f6648a2de5823023a6c146017ba21d8c7c6c1f12d2b81d73f",
    "pi-archimedes-footer-2.1.0.patch": "0e680ca78ed7422abf0241d8dfba982497b93b14064ef375aa4a3f7c0e437e34",
    "pi-archimedes-subagent-2.1.0.patch": "41de1eadb6f329f5c884421d80620df4135c28e34c070b1fc1cb9aba871a5ff0",
}
for name, digest in expected.items():
    actual = hashlib.sha256((root / name).read_bytes()).hexdigest()
    if actual != digest:
        raise SystemExit(f"patch integrity mismatch for {name}: expected {digest}, found {actual}")
PY

TMP=$(mktemp -d "${TMPDIR:-/tmp}/pi-archimedes-package-proof.XXXXXX")
trap 'rm -rf "$TMP"' EXIT
BASE="$TMP/base/node_modules"
PROJECTED="$TMP/projected/node_modules"
mkdir -p "$TMP/packs" "$BASE/@pi-archimedes" "$PROJECTED/@pi-archimedes"

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

for root in "$BASE" "$PROJECTED"; do
  extract "$META_TGZ" "$root/pi-archimedes"
  extract "$ASK_TGZ" "$root/@pi-archimedes/ask"
  extract "$CORE_TGZ" "$root/@pi-archimedes/core"
  extract "$FOOTER_TGZ" "$root/@pi-archimedes/footer"
  extract "$SUBAGENT_TGZ" "$root/@pi-archimedes/subagent"
done
extract "$LANGFUSE_TGZ" "$PROJECTED/pi-langfuse"

compare_manifest() {
  python3 - "$1" "$2" <<'PY'
import json
import pathlib
import sys

published_path, source_path = map(pathlib.Path, sys.argv[1:])
published = json.loads(published_path.read_text(encoding="utf-8"))
source = json.loads(source_path.read_text(encoding="utf-8"))
for section in ("dependencies", "devDependencies", "peerDependencies"):
    for name, value in source.get(section, {}).items():
        if isinstance(value, str) and value.startswith("workspace:"):
            actual = published.get(section, {}).get(name)
            if actual != "2.1.0":
                raise SystemExit(f"unexpected published dependency {name}: {actual}")
            source[section][name] = actual
if published != source:
    raise SystemExit(f"published manifest differs from source: {published_path}")
PY
}

verify_base_source() {
  local package=$1 base_dir source_root path source_path source_file
  case "$package" in
    meta) base_dir="$BASE/pi-archimedes"; source_root=meta ;;
    *) base_dir="$BASE/@pi-archimedes/$package"; source_root="packages/$package" ;;
  esac
  while IFS= read -r path; do
    path=${path#"$base_dir/"}
    source_path="$source_root/$path"
    [ "$path" = LICENSE ] && source_path=LICENSE
    source_file="$TMP/source-$package-${path//\//_}"
    git -C "$FORK" show "$BASE_HEAD:$source_path" > "$source_file" \
      || fail "$package npm base file has no v2.1.0 source: $path"
    if [ "$path" = package.json ]; then
      compare_manifest "$base_dir/$path" "$source_file"
    else
      cmp "$base_dir/$path" "$source_file" \
        || fail "$package npm base differs from v2.1.0 source at $path"
    fi
  done < <(find "$base_dir" -type f | sort)
}

for package in meta ask core footer subagent; do
  verify_base_source "$package"
done

PI_PACKAGE_ROOT="$PROJECTED" "$ROOT/scripts/apply-pi-package-patches.sh" --check
PI_PACKAGE_ROOT="$PROJECTED" "$ROOT/scripts/apply-pi-package-patches.sh"
PI_PACKAGE_ROOT="$PROJECTED" "$ROOT/scripts/apply-pi-package-patches.sh" --check
PI_PACKAGE_ROOT="$PROJECTED" "$ROOT/scripts/apply-pi-package-patches.sh"

production_paths() {
  local package_dir=$1
  printf '%s\n' package.json
  (cd "$package_dir" && find src -type f -name '*.ts' ! -name '*.test.ts' -print)
}

compare_projection_path() {
  local package_dir=$1 fork_dir=$2 path=$3 label=$4
  [ -f "$package_dir/$path" ] && [ -f "$fork_dir/$path" ] \
    || fail "$label production file set differs from maintained fork at $path"
  if [ "$path" = package.json ]; then
    compare_manifest "$package_dir/$path" "$fork_dir/$path"
  else
    cmp "$package_dir/$path" "$fork_dir/$path" \
      || fail "$label projection differs from maintained fork at $path"
  fi
}

verify_projection() {
  local package=$1 package_dir base_dir fork_dir patch_file reverse_output forward_output path
  case "$package" in
    meta)
      package_dir="$PROJECTED/pi-archimedes"
      base_dir="$BASE/pi-archimedes"
      fork_dir="$FORK/meta"
      ;;
    *)
      package_dir="$PROJECTED/@pi-archimedes/$package"
      base_dir="$BASE/@pi-archimedes/$package"
      fork_dir="$FORK/packages/$package"
      ;;
  esac
  patch_file="$ROOT/patches/pi-packages/pi-archimedes-$package-2.1.0.patch"

  while IFS= read -r path; do
    compare_projection_path "$package_dir" "$fork_dir" "$path" "$package"
  done < <({ production_paths "$package_dir"; production_paths "$fork_dir"; } | sort -u)

  reverse_output=$(patch --force --fuzz=0 --reverse --dry-run -p1 -d "$package_dir" < "$patch_file" 2>&1)
  if grep -Eiq 'offset|fuzz' <<<"$reverse_output"; then
    fail "$package reverse dry-run used offset or fuzz"
  fi
  patch --batch --silent --fuzz=0 --reverse -p1 -d "$package_dir" < "$patch_file"
  diff -qr "$base_dir" "$package_dir" \
    || fail "$package reverse did not restore the exact npm base"

  forward_output=$(patch --force --fuzz=0 --forward -p1 -d "$package_dir" < "$patch_file" 2>&1)
  if grep -Eiq 'offset|fuzz' <<<"$forward_output"; then
    fail "$package reapply used offset or fuzz"
  fi
  while IFS= read -r path; do
    compare_projection_path "$package_dir" "$fork_dir" "$path" "$package reapplied"
  done < <({ production_paths "$package_dir"; production_paths "$fork_dir"; } | sort -u)
}

for package in meta ask core footer subagent; do
  verify_projection "$package"
done

if rg -n -i '\b(beads?|closeout|ticket_approval|quality[-_ ]policy|billing[-_ ]class|acceptance decision)\b' \
  "$PROJECTED/@pi-archimedes/subagent/src" "$PROJECTED/@pi-archimedes/core/src/bus.ts"; then
  fail "Archimedes public ports contain pi-setup governance behavior"
fi

for test in public-ports execute index-execute stream limits agents; do
  cp "$FORK/packages/subagent/src/$test.test.ts" \
    "$PROJECTED/@pi-archimedes/subagent/src/$test.test.ts"
done
cp "$FORK/packages/core/src/bus.test.ts" "$PROJECTED/@pi-archimedes/core/src/bus.test.ts"

ln -s "$FORK/packages/subagent/node_modules/@earendil-works" "$PROJECTED/@earendil-works"
ln -s "$FORK/packages/subagent/node_modules/typebox" "$PROJECTED/typebox"
ln -s "$FORK/node_modules/vitest" "$PROJECTED/vitest"
ln -s "$FORK/packages/subagent/node_modules/@types" "$PROJECTED/@types"

cat > "$TMP/projected/package.json" <<'JSON'
{"private":true,"type":"module"}
JSON
cat > "$TMP/projected/public-types.ts" <<'TS'
import { resolveAgentModel } from "@pi-archimedes/subagent/agents";
import {
  SUBAGENT_OUTPUT_CONTRACTS,
  type OutputLimitEvidence,
  type ResolvedChildExecution,
  type SubagentChildTraceRef,
  type SubagentDetails,
  type SubagentExecutionMode,
  type SubagentExecutionProfile,
  type SubagentLimits,
  type SubagentOutputContract,
  type SubagentProgressSummary,
  type SubagentResult,
  type SubagentTermination,
  type SubagentTerminationReason,
  type SubagentToolResult,
  type SubagentUsage,
  type SubagentUsageState,
} from "@pi-archimedes/subagent/types";
import {
  Events,
  getBus,
  type ArchimedesBus,
  type ArchimedesEventPayloadMap,
  type AskRequestPayload,
  type AskResponsePayload,
  type CostUpdatePayload,
  type TodoClearPayload,
  type TodoUpdatePayload,
} from "@pi-archimedes/core/bus";

const resolveModel: (name: string, cwd: string) => string | undefined = resolveAgentModel;
const mode: SubagentExecutionMode = "one-shot";
const outputContract: SubagentOutputContract = "artifact";
const reason: SubagentTerminationReason = "output-limit";
const usageState: SubagentUsageState = "partial";
const limits: SubagentLimits = {
  maxProviderRequests: 1,
  maxToolCalls: 2,
  maxTotalTokens: 3,
  maxOutputTokens: 4,
  maxCostUsd: 0.5,
  maxDurationMs: 6,
};
const profile: SubagentExecutionProfile = { mode, thinking: "high" };
const outputLimit: OutputLimitEvidence = {
  requested: 4,
  effective: 4,
  enforcement: "applied",
};
const execution: ResolvedChildExecution = { profile, limits, outputLimit };
const termination: SubagentTermination = { reason, limit: 4, observed: 4, usageState };
const usage: SubagentUsage = {
  input: 1,
  output: 2,
  cacheRead: 3,
  cacheWrite: 4,
  cost: 0.5,
  turns: 1,
};
const childTrace: SubagentChildTraceRef = { sessionId: "session", traceId: "trace" };
const progressSummary: SubagentProgressSummary = { toolCount: 1, tokens: 10, durationMs: 20 };
const result: SubagentResult = {
  agent: "reviewer",
  task: "Review",
  childSessionId: "session",
  childTrace,
  exitCode: 2,
  usage,
  provider: "provider",
  model: "model",
  execution,
  outputContract,
  finalOutput: "partial",
  error: "limited",
  termination,
  progress: undefined,
  progressSummary,
};
const details: SubagentDetails = { mode: "parallel", results: [result], progress: [] };
const toolResult: SubagentToolResult = {
  content: [{ type: "text", text: "partial" }],
  details,
  isError: true,
};
const cost: CostUpdatePayload = {
  source: "subagent:reviewer",
  inputTokens: 1,
  outputTokens: 2,
  cacheReadTokens: 3,
  cacheWriteTokens: 4,
  cost: 0.5,
};
const todos: TodoUpdatePayload = {
  source: "subagent:reviewer",
  todos: [{ id: 1, title: "Review", description: "Review", status: "in-progress" }],
};
const todoClear: TodoClearPayload = { source: "subagent:reviewer" };
const ask: AskRequestPayload = {
  source: "subagent:reviewer",
  requestId: "request",
  questions: [{
    id: "question",
    question: "Continue?",
    description: "Choose",
    options: [{ label: "Yes" }],
    multi: false,
    recommended: 0,
  }],
};
const answer: AskResponsePayload = {
  requestId: "request",
  cancelled: false,
  results: [{ id: "question", selectedOptions: ["Yes"], customInput: "note" }],
};
const payloads: ArchimedesEventPayloadMap = {
  "archimedes:cost_update": cost,
  "archimedes:todos_update": todos,
  "archimedes:todos_clear": todoClear,
  "archimedes:ask_request": ask,
  "archimedes:ask_response": answer,
};
const bus: ArchimedesBus = getBus();
bus.emit(Events.COST_UPDATE, payloads["archimedes:cost_update"]);
const off = bus.on(Events.ASK_RESPONSE, (_payload: AskResponsePayload) => {});
void [resolveModel, SUBAGENT_OUTPUT_CONTRACTS, toolResult, off];
TS

(
  cd "$TMP/projected"
  "$TSC" --noEmit --strict --skipLibCheck --target ES2022 \
    --module NodeNext --moduleResolution NodeNext --types node public-types.ts
)
(
  cd "$PROJECTED/@pi-archimedes/subagent"
  "$VITEST" run --silent=true \
    src/public-ports.test.ts src/execute.test.ts src/index-execute.test.ts \
    src/stream.test.ts src/limits.test.ts src/agents.test.ts
)
(
  cd "$PROJECTED/@pi-archimedes/core"
  "$VITEST" run --silent=true src/bus.test.ts
)

echo "PASS: Archimedes npm bases, fork projections, reversibility, public declarations, and 100 installed-package tests verified"
