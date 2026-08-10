#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

python3 -m py_compile bin/agent-instructions bin/agnt

bin/agnt -h >/tmp/agnt-help.txt
rg -n "Usage: agnt|tasks|route" /tmp/agnt-help.txt >/dev/null

bin/agnt tasks >/tmp/agnt-tasks.txt
rg -n "orchestration|review|research" /tmp/agnt-tasks.txt >/dev/null

bin/agnt tasks --models >/tmp/agnt-task-models.txt
rg -n "openai-codex/gpt-5\.6-sol" /tmp/agnt-task-models.txt >/dev/null
rg -n "openrouter/minimax/minimax-m3" /tmp/agnt-task-models.txt >/dev/null
rg -n "openrouter/anthropic/claude-opus-5" /tmp/agnt-task-models.txt >/dev/null

bin/agnt metrics -h >/tmp/agnt-metrics-help.txt
rg -n "status|consolidate|reset|prune|annotate" /tmp/agnt-metrics-help.txt >/dev/null
! rg -n "import-session" /tmp/agnt-metrics-help.txt >/dev/null
! rg -n "benchmark" /tmp/agnt-help.txt >/dev/null

bin/agnt instructions AGENTS.md --check >/tmp/agnt-instructions-check.txt
rg -n "PASS" /tmp/agnt-instructions-check.txt >/dev/null

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/AGENTS.d/models/openrouter/minimax"
printf '# Root\n' > "$TMP/AGENTS.md"
printf '# Provider context\n' > "$TMP/AGENTS.d/models/openrouter.md"
printf '# Nested model context\n' > "$TMP/AGENTS.d/models/openrouter/minimax/minimax-m3.md"
bin/agent-instructions "$TMP/AGENTS.md" --context openrouter/minimax/minimax-m3 > /tmp/agnt-nested-context.txt
rg -n "Provider context|Nested model context" /tmp/agnt-nested-context.txt >/dev/null
