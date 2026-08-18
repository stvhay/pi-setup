#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PATCH="$ROOT/patches/pi-packages/pi-langfuse-1.5.14.patch"
FORK="$ROOT/forks/pi-langfuse"
TSX="$FORK/node_modules/.bin/tsx"
BASE_HEAD="04d55a12556bdf4c4b8b208038198dc2fd8e571b"
FORK_QUALITY="94fa7f0c4410ce10da1f98c8fe4b798374c8df2e"
FORK_PREVIOUS="1d705405901c704196154698fade3e9a6a5b5f93"
FORK_HEAD="e5596e8df6136b07db143025ef400d325454b958"
PATCH_SHA256="0fa6010e0bbc010d7f9c27e15b88203ea1ce55a4b41259723afc76a5f65186ec"
NPM_INTEGRITY="sha512-zzQ40IMj7NrGrluzGAqB6zJ645MaqHfAMTdlsOK/fPlQywlTlgPb8Y/PyQc8asSkqWT55KMMDV+qNSKAG1zyTg=="

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
[ "$(git -C "$FORK" show -s --format=%P HEAD)" = "$FORK_PREVIOUS" ] \
  || fail "maintained fork head is not on expected predecessor $FORK_PREVIOUS"
[ "$(git -C "$FORK" show -s --format=%P "$FORK_PREVIOUS")" = "$FORK_QUALITY" ] \
  || fail "maintained fork predecessor is not on quality ancestor $FORK_QUALITY"
[ "$(git -C "$FORK" show -s --format=%P "$FORK_QUALITY")" = "$BASE_HEAD" ] \
  || fail "maintained fork quality ancestor is not on npm base $BASE_HEAD"

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
npm pack "pi-langfuse@1.5.14" --json --pack-destination "$TMP/packs" > "$TMP/pack.json"

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
    "1.5.14",
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

while IFS= read -r path; do
  cmp "$TMP/projected/$path" "$FORK/$path" \
    || fail "projected $path differs from maintained fork"
done < <(awk '/^\+\+\+ b\// {sub(/^\+\+\+ b\//, ""); print}' "$PATCH")

reverse_output=$(patch --force --fuzz=0 --reverse --dry-run -p1 -d "$TMP/projected" < "$PATCH" 2>&1)
if grep -Eiq 'offset|fuzz' <<<"$reverse_output"; then
  fail "reverse apply used offset or fuzz"
fi
patch --batch --silent --fuzz=0 --reverse -p1 -d "$TMP/projected" < "$PATCH"
diff -qr "$TMP/base" "$TMP/projected"

patch --batch --silent --fuzz=0 --forward -p1 -d "$TMP/projected" < "$PATCH"
mkdir "$TMP/projected/test"
cp "$FORK/test/quality.test.ts" "$TMP/projected/test/quality.test.ts"
ln -s "$FORK/node_modules" "$TMP/projected/node_modules"
(
  cd "$TMP/projected"
  node_modules/.bin/tsx --test test/quality.test.ts
)

echo "PASS: pi-langfuse npm base, fork projection, reversibility, and installed quality contract verified"
