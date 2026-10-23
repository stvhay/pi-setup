#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PATCH="$ROOT/patches/pi-packages/pi-langfuse-1.7.0.patch"
FORK="$ROOT/forks/pi-langfuse"
TSX="$FORK/node_modules/.bin/tsx"
BASE_HEAD="1c4dd956597af272d1869ce897e922d7702845fe"
LEGACY_HEAD="0ba150f5bd38c1e282feec5a488a918e6076063b"
BUNDLE="$ROOT/patches/pi-packages/langfuse-runtime"
NPM_CLI=${PI_LANGFUSE_NPM_CLI:-}
PATCH_SHA256="d41b50c3bfd1477f6eaa5299597a0699f9bd028d4f66b8dde8b422f0a57b6909"
NPM_INTEGRITY="sha512-dXMv4NLySMzOfIBmaSNUsu83HQNh3N4qxjgD9l5hvmWARSJ75W2YnD1dfIoRi9QUb2LnJsmSVHqJV9ENDL5K8w=="

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

[ -x "$TSX" ] || fail "missing fork test runtime; run npm ci --ignore-scripts in forks/pi-langfuse"

read -r mode gitlink stage _ < <(git -C "$ROOT" ls-files --stage -- forks/pi-langfuse)
[ "$mode" = "160000" ] && [ "$stage" = "0" ] || fail "missing maintained fork gitlink"
[ "$(git -C "$FORK" rev-parse HEAD)" = "$gitlink" ] || fail "fork checkout differs from pinned gitlink"
git -C "$FORK" merge-base --is-ancestor "$LEGACY_HEAD" HEAD || fail "published history was not preserved"
[ "$(git -C "$FORK" show -s --format=%P "$LEGACY_HEAD")" = "$BASE_HEAD" ] || fail "historical npm ancestry changed"
[ -z "$(git -C "$FORK" status --porcelain)" ] || fail "maintained fork has uncommitted source"
[ -n "$NPM_CLI" ] || NPM_CLI=$(python3 -c 'import pathlib,shutil; print(pathlib.Path(shutil.which("npm")).resolve())')
[ "$(node "$NPM_CLI" --version)" = 12.2.1 ] || fail "set PI_LANGFUSE_NPM_CLI to npm 12.2.1 npm-cli.js"

python3 - "$PATCH" "$PATCH_SHA256" <<'PY'
import hashlib
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
expected = sys.argv[2]
actual = hashlib.sha256(path.read_bytes()).hexdigest()
if actual != expected:
    raise SystemExit(f"patch integrity mismatch: expected {expected}, found {actual}")
PY

TMP=$(mktemp -d "${TMPDIR:-/tmp}/pi-langfuse-package-proof.XXXXXX")
TMP=$(cd "$TMP" && pwd -P)
HARNESS=
trap 'rm -rf "$TMP"; [ -z "$HARNESS" ] || rm -rf "$HARNESS"' EXIT
mkdir -p "$TMP/packs" "$TMP/base" "$TMP/projected"
npm pack "pi-langfuse@1.7.0" --ignore-scripts --json --pack-destination "$TMP/packs" > "$TMP/pack.json"

TARBALL=$(python3 - "$TMP/pack.json" "$TMP/packs" "$NPM_INTEGRITY" <<'PY'
import base64
import hashlib
import json
import pathlib
import sys

metadata, packs, expected_integrity = sys.argv[1:]
metadata = json.loads(pathlib.Path(metadata).read_text(encoding="utf-8"))
entry = metadata[0] if isinstance(metadata, list) else metadata
if (entry.get("name"), entry.get("version"), entry.get("integrity")) != (
    "pi-langfuse",
    "1.7.0",
    expected_integrity,
):
    raise SystemExit(f"unexpected npm metadata: {entry}")
tarball = pathlib.Path(packs, entry["filename"])
actual = "sha512-" + base64.b64encode(hashlib.sha512(tarball.read_bytes()).digest()).decode()
if actual != expected_integrity:
    raise SystemExit(f"tarball integrity mismatch: expected {expected_integrity}, found {actual}")
print(tarball)
PY
)

tar -xzf "$TARBALL" -C "$TMP/base" --strip-components=1
tar -xzf "$TARBALL" -C "$TMP/projected" --strip-components=1

forward_output=$(patch --force --fuzz=0 --forward -p1 -d "$TMP/projected" < "$PATCH" 2>&1)
if grep -Eiq 'offset|fuzz' <<<"$forward_output"; then
  fail "forward apply used offset or fuzz"
fi
if patch --force --fuzz=0 --forward --dry-run -p1 -d "$TMP/projected" < "$PATCH" >/dev/null 2>&1; then
  fail "patch reapplied to projected package"
fi

# Compare every production file, including upstream files outside the patch.
python3 - "$TMP/base" "$TMP/projected" "$FORK" "$BASE_HEAD" "$LEGACY_HEAD" <<'PYPROJECTION'
import pathlib
import subprocess
import sys

base, projected, fork = map(pathlib.Path, sys.argv[1:4])
base_head = sys.argv[4]
paths = ["package.json", "index.ts"] + sorted(str(p.relative_to(base)) for p in (base / "src").rglob("*") if p.is_file())
for name in paths:
    expected = subprocess.check_output(["git", "-C", str(fork), "show", f"{base_head}:{name}"])
    if (base / name).read_bytes() != expected:
        raise SystemExit(f"npm base {name} differs from pinned upstream source")
# This patch is historical provenance, not the current delivery mechanism.
legacy_head = sys.argv[5]
paths = ["package.json", "index.ts"] + subprocess.check_output(
    ["git", "-C", str(fork), "ls-tree", "-r", "--name-only", legacy_head, "--", "src"], text=True).splitlines()
