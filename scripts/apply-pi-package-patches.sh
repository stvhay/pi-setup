#!/usr/bin/env bash
set -euo pipefail

MODE=apply
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PATCH_ROOT=${PI_PACKAGE_PATCH_DIR:-$ROOT/patches/pi-packages}
PACKAGE_ROOT=${PI_PACKAGE_ROOT:-${PI_CONFIG_DEST:-$HOME/.pi}/agent/npm/node_modules}

usage() {
  cat <<'EOF'
Usage: scripts/apply-pi-package-patches.sh [--check]

Apply version-locked temporary patches to Pi's installed npm packages.

Environment overrides:
  PI_PACKAGE_ROOT       node_modules root. Default: ~/.pi/agent/npm/node_modules
  PI_PACKAGE_PATCH_DIR  Patch directory. Default: <repo>/patches/pi-packages
  PI_CONFIG_DEST        Alternate Pi config root used when PI_PACKAGE_ROOT is unset
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --check) MODE=check ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

verify_package() {
  local package_dir=$1 expected_name=$2 expected_version=$3
  python3 - "$package_dir/package.json" "$expected_name" "$expected_version" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
expected_name, expected_version = sys.argv[2:]
try:
    package = json.loads(path.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError) as error:
    raise SystemExit(f"cannot read {path}: {error}")
name, version = package.get("name"), package.get("version")
if name != expected_name or version != expected_version:
    raise SystemExit(
        f"expected {expected_name} {expected_version} at {path.parent}; found {name or '<unknown>'} {version or '<unknown>'}"
    )
PY
}

patch_state() {
  local label=$1 package_dir=$2 expected_name=$3 expected_version=$4 patch_file=$5 marker_file=$6 marker=$7
  verify_package "$package_dir" "$expected_name" "$expected_version" || return 1
  if [ ! -f "$patch_file" ]; then
    echo "missing patch: $patch_file" >&2
    return 1
  fi
  if grep -Fq "$marker" "$package_dir/$marker_file"; then
    if patch --batch --silent --fuzz=0 --reverse --dry-run -p1 -d "$package_dir" < "$patch_file" >/dev/null 2>&1; then
      echo applied
      return
    fi
    echo "$label: installed source is only partially patched" >&2
    return 1
  fi
  if patch --batch --silent --fuzz=0 --forward --dry-run -p1 -d "$package_dir" < "$patch_file" >/dev/null 2>&1; then
    echo pending
    return
  fi
  echo "$label: patch does not match installed source" >&2
  return 1
}

apply_preflighted_patch() {
  local label=$1 package_dir=$2 patch_file=$3 state=$4
  if [ "$state" = applied ]; then
    echo "$label: already applied"
    return
  fi
  patch --batch --silent --fuzz=0 --forward -p1 -d "$package_dir" < "$patch_file"
  echo "$label: applied"
}

LANGFUSE_LABEL="pi-langfuse 1.5.9"
LANGFUSE_DIR="$PACKAGE_ROOT/pi-langfuse"
LANGFUSE_PATCH="$PATCH_ROOT/pi-langfuse-1.5.9.patch"
ARCHIMEDES_LABEL="@pi-archimedes/subagent 1.8.3"
ARCHIMEDES_DIR="$PACKAGE_ROOT/@pi-archimedes/subagent"
ARCHIMEDES_PATCH="$PATCH_ROOT/pi-archimedes-subagent-1.8.3.patch"

# Validate every package and patch before mutating either installed source tree.
LANGFUSE_STATE=$(patch_state "$LANGFUSE_LABEL" "$LANGFUSE_DIR" "pi-langfuse" "1.5.9" "$LANGFUSE_PATCH" "index.ts" "getSessionId?.()")
ARCHIMEDES_STATE=$(patch_state "$ARCHIMEDES_LABEL" "$ARCHIMEDES_DIR" "@pi-archimedes/subagent" "1.8.3" "$ARCHIMEDES_PATCH" "src/stream.ts" "childSessionId")

if [ "$MODE" = check ]; then
  echo "$LANGFUSE_LABEL: $LANGFUSE_STATE"
  echo "$ARCHIMEDES_LABEL: $ARCHIMEDES_STATE"
  exit
fi

apply_preflighted_patch "$LANGFUSE_LABEL" "$LANGFUSE_DIR" "$LANGFUSE_PATCH" "$LANGFUSE_STATE"
apply_preflighted_patch "$ARCHIMEDES_LABEL" "$ARCHIMEDES_DIR" "$ARCHIMEDES_PATCH" "$ARCHIMEDES_STATE"
