---
name: dispatching-parallel-agents
description: Use when facing multiple independent investigation or review domains that can be handled by read-only Pi peers in parallel.
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

Each prompt should include:

- exact scope
- relevant files/commands
- read-only constraint
- expected output
- severity or confidence format if useful

Prompt template:

```text
You are a read-only peer investigator.

Scope: <one test file/subsystem/problem domain>
Repository: <path>
Relevant files/commands:
- <paths>

Rules:
- Do not edit files.
- Do not commit.
- Do not run destructive commands.
- Prefer exact file:line evidence.
- If you propose a fix, describe it as text or a patch sketch only.

Output:
### Findings
### Evidence
### Proposed fix or next diagnostic step
### Confidence: HIGH | MEDIUM | LOW
```

### 3. Dispatch peers

Use `agnt invoke` for one focused peer or `agnt invoke --fanout` for model diversity.

Examples:

```bash
mkdir -p .pi/peer-runs/<topic>
~/.pi/agent/bin/agnt invoke olla-local/qwen3:8b "<prompt>" > .pi/peer-runs/<topic>/domain-a-qwen.md &
~/.pi/agent/bin/agnt invoke olla-local/gemma4:e4b "<prompt>" > .pi/peer-runs/<topic>/domain-b-gemma.md &
wait
```

```bash
printf '%s\n' "<shared review prompt>" > .pi/peer-runs/<topic>/prompt.md
~/.pi/agent/bin/agnt invoke --fanout -o .pi/peer-runs/<topic> olla-cloud/gpt-4.1-mini .pi/peer-runs/<topic>/prompt.md
```

Do not paste large diffs into chat. Write artifacts under `.pi/peer-runs/<topic>/` and point peers at paths.

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
