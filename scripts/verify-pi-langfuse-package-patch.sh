#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PATCH="$ROOT/patches/pi-packages/pi-langfuse-1.7.0.patch"
FORK="$ROOT/forks/pi-langfuse"
TSX="$FORK/node_modules/.bin/tsx"
BASE_HEAD="1c4dd956597af272d1869ce897e922d7702845fe"
FORK_HEAD="0ba150f5bd38c1e282feec5a488a918e6076063b"
PATCH_SHA256="d41b50c3bfd1477f6eaa5299597a0699f9bd028d4f66b8dde8b422f0a57b6909"
NPM_INTEGRITY="sha512-dXMv4NLySMzOfIBmaSNUsu83HQNh3N4qxjgD9l5hvmWARSJ75W2YnD1dfIoRi9QUb2LnJsmSVHqJV9ENDL5K8w=="

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

[ -x "$TSX" ] || fail "missing fork test runtime; run npm ci --ignore-scripts in forks/pi-langfuse"

read -r mode gitlink stage _ < <(git -C "$ROOT" ls-files --stage -- forks/pi-langfuse)
[ "$mode" = "160000" ] && [ "$stage" = "0" ] && [ "$gitlink" = "$FORK_HEAD" ] \
  || fail "forks/pi-langfuse gitlink does not match $FORK_HEAD"
[ "$(git -C "$FORK" rev-parse HEAD)" = "$FORK_HEAD" ] \
  || fail "forks/pi-langfuse checkout does not match $FORK_HEAD"
[ "$(git -C "$FORK" show -s --format=%P HEAD)" = "$BASE_HEAD" ] \
  || fail "maintained fork head is not directly based on npm source $BASE_HEAD"
git -C "$FORK" diff --quiet HEAD -- package.json src test \
  || fail "maintained fork production or contract tests are dirty"

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
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/packs" "$TMP/base" "$TMP/projected"
npm pack "pi-langfuse@1.7.0" --ignore-scripts --json --pack-destination "$TMP/packs" > "$TMP/pack.json"

TARBALL=$(python3 - "$TMP/pack.json" "$TMP/packs" "$NPM_INTEGRITY" <<'PY'
import base64
import hashlib
import json
import pathlib
import sys

metadata, packs, expected_integrity = sys.argv[1:]
entry = json.loads(pathlib.Path(metadata).read_text(encoding="utf-8"))[0]
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
python3 - "$TMP/base" "$TMP/projected" "$FORK" "$BASE_HEAD" <<'PYPROJECTION'
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
paths = ["package.json", "index.ts"] + sorted(str(p.relative_to(fork)) for p in (fork / "src").rglob("*") if p.is_file())
for name in paths:
    if (projected / name).read_bytes() != (fork / name).read_bytes():
        raise SystemExit(f"projected {name} differs from maintained fork")
if {p.relative_to(projected / "src") for p in (projected / "src").rglob("*") if p.is_file()} != {p.relative_to(fork / "src") for p in (fork / "src").rglob("*") if p.is_file()}:
    raise SystemExit("projected production file inventory differs from maintained fork")
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

cp -R "$FORK/test" "$TMP/projected/test"
cp "$ROOT/tests/fixtures/langfuse-managed-wrapper.test.ts" "$TMP/projected/test/managed-wrapper.test.ts"
# Run byte-identical wrapper under this ESM package scope, like Pi's TS loader.
cp "$ROOT/pi/agent/extensions/langfuse-config-env.ts" "$TMP/projected/managed-wrapper.ts"
cmp "$ROOT/pi/agent/extensions/langfuse-config-env.ts" "$TMP/projected/managed-wrapper.ts"
ln -s "$FORK/node_modules" "$TMP/projected/node_modules"
# Do not inherit live credentials or capture overrides into offline contracts.
python3 - "$TMP/projected" "$TMP/projected/managed-wrapper.ts" <<'PYTEST'
import os
import subprocess
import sys

env = {key: value for key, value in os.environ.items() if not key.startswith(("LANGFUSE_", "PI_LANGFUSE_"))}
env["PI_LANGFUSE_MANAGED_WRAPPER"] = sys.argv[2]
raise SystemExit(subprocess.run([
    "node_modules/.bin/tsx", "--test",
    "test/quality.test.ts", "test/tool.test.ts", "test/generation.test.ts",
    "test/redaction.test.ts", "test/cache-contract.test.ts", "test/langfuse.test.ts",
    "test/capture-policy.test.ts", "test/config.test.ts", "test/pi-1-events.test.ts",
    "test/system-state.test.ts", "test/managed-wrapper.test.ts",
], cwd=sys.argv[1], env=env).returncode)
PYTEST

echo "PASS: pi-langfuse npm base, fork projection, reversibility, privacy, ingestion, cache, quality and managed wrapper verified"
