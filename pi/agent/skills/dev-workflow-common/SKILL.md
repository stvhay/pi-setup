---
name: dev-workflow-common
description: Use only when another workflow skill requests shared Pi development conventions.
disable-model-invocation: true
---

# Dev Workflow Common

Shared conventions for Pi development workflow skills. Keep this file small and searchable.

## Filesystem-first context

Prefer durable, greppable artifacts over chat-only state:

- Plans/designs: project-local `.pi/plans/` by default.
- Scratch peer outputs: project-local `.pi/peer-runs/`, `.pi/council/`, `.pi/redteam/`, `.pi/research/` as appropriate.
- Use `rg`, `find`, `git grep`, `git diff`, and exact paths instead of pasting large context into prompts.
- Keep instructions DRY: reference files and commands by path rather than duplicating long text.
- Do not leave avoidable generated artifacts (`__pycache__`, temporary logs, build output) unless they are intentionally part of the task.

## Knowledge graph

If `graphify-out/graph.json` exists, use it to map code structure before broad exploration:

```bash
agnt graphify query "<keyword>"     # lexical label match + BFS expansion
agnt graphify explain "<symbol>"    # one node's callers/dependents with file:line
agnt graphify path "<A>" "<B>"      # shortest connection between two nodes
```

- Queries are lexical, not semantic. Use short identifier/concept keywords (`query "route"`), never sentence-form questions. Run 2-3 keyword probes rather than one long query.
- Treat results as a map of `file:line` locations to read next, not as answers. Verify against source files before acting.
- The graph is built at the last commit (`built_at_commit` in `graph.json`); uncommitted edits and newly added symbols are absent. Use it for pre-change structure and impact analysis, not to inspect brand-new code.

## Task tiers

Choose ceremony by risk, not habit:

- **Tiny:** obvious one-file/doc/config change. Inline design, edit, focused verify, summarize. No plan file unless requested.
- **Normal:** small feature/bugfix. Concise approved design; use a combined design-plan artifact when useful.
- **Large/risky:** architecture, public API, data/security, multi-file uncertainty. Use separate design, plan, checkpoints, review, docs validation.
- **Parallelizable:** independent domains with disjoint files and verification. Use advisory peers by default; use worktrees only with explicit approval.

Hard gates still apply: approval before implementation in design workflows, branch/dirty-tree checks before edits, fresh verification before completion, and approval for destructive/remote git actions.

## Development completion contract

- Approval to implement includes staging and one local atomic commit of task-owned changes unless the user explicitly narrows that approval. Explicit `do not commit` instructions override this default.
- Initial implementation approval may preauthorize exact reversible local Git setup and cleanup: named task branches/worktrees and their post-integration removal. Tracked/config-controlled deletions included in that scope may be staged without another approval.
- Before staging, inspect the diff and status. Never stage unrelated pre-existing changes; if task-owned and unrelated changes cannot be separated safely, preserve the work and ask with exact paths.
- Stop instead of acting on ambiguous ownership, unrelated changes, untracked runtime data, backups, unknown/non-config-controlled data, active worktrees, remote refs, remote deletion, force/reset/clean, or history rewrite. These are outside reversible local authority.
- Deletion preview (not a second approval): before committing, show each exact staged deletion and its recovery source. Fail if any deleted path was not tracked at the recovery commit.

```bash
git status --short --untracked-files=all
recovery_sha=$(git rev-parse HEAD)
git diff --cached --name-status --diff-filter=D --no-renames
git diff --cached --name-only --diff-filter=D --no-renames -z |
  while IFS= read -r -d '' path; do
    git cat-file -e "$recovery_sha:$path" || exit 1
    printf '%s <- %s:%s\n' "$path" "$recovery_sha" "$path"
  done
```

- For preauthorized post-integration cleanup, take `worktree_path`, `branch`, and `integration_target` only from exact approved scope. Verify repository identity, path/branch association, task ownership, inactive ownership, clean status including untracked files, and integrated recovery SHA. Run the guarded non-force block as one unit; any mismatch or command refusal stops before later mutations. Preview precedes removal.

