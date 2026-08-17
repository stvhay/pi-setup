---
name: dispatching-parallel-agents
description: Use for parallel, independent, read-only Pi investigations or reviews.
---

# Dispatching Parallel Agents

Use Pi peers to investigate independent domains concurrently. This skill is read-only/advisory by default. For implementation with writes, use `subagent-driven-development` Mode B with isolated worktrees.

Announce: "I'm using the dispatching-parallel-agents skill to coordinate read-only parallel peer analysis."

At start, read shared conventions if needed:

```text
~/.pi/agent/skills/dev-workflow-common/SKILL.md
```

## Core rule

Parallel peers may share a checkout only for read-only work. Do not allow parallel writes in one worktree. If the task requires edits, route to `subagent-driven-development` worktree mode or execute serially.

Every peer prompt follows the shared evidence-complete packet contract. Agentic peers retrieve primary evidence from exact filesystem paths and commands instead of receiving pasted source.

## Use when

- multiple failing test files appear independent
- multiple subsystems need separate investigation
- several design alternatives need parallel critique
- code review can be split by subsystem
- each domain can be understood with focused context

## Do not use when

- failures are likely related
- one fix may affect all domains
- domains modify the same files
- investigation needs global system context
- peers need to edit files in the current checkout
- external mutable state would be shared

## Shared environment check

Before dispatch, ask whether domains share mutable resources outside git:

- databases or local service state
- `/tmp` files, sockets, ports, queues, caches, or logs
- credentials, cloud resources, external APIs, or rate-limited services
- generated artifacts outside the repository

If shared mutable state exists, do not parallelize until each peer has an isolated environment or the user approves a specific coordination plan.

## Process

### 1. Inspect and group domains

Use filesystem-first inspection:

```bash
git status --short
git diff --stat
find . -maxdepth 3 -type f | sort | head -200
rg -n "FAIL|ERROR|TODO|FIXME|panic|exception" . 2>/dev/null | head -200
```

Group work by independent problem domain:

```markdown
## Domain grouping

| Domain | Evidence | Scope | Independent? |
|---|---|---|---|
| <name> | <files/tests/errors> | <paths> | yes/no |
```

If independence is unclear, do one serial investigation first.

### 2. Create focused peer prompts

Each prompt must keep every labeled template field. Write `unknown` rather than omit a field whose value is unavailable.

- objective and current decision
- exact source-of-truth paths, symbols, and commands
- external contract evidence the worker cannot retrieve
- constraints and read-only scope
- output schema or exact output shape
- verification target and stop conditions

Prompt template:

```text
You are a read-only peer investigator.

Objective: <decision this investigation supports>
Current decision: <accepted state or unresolved choice>
Evidence sources:
- Repository: <path>
- Exact paths/symbols/commands: <retrieval manifest>
- External contract evidence: <bounded evidence unavailable to worker, or none>
Constraints:
- Do not edit files.
- Do not commit.
- Do not run destructive commands.
- Prefer exact file:line evidence.
- If you propose a fix, describe it as text or a patch sketch only.
Output schema:
### Findings
### Evidence
### Proposed fix or next diagnostic step
### Confidence: HIGH | MEDIUM | LOW
Verification target: <test, command, invariant, or decision evidence>
Stop conditions: <evidence boundary, blocker, or completion condition>
```

### 3. Dispatch peers

Route first:

```bash
~/.pi/agent/bin/agnt route --task research --risk medium --budget balanced
```

Use the selected target—or distinct qualified targets from `candidateOrder` when diversity matters—in one `subagent` call. Omit `agent`; named profiles are optional and must not be assumed.

```json
{
  "tasks": [
    { "task": "<domain A read-only prompt>", "model": "<routed target A>", "cwd": "<repository>" },
    { "task": "<domain B read-only prompt>", "model": "<routed target B>", "cwd": "<repository>" }
  ]
}
```

Do not paste large diffs into prompts. Point peers at repository paths. After completion, write returned outputs under `.pi/peer-runs/<topic>/` only when synthesis or handoff needs durable artifacts.

### 4. Synthesize and verify

After peers finish:

1. Read all peer outputs.
2. Deduplicate findings.
3. Verify concrete claims against files/tests.
4. Discard hallucinated or unsupported claims.
5. Decide next action: manual fix, serial execution, worktree implementation, more diagnostics, or no-op.

Synthesis format:

```markdown
ADVISORY_DISPATCH

**Peer outputs:** `.pi/peer-runs/<topic>/`

### Verified findings
- <finding> — `file:line` — <evidence>

### Proposed fixes
- <fix and risk>

### Discarded / unverified
- <claim> — discarded because <reason>

### Next step
- <recommended action>
```

## Common mistakes

- Too broad: "fix all tests". Use one domain per peer.
- No context: include failing test names, paths, or relevant errors.
- Hidden coupling: if domains touch the same production file, investigate serially or use worktrees for implementation.
- Trusting peers: peer output is a lead, not proof.
- Letting read-only peer work become implementation without approval.

## Escalation to implementation

If advisory analysis identifies independent implementation tasks, use `subagent-driven-development`:

- Mode A if peers should only propose patches.
- Mode B if true parallel implementation is approved and per-task worktrees are appropriate.

Do not perform parallel writes from this skill.
