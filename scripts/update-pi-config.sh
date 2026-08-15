#!/usr/bin/env bash
set -euo pipefail

MODE=apply
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
SOURCE=${PI_CONFIG_SOURCE:-$ROOT/pi}
DEST=${PI_CONFIG_DEST:-$HOME/.pi}
PI_COMMAND=${PI_COMMAND:-pi}
PACKAGE_PATCH_HELPER=${PI_PACKAGE_PATCH_HELPER:-$ROOT/scripts/apply-pi-package-patches.sh}
PACKAGE_PATCH_DIR=${PI_PACKAGE_PATCH_DIR:-$ROOT/patches/pi-packages}
ARCHIMEDES_REINSTALL_BACKUP=
LANGFUSE_REINSTALL_BACKUP=

usage() {
  cat <<'EOF'
Usage: scripts/update-pi-config.sh [--dry-run]

Update ~/.pi from this repository's tracked pi/ directory.

This repository is the source of truth. The live ~/.pi directory is treated as
runtime/deployed state. Runtime secrets and local state are preserved. Missing,
mismatched, or stale-patch exact package bases are installed, then tracked patches run.

Environment overrides:
  PI_CONFIG_SOURCE          Source config directory. Default: <repo>/pi
  PI_CONFIG_DEST            Destination. Default: $HOME/.pi
  PI_CONFIG_DEST_UNSAFE_OK  Set to 1 to allow a non-.pi destination after review.
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) MODE=dry-run ;;
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

package_is_exact() {
  python3 - "$1" "$2" "$3" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
try:
    package = json.loads(path.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError):
    raise SystemExit(1)
raise SystemExit(0 if (package.get("name"), package.get("version")) == tuple(sys.argv[2:]) else 1)
PY
}

patch_dry_run_is_exact() {
  local direction=$1 package_dir=$2 patch_file=$3 output status=1
  output=$(mktemp)
  if [ "$direction" = reverse ]; then
    if patch --force --fuzz=0 --reverse --dry-run -p1 -d "$package_dir" \
      < "$patch_file" >"$output" 2>&1 \
      && ! grep -Eiq 'offset|fuzz' "$output"; then
      status=0
    fi
  elif patch --force --fuzz=0 --dry-run -p1 -d "$package_dir" \
    < "$patch_file" >"$output" 2>&1 \
    && ! grep -Eiq 'offset|fuzz' "$output"; then
    status=0
  fi
  rm -f "$output"
  return "$status"
}

package_patch_is_clean_or_applied() {
  local package_dir=$1 patch_file=$2
  patch_dry_run_is_exact reverse "$package_dir" "$patch_file" \
    || patch_dry_run_is_exact forward "$package_dir" "$patch_file"
}

pin_patch_base_dependency() {
  local relative=$1 name=$2 version=$3
  local manifest="$DEST/agent/npm/package.json"
  local package_json="$DEST/agent/npm/node_modules/$relative/package.json"
  package_is_exact "$package_json" "$name" "$version" || return 0
  if [ "$MODE" = dry-run ]; then
    echo "DRY-RUN: pin installed $name dependency to $version in $manifest"
    return
  fi
  [ -f "$manifest" ] || return 0
  python3 - "$manifest" "$name" "$version" <<'PY'
import json
import os
import pathlib
import sys
import tempfile

path = pathlib.Path(sys.argv[1])
name, version = sys.argv[2:]
data = json.loads(path.read_text(encoding="utf-8"))
dependencies = data.get("dependencies")
if not isinstance(dependencies, dict) or name not in dependencies or dependencies[name] == version:
    raise SystemExit(0)
dependencies[name] = version
with tempfile.NamedTemporaryFile(
    mode="w",
    encoding="utf-8",
    dir=path.parent,
    prefix=f".{path.name}.",
    delete=False,
) as output:
    json.dump(data, output, indent=2)
    output.write("\n")
    temporary_path = pathlib.Path(output.name)
temporary_path.chmod(path.stat().st_mode)
os.replace(temporary_path, path)
PY
}

