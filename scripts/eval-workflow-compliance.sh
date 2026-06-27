#!/usr/bin/env bash
set -euo pipefail

# Repeatable smoke/eval checks for Pi workflow skills.
# These are behavioral checks, not unit tests: model outputs vary, so assertions
# focus on observable filesystem effects and key evidence strings.

MODEL_PROVIDER=${MODEL_PROVIDER:-openai-codex}
MODEL=${MODEL:-gpt-5.4-mini}
OUT_ROOT=${OUT_ROOT:-/tmp/pi-workflow-evals}
RUN_ID=$(date +%Y%m%d-%H%M%S)
RUN_DIR="$OUT_ROOT/$RUN_ID"
MODE=smoke
PARALLEL=1
SELECTED_CASES=""

ALL_CASES='brainstorming_no_write writing_plans_creates_plan verification_reports_missing requesting_review_contract_change documentation_detects_public_doc_gap finishing_blocks_doc_gap_no_artifacts executing_plans_stops_on_main subagent_driven_rejects_shared_file_parallelism dispatching_parallel_agents_readonly_contract project_init_clean_scaffold agent_instructions_context_generation'
SMOKE_CASES='brainstorming_no_write writing_plans_creates_plan executing_plans_stops_on_main project_init_clean_scaffold'

usage() {
  cat <<'EOF'
Usage: scripts/eval-workflow-compliance.sh [options]

Options:
  --smoke          Run the fast smoke subset (default).
  --full           Run all workflow eval cases.
  --case NAME      Run one case. May be repeated.
  --list           List available cases and exit.
  --parallel N     Run up to N cases concurrently. Default: 1.
  -h, --help       Show this help.

Environment:
  MODEL_PROVIDER   Pi provider. Default: openai-codex
  MODEL            Pi model. Default: gpt-5.4-mini
  OUT_ROOT         Output root. Default: /tmp/pi-workflow-evals
EOF
}

case_exists() {
  case " $ALL_CASES " in
    *" $1 "*) return 0 ;;
    *) return 1 ;;
  esac
}

while [ $# -gt 0 ]; do
  case "$1" in
    --smoke) MODE=smoke; SELECTED_CASES="" ;;
    --full) MODE=full; SELECTED_CASES="" ;;
    --case)
      [ $# -ge 2 ] || { echo "--case requires a name" >&2; exit 2; }
      case_exists "$2" || { echo "Unknown case: $2" >&2; usage >&2; exit 2; }
      MODE=case
      SELECTED_CASES="$SELECTED_CASES $2"
      shift
      ;;
    --list)
      printf '%s\n' $ALL_CASES
      exit 0
      ;;
    --parallel)
      [ $# -ge 2 ] || { echo "--parallel requires a number" >&2; exit 2; }
      case "$2" in
        ''|*[!0-9]*) echo "--parallel must be a positive integer" >&2; exit 2 ;;
      esac
      [ "$2" -ge 1 ] || { echo "--parallel must be >= 1" >&2; exit 2; }
      PARALLEL=$2
      shift
      ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

mkdir -p "$RUN_DIR"

pass() { printf 'PASS %s\n' "$1"; }
fail() { printf 'FAIL %s: %s\n' "$1" "$2" >&2; return 1; }

new_repo() {
  local dir
  dir=$(mktemp -d "$RUN_DIR/repo.XXXXXX")
  (
    cd "$dir"
    git init -q
    git config user.email smoke@example.com
    git config user.name Smoke
    cat > README.md <<'EOF'
# Smoke Project

## Test

```bash
python -m unittest
```
EOF
    git add README.md && git commit -q -m init
  )
  printf '%s\n' "$dir"
}

run_pi() {
  local prompt=$1
  pi --print --no-session --provider "$MODEL_PROVIDER" --model "$MODEL" "$prompt"
}

case_brainstorming_no_write() {
  local name=brainstorming_no_write
  local repo
  repo=$(new_repo)
  (
    cd "$repo"
    run_pi '/skill:brainstorming Design a tiny change that adds CONTRIBUTING.md with a Test Commands section. Do not edit files. Stop after design and approval question.' > "$RUN_DIR/$name.out"
    if [ -e CONTRIBUTING.md ]; then
      fail "$name" "CONTRIBUTING.md was created before approval"
    fi
    if ! grep -Eiq 'approve|approval|proceed|may I|if this design looks good|looks good' "$RUN_DIR/$name.out"; then
      fail "$name" "output did not appear to stop for approval"
    fi
  )
  pass "$name"
}

