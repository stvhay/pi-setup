#!/usr/bin/env bash
set -euo pipefail

ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || {
  echo "FAIL: vendor pin preflight must run inside a Git worktree" >&2
  exit 1
}
fail() {
  echo "FAIL: $*" >&2
  exit 1
}

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
GITMODULES=$TMP/gitmodules
CHECK_REPO=$TMP/fetch

git -C "$ROOT" show :.gitmodules >"$GITMODULES" 2>/dev/null || fail "missing staged .gitmodules"
git init --bare --quiet "$CHECK_REPO"

count=0
while IFS= read -r path_key; do
  prefix=${path_key%.path}
  path=$(git config --file "$GITMODULES" --get "$path_key") || fail "$path_key has no path"
  url=$(git config --file "$GITMODULES" --get "$prefix.url") || fail "$path has no configured remote URL"
  branch=$(git config --file "$GITMODULES" --get "$prefix.branch") || fail "$path has no configured remote branch"

  entry=$(git -C "$ROOT" ls-files --stage -- "$path")
  metadata=${entry%%$'\t'*}
  read -r mode pin stage <<<"$metadata"
  [ "$mode" = "160000" ] && [ "$stage" = "0" ] && [ -n "${pin:-}" ] || fail "$path is not a staged gitlink"

  if ! git -C "$CHECK_REPO" fetch --quiet --no-tags "$url" "refs/heads/$branch"; then
    fail "$path: cannot fetch $url branch $branch"
  fi
  if ! git -C "$CHECK_REPO" cat-file -e "$pin^{commit}" 2>/dev/null ||
     ! git -C "$CHECK_REPO" merge-base --is-ancestor "$pin" FETCH_HEAD; then
    fail "$path: pinned commit $pin is not reachable from $url branch $branch. Publish vendor commit before committing its superproject gitlink."
  fi

  printf 'OK: %s pin %s is published on %s\n' "$path" "$pin" "$branch"
  count=$((count + 1))
done < <(git config --file "$GITMODULES" --name-only --get-regexp '^submodule\..*\.path$')

[ "$count" -gt 0 ] || fail "no vendor submodules configured in $GITMODULES"
echo "PASS: all vendor pins are published"