restore_archimedes_reinstall_backup() {
  [ -n "$ARCHIMEDES_REINSTALL_BACKUP" ] || return 0
  local modules="$DEST/agent/npm/node_modules"
  if [ -d "$ARCHIMEDES_REINSTALL_BACKUP/pi-archimedes" ]; then
    rm -rf "$modules/pi-archimedes"
    mv "$ARCHIMEDES_REINSTALL_BACKUP/pi-archimedes" "$modules/pi-archimedes"
  fi
  if [ -d "$ARCHIMEDES_REINSTALL_BACKUP/@pi-archimedes/subagent" ]; then
    rm -rf "$modules/@pi-archimedes/subagent"
    mv "$ARCHIMEDES_REINSTALL_BACKUP/@pi-archimedes/subagent" "$modules/@pi-archimedes/subagent"
  fi
  if [ -d "$ARCHIMEDES_REINSTALL_BACKUP/@pi-archimedes/footer" ]; then
    rm -rf "$modules/@pi-archimedes/footer"
    mv "$ARCHIMEDES_REINSTALL_BACKUP/@pi-archimedes/footer" "$modules/@pi-archimedes/footer"
  fi
  rm -rf "$ARCHIMEDES_REINSTALL_BACKUP"
  ARCHIMEDES_REINSTALL_BACKUP=
}

restore_langfuse_reinstall_backup() {
  [ -n "$LANGFUSE_REINSTALL_BACKUP" ] || return 0
  local package_dir="$DEST/agent/npm/node_modules/pi-langfuse"
  if [ -d "$LANGFUSE_REINSTALL_BACKUP/pi-langfuse" ]; then
    rm -rf "$package_dir"
    mv "$LANGFUSE_REINSTALL_BACKUP/pi-langfuse" "$package_dir"
  fi
  rm -rf "$LANGFUSE_REINSTALL_BACKUP"
  LANGFUSE_REINSTALL_BACKUP=
}

reinstall_langfuse_patch_base() {
  local package_dir="$DEST/agent/npm/node_modules/pi-langfuse"
  if [ "$MODE" = dry-run ]; then
    run rm -rf "$package_dir"
    run env PI_CODING_AGENT_DIR="$DEST/agent" "$PI_COMMAND" install npm:pi-langfuse@1.5.14
    return
  fi

  local backup
  backup=$(mktemp -d "$DEST/agent/npm/.langfuse-reinstall.XXXXXX")
  LANGFUSE_REINSTALL_BACKUP=$backup
  mv "$package_dir" "$backup/pi-langfuse"
  if env PI_CODING_AGENT_DIR="$DEST/agent" "$PI_COMMAND" install npm:pi-langfuse@1.5.14 \
    && package_is_exact "$package_dir/package.json" pi-langfuse 1.5.14; then
    return
  fi

  restore_langfuse_reinstall_backup
  echo "Could not reinstall exact Langfuse patch base; restored previous package files" >&2
  return 1
}

install_langfuse_patch_base() {
  local package_dir="$DEST/agent/npm/node_modules/pi-langfuse"
  local package_json="$package_dir/package.json"
  local patch_file="$PACKAGE_PATCH_DIR/pi-langfuse-1.5.14.patch"
  if package_is_exact "$package_json" pi-langfuse 1.5.14; then
    if package_patch_is_clean_or_applied "$package_dir" "$patch_file"; then
      echo "pi-langfuse 1.5.14: already installed"
    else
      reinstall_langfuse_patch_base
    fi
  else
    run env PI_CODING_AGENT_DIR="$DEST/agent" "$PI_COMMAND" install npm:pi-langfuse@1.5.14
  fi
}

reinstall_archimedes_patch_base() {
  local modules="$DEST/agent/npm/node_modules"
  local meta_dir="$modules/pi-archimedes" subagent_dir="$modules/@pi-archimedes/subagent"
  local footer_dir="$modules/@pi-archimedes/footer"
  if [ "$MODE" = dry-run ]; then
    run rm -rf "$meta_dir" "$subagent_dir" "$footer_dir"
    run env PI_CODING_AGENT_DIR="$DEST/agent" "$PI_COMMAND" install npm:pi-archimedes@2.0.1
    return
  fi

  local backup
  backup=$(mktemp -d "$DEST/agent/npm/.archimedes-reinstall.XXXXXX")
  ARCHIMEDES_REINSTALL_BACKUP=$backup
  mkdir -p "$backup/@pi-archimedes"
  mv "$meta_dir" "$backup/pi-archimedes" || return 1
  mv "$subagent_dir" "$backup/@pi-archimedes/subagent" || return 1
  mv "$footer_dir" "$backup/@pi-archimedes/footer" || return 1
  if env PI_CODING_AGENT_DIR="$DEST/agent" "$PI_COMMAND" install npm:pi-archimedes@2.0.1 \
    && package_is_exact "$meta_dir/package.json" pi-archimedes 2.0.1 \
    && package_is_exact "$subagent_dir/package.json" @pi-archimedes/subagent 2.0.1 \
    && package_is_exact "$footer_dir/package.json" @pi-archimedes/footer 2.0.1; then
    return
  fi

  restore_archimedes_reinstall_backup
  echo "Could not reinstall exact Archimedes patch base; restored previous package files" >&2
  return 1
}

