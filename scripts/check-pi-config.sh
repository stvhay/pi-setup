#!/usr/bin/env bash
set -euo pipefail

ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
PI_DIR=${PI_CONFIG_DIR:-$ROOT/pi}

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

check_exists() {
  local path=$1
  [ -e "$path" ] || fail "missing $path"
}

check_absent() {
  local path=$1
  [ ! -e "$path" ] || fail "private/generated state present: $path"
}

[ -d "$PI_DIR" ] || fail "missing Pi config directory: $PI_DIR"

SOURCE_CHECK=0
if [ "$PI_DIR" = "$ROOT/pi" ]; then
  SOURCE_CHECK=1
fi

# The source-of-truth config is now tracked directly under pi/. A nested .git
# file/directory means the old submodule topology has leaked back in.
if [ "$SOURCE_CHECK" = 1 ]; then
  [ ! -e "$ROOT/.gitmodules" ] || fail ".gitmodules is obsolete; pi/ should be tracked directly"
  [ ! -e "$PI_DIR/.git" ] || fail "$PI_DIR must not be a nested git checkout/submodule"
fi

check_exists "$PI_DIR/README.md"
check_exists "$PI_DIR/.gitignore"
check_exists "$PI_DIR/agent/AGENTS.md"
check_exists "$PI_DIR/agent/settings.json"
check_exists "$PI_DIR/agent/models.json"
check_exists "$PI_DIR/agent/catalog.json"
check_exists "$PI_DIR/agent/bin"
check_exists "$PI_DIR/agent/bin/agnt"
check_exists "$PI_DIR/agent/skills"
check_exists "$PI_DIR/agent/extensions"
check_exists "$PI_DIR/agent/mcp.json"

if [ -x "$PI_DIR/agent/bin/agnt" ]; then
  "$PI_DIR/agent/bin/agnt" action validate >/dev/null
  "$PI_DIR/agent/bin/agnt" context-health --strict >/dev/null
  "$PI_DIR/agent/bin/agnt" work audit --json >/dev/null
  "$PI_DIR/agent/bin/agnt" work health --json --no-beads >/dev/null
  prompt_inventory=$(mktemp)
  "$PI_DIR/agent/bin/agnt" prompt inventory >"$prompt_inventory"
  python3 -m json.tool "$prompt_inventory" >/dev/null
  rm -f "$prompt_inventory"
fi

if [ "$SOURCE_CHECK" = 1 ]; then
  check_absent "$PI_DIR/agent/auth.json"
  check_absent "$PI_DIR/agent/sessions"
  check_absent "$PI_DIR/agent/npm"
  check_absent "$PI_DIR/agent/git"
  check_absent "$PI_DIR/agent/mcp-cache.json"
  check_absent "$PI_DIR/agent/mcp-onboarding.json"
  check_absent "$PI_DIR/agent/trust.json"

  if git -C "$ROOT" ls-files | grep -E '(^|/)auth\.json$|(^|/)sessions/|(^|/)npm/|(^|/)git/|mcp-cache\.json|mcp-onboarding\.json|trust\.json' >/dev/null; then
    fail "private/generated state is tracked"
  fi

  if [ -d "$ROOT/.beads" ]; then
    check_exists "$ROOT/.beads/config.yaml"
    check_exists "$ROOT/.beads/metadata.json"
    check_exists "$ROOT/.beads/issues.jsonl"
    if git -C "$ROOT" ls-files | grep -E '^\.beads/(embeddeddolt|dolt|.*\.lock|\.local_version|export-state|last-touched|interactions\.jsonl)' >/dev/null; then
      fail "Beads runtime/local state is tracked"
    fi
  fi
fi

echo "PASS: Pi config layout is valid: $PI_DIR"