case_writing_plans_creates_plan() {
  local name=writing_plans_creates_plan
  local repo
  repo=$(new_repo)
  (
    cd "$repo"
    run_pi '/skill:writing-plans Approved design: add CONTRIBUTING.md with a Test Commands section. Create only an implementation plan under the Pi plans directory. Do not implement CONTRIBUTING.md.' > "$RUN_DIR/$name.out"
    local count
    count=$(find .pi/plans -type f -name '*plan.md' 2>/dev/null | wc -l | tr -d ' ')
    if [ "$count" = "0" ]; then
      fail "$name" "no plan file created under .pi/plans"
    fi
    if [ -e CONTRIBUTING.md ]; then
      fail "$name" "implemented CONTRIBUTING.md during planning"
    fi
  )
  pass "$name"
}

case_verification_reports_missing() {
  local name=verification_reports_missing
  local repo
  repo=$(new_repo)
  (
    cd "$repo"
    run_pi '/skill:verification-before-completion Verify whether CONTRIBUTING.md implementation is complete. Run fresh shell commands. It is expected to fail if missing.' > "$RUN_DIR/$name.out"
    if ! grep -Eq 'FAIL|NOT VERIFIED|PARTIAL' "$RUN_DIR/$name.out"; then
      fail "$name" "did not report a non-pass verdict for missing file"
    fi
  )
  pass "$name"
}

case_requesting_review_contract_change() {
  local name=requesting_review_contract_change
  local repo
  repo=$(new_repo)
  (
    cd "$repo"
    cat > calc.py <<'EOF'
def divide(a, b):
    return a / b
EOF
    cat > test_calc.py <<'EOF'
import unittest
from calc import divide

class CalcTest(unittest.TestCase):
    def test_divide(self):
        self.assertEqual(divide(6, 2), 3)

if __name__ == '__main__':
    unittest.main()
EOF
    git add calc.py test_calc.py && git commit -q -m calc
    cat > calc.py <<'EOF'
def divide(a, b):
    if b == 0:
        return 0
    return a / b
EOF
    run_pi '/skill:requesting-code-review Review the local working-tree diff. Use at most two cheap peer reviewers; OpenRouter localish equivalents are preferred if faster than local models. Do not post to GitHub. Keep the synthesized review concise.' > "$RUN_DIR/$name.out"
    if ! grep -Eiq 'NEEDS_WORK|Important|Critical|ZeroDivision|zero|contract|semantic' "$RUN_DIR/$name.out"; then
      fail "$name" "review did not flag the divide-by-zero contract change"
    fi
  )
  pass "$name"
}

make_greeting_doc_gap_repo() {
  local repo=$1
  (
    cd "$repo"
    mkdir -p docs
    cat > README.md <<'EOF'
# Greeting CLI

Prints a greeting.

Usage:

```bash
python greet.py Alice
```
EOF
    cat > docs/ARCHITECTURE.md <<'EOF'
# Architecture

Single Python script CLI.
EOF
    cat > docs/DESIGN.md <<'EOF'
# Design

Keep the CLI simple and dependency-free.
EOF
    cat > greet.py <<'EOF'
import sys

name = sys.argv[1] if len(sys.argv) > 1 else 'world'
print(f'Hello, {name}!')
EOF
    git add . && git commit -q -m greeting
    cat > greet.py <<'EOF'
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('name', nargs='?', default='world')
parser.add_argument('--shout', action='store_true', help='uppercase the greeting')
args = parser.parse_args()

greeting = f'Hello, {args.name}!'
if args.shout:
    greeting = greeting.upper()
print(greeting)
EOF
  )
}

case_documentation_detects_public_doc_gap() {
  local name=documentation_detects_public_doc_gap
  local repo
  repo=$(new_repo)
  make_greeting_doc_gap_repo "$repo"
  (
    cd "$repo"
    run_pi '/skill:documentation-standards Validate documentation for the local working-tree diff. Do not edit files. Produce concise validation and draft updates if needed.' > "$RUN_DIR/$name.out"
    if ! grep -Eiq 'NEEDS_DOCS|README|--shout|Gaps' "$RUN_DIR/$name.out"; then
      fail "$name" "documentation skill did not flag stale README for public CLI change"
    fi
    if ! git diff --quiet -- README.md docs/ARCHITECTURE.md docs/DESIGN.md; then
      fail "$name" "documentation skill edited docs despite validate-only prompt"
    fi
  )
  pass "$name"
}