```bash
(
  set -euo pipefail
  : "${worktree_path:?approved worktree path is required}"
  : "${branch:?approved local branch is required}"
  : "${integration_target:?approved integration target is required}"
  test "$(git -C "$worktree_path" rev-parse --path-format=absolute --git-common-dir)" = \
    "$(git rev-parse --path-format=absolute --git-common-dir)"
  actual_branch=$(git -C "$worktree_path" symbolic-ref --quiet --short HEAD)
  test "$actual_branch" = "$branch"
  test -z "$(git -C "$worktree_path" status --short --untracked-files=all)"
  recovery_sha=$(git -C "$worktree_path" rev-parse HEAD)
  git merge-base --is-ancestor "$recovery_sha" "$integration_target"
  printf '%s %s <- %s\n' "$worktree_path" "$branch" "$recovery_sha"
  git worktree remove "$worktree_path"
  git branch -d "$branch"
)
```

- Initial implementation approval may preauthorize one exact local integration when it names target checkout/branch, expected target HEAD, and source commit SHA. Run only the guarded helper from that target checkout:

```bash
agnt work integrate \
  --target-branch "$target_branch" \
  --expected-head "$expected_head" \
  --source-sha "$source_sha"
```

- The helper takes a target-ref-scoped OS lock shared through Git's common directory, clears ambient `GIT_*` overrides, pins the approved worktree, disables hooks/signing/fsmonitor/signature enforcement, rejects command-bearing custom merge/filter/branch-options config, then rechecks branch, exact HEAD/source, and clean status before one local merge. Timeout, cancellation, target divergence, source mismatch, unsafe config, or dirty state stops without mutation. Conflict runs only `git merge --abort` and verifies exact clean baseline restoration; failed recovery stops. Do not attempt another merge, cherry-pick, rebase, reset, clean, or alternate integration strategy under the original approval.

## Deployment approval contract

Initial implementation approval may preauthorize deployment to verified local-live and explicitly designated test/staging environments. Approval must contain:

- **Action:** Bead ID, exact deployment command, source-selection rule restricted to that Bead's task-owned verified candidate commit/artifact, exact preview command/options, and approved expected-effect bounds.
- **Scope:** canonical environment identifier, class (`local-live`, `test`, or `staging`), resolved absolute destination, host, account, and user identity plus project/cluster/region/namespace as applicable, managed writes/deletions, and exclusions.
- **Consequences:** runtime/users affected and downstream operations triggered.
- **Reversibility:** known-good revision/artifact, preserved state or backup, exact rollback command, limits, and rollback verification. Destructive rollback is outside this authority.
- **Closeout:** required prechecks, dry-run or equivalent preview, post-deploy verification/health check, evidence location, and stop conditions.

Before mutation, independently read target identity from deployment tooling and compare every approved identity field. Local-live Pi config means canonical tracked `pi/` source to the approved resolved absolute destination after post-symlink resolution, on the approved host/account/user, without `PI_CONFIG_DEST_UNSAFE_OK`; a `$HOME/.pi` expression alone is mutable-only and insufficient. Test/staging must be explicitly classified in tracked project policy and have a stable unique identity. Production labels/signals override lower-risk labels. Missing, conflicting, mutable-only, or mismatched identity is unknown and fails closed.

Resolve the approved source-selection rule to one immutable candidate revision/artifact belonging only to the named Bead. Run documented repository checks and the exact preview command/options; capture dry-run or equivalent preview including managed deletions, then prove every effect is within approved expected-effect bounds. After deployment, run named health/smoke checks and compare desired revision/artifact with observed state. Retain preview, identity, verification, and rollback evidence. Failure, drift, broader deletion, unavailable rollback, secrets change, or changed Bead/command/source/destination stops; do not retry mutation or improvise rollback under original authority.

Production and unknown targets require a new explicit approval with elevated stakes; never batch them with local-live/test/staging. Deployment authority is single-use for one named environment and is consumed by the first mutation attempt; it expires unused when the Bead closes or approved scope changes. Rejection, cancellation, or timeout leaves deployment blocked. There is no deadline that permits automatic deployment and no proceed-by-default behavior; any modified or expired scope requires a new preview and approval.

## Ordinary push approval contract

Initial implementation approval may preauthorize one ordinary branch push after successful Bead closeout. Approval must bind the Bead, repository, canonical remote name and push URL, exact local and remote branch names, approved base commit SHA, candidate-selection rule limited to the task-owned implementation commit plus portable Beads closeout commit, expected remote ref state (absent or one commit SHA), final-gate commands, exclusions, and stop policy. Generic approval metadata, a remote name alone, or approval added after scope changed is insufficient.