install_archimedes_patch_base() {
  local modules="$DEST/agent/npm/node_modules"
  local meta_dir="$modules/pi-archimedes" subagent_dir="$modules/@pi-archimedes/subagent"
  local footer_dir="$modules/@pi-archimedes/footer"
  local meta="$meta_dir/package.json" subagent="$subagent_dir/package.json" footer="$footer_dir/package.json"
  local meta_patch="$PACKAGE_PATCH_DIR/pi-archimedes-meta-2.0.1.patch"
  local subagent_patch="$PACKAGE_PATCH_DIR/pi-archimedes-subagent-2.0.1.patch"
  local footer_patch="$PACKAGE_PATCH_DIR/pi-archimedes-footer-2.0.1.patch"
  if package_is_exact "$meta" pi-archimedes 2.0.1 \
    && package_is_exact "$subagent" @pi-archimedes/subagent 2.0.1 \
    && package_is_exact "$footer" @pi-archimedes/footer 2.0.1; then
    if package_patch_is_clean_or_applied "$meta_dir" "$meta_patch" \
      && package_patch_is_clean_or_applied "$subagent_dir" "$subagent_patch" \
      && package_patch_is_clean_or_applied "$footer_dir" "$footer_patch"; then
      echo "pi-archimedes 2.0.1: already installed"
      echo "@pi-archimedes/subagent 2.0.1: already installed"
      echo "@pi-archimedes/footer 2.0.1: already installed"
    else
      reinstall_archimedes_patch_base
    fi
  else
    run env PI_CODING_AGENT_DIR="$DEST/agent" "$PI_COMMAND" install npm:pi-archimedes@2.0.1
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

# Preserve the Pi-managed changelog marker while replacing the rest of the
# repository-managed settings file. The temporary copy is mode 0600 and is
# removed on exit.
RUNTIME_SETTINGS_BACKUP=
cleanup() {
  local status=$?
  if [ "$status" -ne 0 ]; then
    restore_archimedes_reinstall_backup
    restore_langfuse_reinstall_backup
  else
    if [ -n "$ARCHIMEDES_REINSTALL_BACKUP" ]; then
      rm -rf "$ARCHIMEDES_REINSTALL_BACKUP"
      ARCHIMEDES_REINSTALL_BACKUP=
    fi
    if [ -n "$LANGFUSE_REINSTALL_BACKUP" ]; then
      rm -rf "$LANGFUSE_REINSTALL_BACKUP"
      LANGFUSE_REINSTALL_BACKUP=
    fi
  fi
  if [ -n "$RUNTIME_SETTINGS_BACKUP" ]; then
    rm -f "$RUNTIME_SETTINGS_BACKUP"
  fi
  return "$status"
}
trap cleanup EXIT

if [ "$MODE" = apply ] && [ -f "$DEST/agent/settings.json" ]; then
  RUNTIME_SETTINGS_BACKUP=$(mktemp "${TMPDIR:-/tmp}/pi-settings.XXXXXX")
  cp "$DEST/agent/settings.json" "$RUNTIME_SETTINGS_BACKUP"
fi

# Olla provider support was retired, but machine-local extensions normally
# survive deploys. Preserve the obsolete override as runtime evidence while
# removing it from Pi extension discovery.
legacy_ollama_extension="$DEST/agent/extensions/ollama.local.ts"
if [ -f "$legacy_ollama_extension" ] && grep -qF './olla-provider.ts' "$legacy_ollama_extension"; then
  retired_dir="$DEST/runtime/retired-config"
  if [ "$MODE" = apply ]; then
    mkdir -p "$retired_dir"
    backup=$(mktemp "$retired_dir/ollama.local.ts-XXXXXX")
  else
    backup="$retired_dir/ollama.local.ts-XXXXXX"
    run mkdir -p "$retired_dir"
  fi
  echo "Retiring incompatible machine-local Ollama extension to $backup."
  run mv "$legacy_ollama_extension" "$backup"
fi

# Preserve runtime secrets/state while deleting stale managed files. Source-only
# metadata and caches are not deployed or deletion-protected.
RSYNC_EXCLUDES=(
  --filter='-s .git/'
  --exclude='.git.backup-*'
  --exclude='agent/auth.json'
  --exclude='agent/sessions/'
  --exclude='agent/pi-langfuse/'
  --exclude='agent/npm/'
  --exclude='agent/git/'
  --exclude='agent/mcp-cache.json'
  --exclude='agent/mcp-onboarding.json'
  --exclude='agent/models-store.json'
  --exclude='agent/trust.json'
  --exclude='agent/extensions/*.local.ts'
  --exclude='.pi/'
  --exclude='improvement/'
  --exclude='metrics/'
  --exclude='runtime/'
  --exclude='agent/macbook-ollama-power-*/'
  --filter='-s __pycache__/'
  --filter='-s *.py[cod]'
  --exclude='.DS_Store'
  --exclude='*.local'
  --exclude='*.local.json'
  --exclude='.env'
  --exclude='.env.*'
)

run rsync -a --delete "${RSYNC_EXCLUDES[@]}" "$SOURCE/" "$DEST/"

if [ "$MODE" = apply ] && [ -n "$RUNTIME_SETTINGS_BACKUP" ]; then
  python3 - "$RUNTIME_SETTINGS_BACKUP" "$DEST/agent/settings.json" <<'PY'
import json
import os
import pathlib
import sys
import tempfile

runtime_path = pathlib.Path(sys.argv[1])
deployed_path = pathlib.Path(sys.argv[2])
runtime_settings = json.loads(runtime_path.read_text(encoding="utf-8"))
if "lastChangelogVersion" in runtime_settings:
    deployed_settings = json.loads(deployed_path.read_text(encoding="utf-8"))
    deployed_settings["lastChangelogVersion"] = runtime_settings["lastChangelogVersion"]
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=deployed_path.parent,
        prefix=f".{deployed_path.name}.",
        delete=False,
    ) as output:
        json.dump(deployed_settings, output, indent=2)
        output.write("\n")
        temporary_path = pathlib.Path(output.name)
    temporary_path.chmod(deployed_path.stat().st_mode)
    os.replace(temporary_path, deployed_path)