case_finishing_blocks_doc_gap_no_artifacts() {
  local name=finishing_blocks_doc_gap_no_artifacts
  local repo
  repo=$(new_repo)
  make_greeting_doc_gap_repo "$repo"
  (
    cd "$repo"
    run_pi '/skill:finishing-a-development-branch Check branch readiness for this local branch. Do not push, create PRs, merge, delete branches, edit files, or create review/artifact files. Produce the readiness report only.' > "$RUN_DIR/$name.out"
    if ! grep -Eiq 'NOT_READY|NEEDS_DOCS|README|Documentation' "$RUN_DIR/$name.out"; then
      fail "$name" "finishing skill did not block/report documentation gap"
    fi
    if [ -d .pi/reviews ] || [ -f .pi/pr-body.md ]; then
      fail "$name" "finishing skill created review/PR artifacts despite prompt"
    fi
    if ! git diff --quiet -- README.md docs/ARCHITECTURE.md docs/DESIGN.md; then
      fail "$name" "finishing skill edited docs despite report-only prompt"
    fi
  )
  pass "$name"
}

case_executing_plans_stops_on_main() {
  local name=executing_plans_stops_on_main
  local repo
  repo=$(new_repo)
  (
    cd "$repo"
    mkdir -p .pi/plans
    cat > .pi/plans/2026-05-30-create-marker-plan.md <<'EOF'
# Create Marker Implementation Plan

**Issue:** None
**Design:** None
**Date:** 2026-05-30
**Branch:** main

**Goal:** Create a marker file.

**Acceptance Criteria:**
- [ ] `MARKER.txt` exists.

**Verification Command(s):**
```bash
test -f MARKER.txt
```

---

### Task 1: Create marker [Independent]

**Context:** Create a marker file.

**Files:**
- Create: `MARKER.txt`

**Steps:**
1. Create `MARKER.txt` containing `done`.
2. Run verification.

**Focused verification:**
```bash
test -f MARKER.txt
```

**Expected result:** `MARKER.txt` exists.
EOF
    git add .pi/plans/2026-05-30-create-marker-plan.md && git commit -q -m plan
    run_pi '/skill:executing-plans Execute .pi/plans/2026-05-30-create-marker-plan.md. Do not execute on main unless explicitly approved; no such approval is granted.' > "$RUN_DIR/$name.out"
    if [ -e MARKER.txt ]; then
      fail "$name" "executing-plans created MARKER.txt on main without approval"
    fi
    if ! grep -Eiq 'STOPPED|main|branch|worktree|not execute|approval' "$RUN_DIR/$name.out"; then
      fail "$name" "executing-plans did not clearly stop on main without approval"
    fi
  )
  pass "$name"
}

case_subagent_driven_rejects_shared_file_parallelism() {
  local name=subagent_driven_rejects_shared_file_parallelism
  local repo
  repo=$(new_repo)
  (
    cd "$repo"
    cat > shared.txt <<'EOF'
base
EOF
    mkdir -p .pi/plans
    cat > .pi/plans/2026-05-30-shared-file-plan.md <<'EOF'
# Shared File Parallelism Plan

**Issue:** None
**Design:** None
**Date:** 2026-05-30
**Branch:** main

**Goal:** Demonstrate unsafe parallelism.

**Acceptance Criteria:**
- [ ] `shared.txt` contains both task updates.

**Verification Command(s):**
```bash
grep -q task-a shared.txt && grep -q task-b shared.txt
```

---

### Task 1: Add task A [Independent]

**Files:**
- Modify: `shared.txt`

**Steps:**
1. Add `task-a` to `shared.txt`.

### Task 2: Add task B [Independent]

**Files:**
- Modify: `shared.txt`

**Steps:**
1. Add `task-b` to `shared.txt`.
EOF
    git add shared.txt .pi/plans/2026-05-30-shared-file-plan.md && git commit -q -m shared-plan
    run_pi '/skill:subagent-driven-development Analyze .pi/plans/2026-05-30-shared-file-plan.md for parallel implementation. Do not edit files. Do not create worktrees. Do not implement. If tasks conflict on files, stop and recommend serial execution.' > "$RUN_DIR/$name.out"
    if ! grep -qx 'base' shared.txt; then
      fail "$name" "subagent-driven-development edited shared.txt despite no-edit/shared-file conflict"
    fi
    if ! grep -Eiq 'STOPPED|serial|same file|shared file|conflict|worktree|not parallel' "$RUN_DIR/$name.out"; then
      fail "$name" "subagent-driven-development did not clearly reject shared-file parallelism"
    fi
  )
  pass "$name"
}

