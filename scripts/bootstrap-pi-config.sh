#!/usr/bin/env bash
set -euo pipefail

MODE=dry-run
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
SOURCE=${PI_CONFIG_SOURCE:-$ROOT/pi}
DEST=${PI_CONFIG_DEST:-$HOME/.pi}

usage() {
  cat <<'EOF'
Usage: scripts/bootstrap-pi-config.sh [--dry-run|--apply]

Deploy the tracked Pi config from this repository's pi/ directory to ~/.pi.

This repository is the source of truth. The live ~/.pi directory is treated as
runtime/deployed state. Runtime secrets and local state are preserved.

Environment overrides:
  PI_CONFIG_SOURCE          Source config directory. Default: <repo>/pi
  PI_CONFIG_DEST            Destination. Default: $HOME/.pi
  PI_CONFIG_DEST_UNSAFE_OK  Set to 1 to allow a non-.pi destination after review.
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) MODE=dry-run ;;
    --apply) MODE=apply ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

run() {
  if [ "$MODE" = apply ]; then
    "$@"
  else
    printf 'DRY-RUN:'
    printf ' %q' "$@"
    printf '\n'
  fi
}

if [ ! -d "$SOURCE" ]; then
  echo "Config source directory is not available: $SOURCE" >&2
  exit 1
fi

if [ ! -f "$SOURCE/agent/AGENTS.md" ] || [ ! -x "$SOURCE/agent/bin/agnt" ]; then
  echo "Config source does not look like a deployable Pi config: $SOURCE" >&2
  exit 1
fi

resolve_path() {
  python3 -c 'import pathlib, sys; print(pathlib.Path(sys.argv[1]).expanduser().resolve(strict=False))' "$1"
}

refuse_dest() {
  echo "Refusing unsafe PI_CONFIG_DEST: $DEST" >&2
  echo "Reason: $1" >&2
  echo "Use the default ~/.pi destination, or set PI_CONFIG_DEST_UNSAFE_OK=1 only after reviewing the rsync --delete target." >&2
  exit 1
}

validate_dest() {
  local dest_abs source_abs root_abs home_abs dest_base
  dest_abs=$(resolve_path "$DEST")
  source_abs=$(resolve_path "$SOURCE")
  root_abs=$(resolve_path "$ROOT")
  home_abs=$(resolve_path "$HOME")
  dest_base=$(basename "$dest_abs")

  case "$dest_abs" in
    ""|"/") refuse_dest "destination is empty or filesystem root" ;;
  esac
  if [ "$dest_abs" = "$home_abs" ]; then
    refuse_dest "destination is the home directory"
  fi
  if [ "$dest_abs" = "$root_abs" ]; then
    refuse_dest "destination is the repository root"
  fi
  if [ "$dest_abs" = "$source_abs" ]; then
    refuse_dest "destination is the tracked source directory"
  fi
  if [ "$dest_base" != ".pi" ] && [ "${PI_CONFIG_DEST_UNSAFE_OK:-}" != 1 ]; then
    refuse_dest "destination basename must be .pi"
  fi
}

validate_dest

mkdir_parent() {
  local dir
  dir=$(dirname "$1")
  run mkdir -p "$dir"
}

mkdir_parent "$DEST"
if [ ! -e "$DEST" ]; then
  run mkdir -p "$DEST"
fi

# Retire legacy live git metadata. The repository checkout is now the source of
# truth; ~/.pi is a deployed runtime copy. Moving .git instead of deleting it
# preserves recovery information without leaving `git pull` as a misleading
# update path.
if [ -e "$DEST/.git" ]; then
  timestamp=$(date +%Y%m%d-%H%M%S)
  backup="$DEST/.git.backup-$timestamp"
  echo "Existing git metadata found at $DEST/.git; will move it to $backup."
  run mv "$DEST/.git" "$backup"
fi

# Preserve runtime secrets/state and project-local caches while deleting stale
# managed files. Excluded paths are not deleted by rsync --delete.
RSYNC_EXCLUDES=(
  --exclude='.git/'
  --exclude='.git.backup-*'
  --exclude='agent/auth.json'
  --exclude='agent/sessions/'
  --exclude='agent/npm/'
  --exclude='agent/git/'
  --exclude='agent/mcp-cache.json'
  --exclude='agent/mcp-onboarding.json'
  --exclude='agent/trust.json'
  --exclude='.pi/'
  --exclude='metrics/'
  --exclude='agent/macbook-ollama-power-*/'
  --exclude='__pycache__/'
  --exclude='*.py[cod]'
  --exclude='.DS_Store'
  --exclude='*.local'
  --exclude='*.local.json'
  --exclude='.env'
  --exclude='.env.*'
)

run rsync -a --delete "${RSYNC_EXCLUDES[@]}" "$SOURCE/" "$DEST/"
run touch "$DEST/.managed-by-pi-setup"

echo "Done. Verify with: PI_CONFIG_DIR=$DEST scripts/check-pi-config.sh"