PY
elif [ "$MODE" = dry-run ] && [ -f "$DEST/agent/settings.json" ]; then
  echo "DRY-RUN: preserve Pi-managed lastChangelogVersion in $DEST/agent/settings.json"
fi

# Reconcile only missing, mismatched, or stale version-locked patch bases.
# Keep their npm manifest entries exact before and after each install so npm cannot
# reify a newly released version of one patch base while installing the other.
pin_patch_base_dependency "pi-archimedes" "pi-archimedes" "2.0.1"
pin_patch_base_dependency "pi-langfuse" "pi-langfuse" "1.5.14"
install_archimedes_patch_base
pin_patch_base_dependency "pi-archimedes" "pi-archimedes" "2.0.1"
install_langfuse_patch_base
pin_patch_base_dependency "pi-langfuse" "pi-langfuse" "1.5.14"
if [ "$MODE" = dry-run ]; then
  run env PI_CONFIG_DEST="$DEST" "$PACKAGE_PATCH_HELPER"
elif env PI_CONFIG_DEST="$DEST" "$PACKAGE_PATCH_HELPER"; then
  : # Keep any reinstall backup until every later deployment step succeeds.
else
  restore_archimedes_reinstall_backup
  exit 1
fi

if [ "$MODE" = apply ]; then
  if [ -n "${LANGFUSE_PUBLIC_KEY:-}" ] && [ -n "${LANGFUSE_SECRET_KEY:-}" ] && [ -n "${LANGFUSE_BASE_URL:-${LANGFUSE_HOST:-}}" ] || python3 - "$DEST/agent/pi-langfuse/config.json" <<'PY'
import json
import pathlib
import sys

try:
    config = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError):
    raise SystemExit(1)
raise SystemExit(0 if all(config.get(key) for key in ("publicKey", "secretKey", "host")) else 1)
PY
  then
    PI_CONFIG_DIR="$DEST" "$DEST/agent/bin/agnt" langfuse apply
  else
    echo "Skipping Langfuse evaluator sync: credentials are not configured."
  fi
else
  echo "DRY-RUN: $DEST/agent/bin/agnt langfuse apply (when Langfuse credentials are configured)"
fi

run touch "$DEST/.managed-by-pi-setup"

echo "Done. Verify with: PI_CONFIG_DIR=$DEST scripts/check-pi-config.sh"