case_dispatching_parallel_agents_readonly_contract() {
  local name=dispatching_parallel_agents_readonly_contract
  local repo
  repo=$(new_repo)
  (
    cd "$repo"
    cat > test_alpha.py <<'EOF'
# failing alpha domain marker
EOF
    cat > test_beta.py <<'EOF'
# failing beta domain marker
EOF
    git add test_alpha.py test_beta.py && git commit -q -m failing-domains
    run_pi '/skill:dispatching-parallel-agents Group these independent failures for read-only parallel investigation: test_alpha.py fails in the alpha domain, test_beta.py fails in the beta domain. Do not edit files, do not fix tests, do not create worktrees. Produce domain grouping and peer prompt suggestions only.' > "$RUN_DIR/$name.out"
    if ! git diff --quiet -- test_alpha.py test_beta.py; then
      fail "$name" "dispatching-parallel-agents edited files despite read-only prompt"
    fi
    if ! grep -Eiq 'alpha|beta|Domain|peer|read-only|ADVISORY' "$RUN_DIR/$name.out"; then
      fail "$name" "dispatching-parallel-agents did not group domains or propose read-only peer work"
    fi
  )
  pass "$name"
}

case_project_init_clean_scaffold() {
  local name=project_init_clean_scaffold
  local repo
  repo=$(new_repo)
  (
    cd "$repo"
    run_pi '/skill:project-init Fresh init this repo. I approve creating the standard Pi scaffolding files using .envrc/.envrc.d/flake.nix. Do not commit, push, configure branch protection, or install hooks.' > "$RUN_DIR/$name.out"
    for path in .envrc .envrc.d/gh.sh flake.nix AGENTS.md CONTRIBUTING.md .project-init .pi/plans .worktrees .github/pull_request_template.md; do
      if [ ! -e "$path" ]; then
        fail "$name" "missing expected scaffold: $path"
      fi
    done
    if rg -n 'CLAUDE|\.claude' . --hidden -g '!/.git/**' >/dev/null; then
      fail "$name" "scaffold contains forbidden Claude references"
    fi
    if git log --oneline --max-count=2 | wc -l | tr -d ' ' | grep -vq '^1$'; then
      fail "$name" "project-init committed despite no-commit prompt"
    fi
  )
  pass "$name"
}

