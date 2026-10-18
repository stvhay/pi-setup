#!/bin/sh
set -eu

fail() { printf '%s\n' "craft-mcp: $*" >&2; exit 1; }
usage() { printf '%s\n' 'usage: start-craft-mcp.sh photocraft|vectorcraft|cadcraft|soundcraft' >&2; exit 2; }
[ "$#" -eq 1 ] || usage
app=$1
case "$app" in
    photocraft) version=0.9.0; root=.artcraft/workspace ;;
    vectorcraft) version=0.12.0; root=.artcraft/vectorcraft-workspace-recovery ;;
    cadcraft) version=0.7.0; root=.artcraft/cadcraft-workspace ;;
    soundcraft) version=0.7.0; root=.artcraft/soundcraft-workspace ;;
    *) usage ;;
esac
case "${HOME:-}" in
    /*) ;;
    *) fail 'HOME must be absolute' ;;
esac
binary="$HOME/.artcraft/$app-cli-$version-macos-universal/$app-cli"
[ -f "$binary" ] && [ -x "$binary" ] || fail "missing executable: $binary"

set -- .artcraft "$root"
if [ "$app" = vectorcraft ]; then
    set -- "$@" "$root/config" "$root/config/Fonts"
fi
# shortcut: static path checks, use OS isolation if concurrent hostile writers are possible.
for dir do
    if [ -L "$dir" ] || { [ -e "$dir" ] && [ ! -d "$dir" ]; }; then
        fail "unsafe directory: $dir"
    fi
done
for dir do
    if [ ! -d "$dir" ]; then
        /bin/mkdir -m 700 "$dir" || fail "cannot create directory: $dir"
    fi
done

if [ "$app" = cadcraft ]; then
    # Upstream has no allowed-root flags. cwd is a convention, not confinement.
    # Explicit ./ bypasses inherited CDPATH lookup and its stdout output.
    cd "./$root" || fail "cannot enter directory: $root"
    exec "$binary" mcp
fi

set -- mcp
if [ "$app" = vectorcraft ]; then
    export VECTORCRAFT_CONFIG_DIR="$root/config" VECTORCRAFT_NO_PREFS=1
    set -- "$@" --headless
fi
exec "$binary" "$@" --automation-read-root "$root" --automation-write-root "$root"