for name in paths:
    expected = subprocess.check_output(["git", "-C", str(fork), "show", f"{legacy_head}:{name}"])
    if (projected / name).read_bytes() != expected:
        raise SystemExit(f"historical projection differs: {name}")
if {str(p.relative_to(projected)) for p in (projected / "src").rglob("*") if p.is_file()} != {p for p in paths if p.startswith("src/")}:
    raise SystemExit("historical projection file inventory differs")
PYPROJECTION

# Include the OS implementation even when Nix/Homebrew supplies PATH patch.
PATCH_ENGINES=("$(command -v patch)")
if [ -x /usr/bin/patch ] && ! [ /usr/bin/patch -ef "${PATCH_ENGINES[0]}" ]; then
  PATCH_ENGINES+=(/usr/bin/patch)
fi

cp -R "$TMP/projected" "$TMP/expected-projection"
for patch_bin in "${PATCH_ENGINES[@]}"; do
  reverse_output=$(LC_ALL=C "$patch_bin" --verbose --force --fuzz=0 --reverse --dry-run -p1 -d "$TMP/projected" < "$PATCH" 2>&1)
  if grep -Eiq 'offset|fuzz' <<<"$reverse_output"; then
    fail "$patch_bin reverse apply used offset or fuzz"
  fi
  "$patch_bin" --batch --silent --fuzz=0 --reverse -p1 -d "$TMP/projected" < "$PATCH"
  diff -qr "$TMP/base" "$TMP/projected" || fail "$patch_bin reverse did not restore exact npm base"
  forward_output=$(LC_ALL=C "$patch_bin" --verbose --force --fuzz=0 --forward -p1 -d "$TMP/projected" < "$PATCH" 2>&1)
  if grep -Eiq 'offset|fuzz' <<<"$forward_output"; then
    fail "$patch_bin reapply used offset or fuzz"
  fi
  diff -qr "$TMP/expected-projection" "$TMP/projected" || fail "$patch_bin reapply changed projection"
  echo "Verified exact Langfuse round trip: $patch_bin"
done

# Current delivery must match a fresh deterministic build and real installed
# dependencies. The test harness uses the fork's dev SDK, not borrowed runtime deps.
(cd "$FORK" && node "$NPM_CLI" run typecheck && node test/run.mjs)
PI_LANGFUSE_NPM_CLI="$NPM_CLI" node --test "$FORK/vendor/langfuse-otel/test/installed.test.mjs"
PI_LANGFUSE_NPM_CLI="$NPM_CLI" node --test "$FORK/vendor/runtime-release/test/build.test.mjs"
node "$FORK/vendor/runtime-release/build.mjs" --output "$TMP/rebuilt" --npm-cli "$NPM_CLI"
diff -qr "$BUNDLE" "$TMP/rebuilt" || fail "tracked runtime projection is stale"
DEST="$TMP/destination"
python3 "$ROOT/scripts/install-pi-langfuse-runtime.py" --bundle "$BUNDLE" --dest "$DEST" --npm-cli "$NPM_CLI"
python3 "$ROOT/scripts/install-pi-langfuse-runtime.py" --bundle "$BUNDLE" --dest "$DEST" --npm-cli "$NPM_CLI"
python3 "$ROOT/scripts/install-pi-langfuse-runtime.py" --bundle "$BUNDLE" --dest "$DEST" --check
RELEASE_ID=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["id"])' "$BUNDLE/release.json")
RELEASE="$DEST/runtime/pi-langfuse/releases/$RELEASE_ID"
(cd "$RELEASE" && node "$NPM_CLI" audit --omit=dev --json) > "$TMP/production-audit.json"
python3 - "$TMP/production-audit.json" <<'PYAUDIT'
import json, sys
assert json.load(open(sys.argv[1]))["metadata"]["vulnerabilities"]["total"] == 0
PYAUDIT

HARNESS=$(mktemp -d "$FORK/node_modules/.langfuse-proof.XXXXXX")
mkdir -p "$HARNESS/lib" "$TMP/home"
printf '{"type":"module"}\n' > "$HARNESS/package.json"
cp "$ROOT/tests/fixtures/langfuse-managed-wrapper.test.ts" "$HARNESS/managed-wrapper.test.ts"
cp "$ROOT/pi/agent/extensions/langfuse-config-env.ts" "$HARNESS/managed-wrapper.ts"
cp "$ROOT/pi/agent/extensions/lib/langfuse-runtime.ts" "$HARNESS/lib/langfuse-runtime.ts"
python3 - "$TSX" "$HARNESS" "$RELEASE" "$TMP/home" <<'PYTEST'
import os
import pathlib
import subprocess
import sys

tsx, harness, release, home = sys.argv[1:]
env = {key: os.environ[key] for key in ("PATH", "TMPDIR", "LANG", "SystemRoot") if key in os.environ}
env.update(HOME=home, PI_LANGFUSE_MANAGED_WRAPPER=str(pathlib.Path(harness, "managed-wrapper.ts")),
           PI_LANGFUSE_RUNTIME_RELEASE=release)
raise SystemExit(subprocess.run([tsx, "--test", str(pathlib.Path(harness, "managed-wrapper.test.ts"))], env=env).returncode)
PYTEST
python3 "$ROOT/scripts/install-pi-langfuse-runtime.py" --bundle "$BUNDLE" --dest "$DEST" --check
echo "PASS: historical npm provenance, deterministic isolated projection, fresh/reused installed tree, zero production audit and real Pi wrapper/quality loading verified"