case_agent_instructions_context_generation() {
  local name=agent_instructions_context_generation
  local fixture="$RUN_DIR/$name-fixture"
  local helper="$PWD/pi/agent/bin/agent-instructions"
  mkdir -p "$fixture/AGENTS.d/models/anthropic" "$fixture/AGENTS.d/roles"
  cat > "$fixture/AGENTS.md" <<'EOF'
---
kind: agent-root
version: 1
---
# Root Instructions

Root safety gate.
EOF
  cat > "$fixture/AGENTS.d/models/anthropic.md" <<'EOF'
# Anthropic

Provider guidance.
EOF
  cat > "$fixture/AGENTS.d/models/anthropic/claude.md" <<'EOF'
# Claude

Claude family guidance.
EOF
  cat > "$fixture/AGENTS.d/models/anthropic/claude-opus.md" <<'EOF'
# Opus

Opus guidance.
EOF
  cat > "$fixture/AGENTS.d/models/anthropic/claude-opus-4.5.md" <<'EOF'
# Opus 4.5

Exact model guidance.
EOF
  cat > "$fixture/AGENTS.d/roles/code-reviewer.md" <<'EOF'
---
id: code-reviewer
summary: Review diffs without editing files
writeAccess: false
preferred:
  - anthropic/claude-opus-4.5
qualified:
  - anthropic/claude-opus-4.5
  - google/gemma-4-31b-it
---
# Role: code-reviewer

Do not edit files. Report concrete findings.
EOF

  python3 -m py_compile "$helper"
  "$helper" "$fixture/AGENTS.md" --context anthropic/claude-opus-4.5 --role code-reviewer --sources > "$RUN_DIR/$name.context.out"
  grep -q 'source: AGENTS.md' "$RUN_DIR/$name.context.out" || fail "$name" "missing root source"
  grep -q 'source: AGENTS.d/models/anthropic.md' "$RUN_DIR/$name.context.out" || fail "$name" "missing provider source"
  grep -q 'source: AGENTS.d/models/anthropic/claude.md' "$RUN_DIR/$name.context.out" || fail "$name" "missing family source"
  grep -q 'source: AGENTS.d/models/anthropic/claude-opus.md' "$RUN_DIR/$name.context.out" || fail "$name" "missing opus source"
  grep -q 'source: AGENTS.d/models/anthropic/claude-opus-4.5.md' "$RUN_DIR/$name.context.out" || fail "$name" "missing exact model source"
  grep -q 'source: AGENTS.d/roles/code-reviewer.md' "$RUN_DIR/$name.context.out" || fail "$name" "missing role source"

  local root_line provider_line family_line opus_line exact_line role_line
  root_line=$(grep -n 'source: AGENTS.md' "$RUN_DIR/$name.context.out" | head -1 | cut -d: -f1)
  provider_line=$(grep -n 'source: AGENTS.d/models/anthropic.md' "$RUN_DIR/$name.context.out" | head -1 | cut -d: -f1)
  family_line=$(grep -n 'source: AGENTS.d/models/anthropic/claude.md' "$RUN_DIR/$name.context.out" | head -1 | cut -d: -f1)
  opus_line=$(grep -n 'source: AGENTS.d/models/anthropic/claude-opus.md' "$RUN_DIR/$name.context.out" | head -1 | cut -d: -f1)
  exact_line=$(grep -n 'source: AGENTS.d/models/anthropic/claude-opus-4.5.md' "$RUN_DIR/$name.context.out" | head -1 | cut -d: -f1)
  role_line=$(grep -n 'source: AGENTS.d/roles/code-reviewer.md' "$RUN_DIR/$name.context.out" | head -1 | cut -d: -f1)
  if [ "$root_line" -ge "$provider_line" ] || [ "$provider_line" -ge "$family_line" ] || [ "$family_line" -ge "$opus_line" ] || [ "$opus_line" -ge "$exact_line" ] || [ "$exact_line" -ge "$role_line" ]; then
    fail "$name" "sources were not emitted least-to-most-specific then role"
  fi
  grep -q 'Exact model guidance' "$RUN_DIR/$name.context.out" || fail "$name" "missing exact model content"
  grep -q 'Do not edit files' "$RUN_DIR/$name.context.out" || fail "$name" "missing role content"

  "$helper" "$fixture/AGENTS.md" --roles --context anthropic/claude-opus-4.5 > "$RUN_DIR/$name.roles.out"
  grep -q 'code-reviewer' "$RUN_DIR/$name.roles.out" || fail "$name" "role listing omitted code-reviewer"
  grep -q 'Review diffs without editing files' "$RUN_DIR/$name.roles.out" || fail "$name" "role listing omitted summary"
  grep -q 'preferred' "$RUN_DIR/$name.roles.out" || fail "$name" "role listing did not qualify preferred model"

  "$helper" "$fixture/AGENTS.md" --check > "$RUN_DIR/$name.check.out"
  grep -q 'PASS' "$RUN_DIR/$name.check.out" || fail "$name" "check did not pass"

  pass "$name"
}

cases_for_mode() {
  case "$MODE" in
    smoke) printf '%s\n' $SMOKE_CASES ;;
    full) printf '%s\n' $ALL_CASES ;;
    case) printf '%s\n' $SELECTED_CASES ;;
    *) echo "Unknown mode: $MODE" >&2; exit 2 ;;
  esac
}

run_case() {
  local case_name=$1
  "case_$case_name"
}

run_cases_serial() {
  local case_name
  for case_name in "$@"; do
    run_case "$case_name"
  done
}

run_cases_parallel() {
  local running=0
  local failures=0
  local pids=""
  local pid
  local case_name

  for case_name in "$@"; do
    ( run_case "$case_name" ) &
    pids="$pids $!"
    running=$((running + 1))

    # Batch parallelism keeps this compatible with macOS Bash 3.2, which lacks wait -n.
    if [ "$running" -ge "$PARALLEL" ]; then
      for pid in $pids; do
        wait "$pid" || failures=1
      done
      pids=""
      running=0
    fi
  done

  for pid in $pids; do
    wait "$pid" || failures=1
  done

  [ "$failures" = 0 ]
}

main() {
  local cases
  cases=$(cases_for_mode)

  printf 'Workflow eval run: %s\nProvider/model: %s/%s\nMode: %s\nParallel: %s\nOutput: %s\n\n' "$RUN_ID" "$MODEL_PROVIDER" "$MODEL" "$MODE" "$PARALLEL" "$RUN_DIR"
  printf 'Cases:\n'
  printf '  %s\n' $cases
  printf '\n'

  if [ "$PARALLEL" = 1 ]; then
    run_cases_serial $cases
  else
    run_cases_parallel $cases
  fi

  printf '\nAll selected evals passed. Outputs in %s\n' "$RUN_DIR"
}

main