Before pushing, require the task-owned commit, successful final gate after the last task change, successful direct closeout with committed portable Beads state, clean tracked state, and exact approved local branch. Resolve the selection rule to immutable push `HEAD`; its range after the approved base must contain only the task-owned implementation commit and portable closeout commit. Re-read the canonical push URL and remote ref without tags. The remote ref must still equal the approved absent/SHA state; an existing ref must also be an ancestor of push `HEAD`. Unknown remote ownership, branch protection, or production role fails closed. Push only the exact branch refspec normally, with no force, options that create tags, or extra refspecs. Verify the remote SHA equals push `HEAD` afterward.

This authority excludes protected or production branches, upstream PR creation, Ready state, reviewer requests, merge, tag, release, package publication, remote deletion, force, and history rewrite. Any dirty tracked state, failed final gate or closeout, identity mismatch, unexpected remote state, non-fast-forward result, changed scope, or ambiguous protection/production status stops and requires separate exact approval when the action may be delegated. Rejection, cancellation, or timeout leaves push blocked.

Immediately before invoking Git, atomically mark the exact approval consumed in durable authorization state with resolved push SHA and attempt ID. If the platform cannot prove an unused-to-consumed transition, stop; chat/session memory is insufficient. The first push mutation attempt consumes the authority, whether it succeeds, fails, or has an uncertain result. Stop with no automatic retry or rollback mutation. Public history is not fully reversible: retain local commits, report exact local and remote refs, and seek separate approval for a forward correction. Never use force, remote deletion, or history rewrite as automatic rollback.

- After verification, commit task-owned changes. Do not close the Bead or claim completion while task-owned changes remain uncommitted unless committing is explicitly prohibited or blocked; record that blocker and resumption path instead.
- For direct work, record `agnt improve outcome <id> <outcome>`, then run `agnt work direct-closeout <id> --reason "<reason>"`. This second local commit records shared portable Beads state separately: explicit export, target closeout parity, and all legitimate `.beads/issues.jsonl` rows. It refuses tracked non-Beads changes and never stages or commits them.
- Outside exact preauthorized setup, integration, cleanup, verified non-production deployment, and one ordinary post-closeout push, push, branch/worktree deletion, local merge, and deployment require explicit approval. Alternate merge strategies, protected/production pushes, production/unknown deployment, remote deletion, history rewrite, Beads deletion/remote/history changes, hooks, and force/reset/clean remain explicitly gated; direct closeout itself never pushes.

## Plan directory

Use the helper:

```bash
PLANS_DIR=$(~/.pi/agent/bin/agnt plans-dir)
```

Override with `PI_PLANS_DIR` when needed.

## Peer orchestration

For interactive work, keep policy in `agnt` and execution in Archimedes:

1. Run `~/.pi/agent/bin/agnt route --task <task> --risk <level> --budget <budget>`.
2. Call the `subagent` tool with `agent` omitted and the routed target as `model`.
3. Use one `tasks` array for independent parallel peers.
4. Persist returned outputs under `.pi/peer-runs/<topic>/` only when downstream work needs artifacts.

```json
{
  "tasks": [
    { "task": "<focused read-only prompt A>", "model": "<routed target A>", "cwd": "<repository>" },
    { "task": "<focused read-only prompt B>", "model": "<routed target B>", "cwd": "<repository>" }
  ]
}
```

Use `mode: "one-shot"` for cold complete packets and normal agentic mode for peers that need tools or project context. Default peer roles should come from curated task/model policy, not hard-coded Claude assumptions.

## Web research

Use backend-agnostic helpers:

```bash
~/.pi/agent/bin/agnt web-search "query"
~/.pi/agent/bin/agnt web-fetch URL
```

`agnt web-search` reports `cat: <category>` in its output. Cite only fetched/verified URLs.

## Skill adaptation rules

When porting older Claude Code skills to Pi:

- Replace `.claude/...` paths with `.pi/...` unless there is a project-specific reason not to.
- Replace platform-specific Task assumptions with routed unnamed `subagent` calls or explicit manual execution; use subagent `mode: "one-shot"` for cold packets.
- Do not assume native WebSearch/WebFetch, AskUserQuestion, TodoWrite, MCP, hooks, background bash, or plan mode.
- Prefer concise prompts and artifacts that can be found with `rg`.
