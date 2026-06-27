# Available CLI tools

## Code search

- **`rg PATTERN [PATH]`** — ripgrep, regex search across files. Fast.
- **`ast-grep --pattern '<code>' --lang <lang>`** — structural / AST search.

## Image generation

- **`nanobanana [--help] -o OUT.png -a [ASPECT] [-s SIZE] [-m MODEL] <prompt>`**
  - preselected model alias: **`nanobanana-2`** (cheaper), **`nanobanana-pro`** (default)
  - Requires `GEMINI_API_KEY` in env.

# Agent helper convention

Use `~/.pi/agent/bin/agnt` as the primary helper interface:

```bash
agnt [command [args]] [subcommand ...] [filename]
```

When practical, commands read stdin if no filename is supplied, write primary results to stdout, write diagnostics to stderr, and use `-o` for output files/directories.

## Common commands

- List tasks: `agnt tasks`
- List task/model routing: `agnt tasks --models`
- Web search: `agnt web-search "query"`
- Web fetch: `agnt web-fetch URL`
- Query/build code knowledge graphs: `agnt graphify ...`
- List models for a task: `agnt invoke --list [TASK]`
- Recommend a model for constraints: `agnt route --task TASK --risk medium --budget balanced`
- Invoke one peer: `agnt invoke [--task TASK] provider/model [filename]`
- Fan out peers: `agnt invoke --fanout [-o DIR] provider/model [filename]`
- Generate layered role/model instructions: `agnt instructions --context provider/model --role ROLE`
- Run evals: `agnt eval list` and `agnt eval run EVAL_ID --dry-run`
- Inventory prompts: `agnt prompt inventory`
- List/validate action templates: `agnt action list` and `agnt action validate`
- Create/validate run artifacts: `agnt runs create` and `agnt runs validate`
- Inspect beads-backed work: `agnt work next --json` and `agnt work plan --dry-run`
- Emit communication preferences: `agnt soul`
- Resolve plans dir: `agnt plans-dir`

Use `agnt -h` and `agnt COMMAND -h` for current syntax.

# Orchestration

Delegate difficult tasks to stronger models, easy tasks to cheaper models, and independent critique/review to diverse peers. Prefer local or low-cost models when they are fast enough. Verify peer output against files, tests, and primary sources before acting.

Escalation order:

1. Increase the current orchestrator's thinking level.
2. Delegate read-only analysis to one stronger specialist.
3. Fan out diverse cheap peers for critique.
4. Switch the primary orchestrator only for sustained high-stakes work.

Cost policy: OpenAI/Codex models benefit from the active subscription/discount and should be preferred when capability is comparable. Anthropic is still available when needed, but treat Claude usage as retail-priced extra usage rather than subscription-backed capacity.

For strict workflow orchestration with gates—approval before edits, planning without implementation, verification before completion, PR/merge readiness—prefer models listed under:

```bash
agnt invoke --list orchestration
```

Use scriptable routing instead of embedding a static model matrix in instructions:

```bash
agnt route --task orchestration --risk high --budget quality
agnt tasks --models
```

# Work, tasks, skills, prompts, roles, and tools

Keep these concepts separate:

- A **work item** (often a bead when the project has `.beads/`) is durable task/dependency state: what is ready, blocked, or complete.
- A **task** is an operational routing label for model/tool defaults, such as `review`, `research`, `planning`, or `orchestration`.
- A **prompt/action template** intentionally starts an action and may select a task, skills, roles, tools, and output contract.
- A **skill** is a reusable capability package: workflow, method, expertise, references, helper tools, or any mix of those.
- A **role** is a concise delegated-peer stance/output contract generated with `agnt instructions --role ROLE --context provider/model`.
- A **tool** is deterministic behavior; prefer tools/evals over prose for repeatable routing, validation, data extraction, and context generation.

Tasks answer “what model/tool default should I use?” Skills answer “what method/capability should I load?” Roles answer “how should this peer behave and report?” Work should produce durable artifacts when downstream agents, tools, or humans need to inspect or continue it. Task routing, prompts, and roles do not replace skill instructions or project safety gates.

When a project has `.beads/`, treat Beads as the agent-facing work graph: use `bd prime` for current workflow context, `bd ready` to find unblocked work, and `bd show <id>` to inspect work. Do not delete beads, rewrite Beads/Dolt history, change Beads remotes, or install Beads hooks without explicit approval.

# Research

Do not assume model-native browsing. For cited external claims, search first, fetch/verify URLs, then cite only verified pages:

```bash
agnt web-search "query"
agnt web-fetch URL
```

# Development workflow conventions

- Prefer filesystem artifacts over chat-only state. Keep designs/plans in project-local `.pi/plans/` unless instructed otherwise.
- Use `agnt plans-dir` to resolve/create the plans directory.
- Use `rg`, `find`, `git grep`, `git diff`, and exact file paths to retrieve context instead of bloating prompts.
- If `graphify-out/graph.json` exists and the task asks about architecture, code concepts, dependencies, data flow, or cross-file relationships, probe it first with short keyword queries — `agnt graphify query "<keyword>"`, `agnt graphify explain "<symbol>"` — then verify important claims against source files. Matching is lexical: use identifiers/keywords, not sentence-form questions.
- Shared workflow conventions live in the hidden skill `~/.pi/agent/skills/dev-workflow-common/SKILL.md`.

# Context package convention

Use compact layered instruction packages instead of bloating skills or base `AGENTS.md` files.

- Root files: `AGENTS.md`, `AGENT.md`, `SKILL.md`, or `SOUL.md`.
- Supplements live beside the root under `<root-stem>.d/`, for example `AGENTS.d/`, `SKILL.d/`, or `SOUL.d/`.
- Model files live in `<root-stem>.d/models/`. Prefer family-keyed files (`AGENTS.d/models/<family>.md`, families defined in `agent/catalog.json`) so one overlay applies to every venue of the same weights; slash-style provider/model paths (for example `AGENTS.d/models/openrouter-localish/google/gemma-4-31b-it.md`) refine a family overlay for one venue.
- Role files live in `<root-stem>.d/roles/` and may include short frontmatter: `id`, `summary`, `task`, `writeAccess`, `preferred`, `qualified`, `disallowed`.
- Generate layered global + project role context with `agnt instructions --context provider/model --role role`.
- List available roles with `agnt instructions --roles`.
- Use append-only concatenation for now; avoid patch/diff overlays unless a future named-section mechanism is designed.

Supplemental context may specialize model/role behavior, but must not weaken project safety gates. `SOUL.md` captures communication preferences only and must not override approval, verification, git, security, or project instructions.
