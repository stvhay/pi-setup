---
name: skill-creator
description: Use when creating a new Pi skill, updating an existing skill, testing skill behavior, improving a skill description, or deciding whether a workflow should become a reusable skill.
---

# Skill Creator

Create and improve Pi skills with test-driven process design. A skill is process documentation that changes agent behavior, so treat it like code: establish a failing or weak baseline, write the smallest useful skill change, then verify behavior improved.

Announce: "I'm using the skill-creator skill to design and test this skill change."

At start, read shared conventions if needed:

```text
~/.pi/agent/skills/dev-workflow-common/SKILL.md
```

## Core rule

No new skill or meaningful skill edit without a baseline scenario first.

Baseline scenario means a concrete prompt/task that shows what agents do without the skill or before the change. For small edits, a written expected-failure scenario may be enough; for discipline or workflow-gate skills, run a peer/model baseline when practical.

## When to create a skill

Create a skill when:

- the technique is reusable across projects
- agents will not reliably infer the process from normal instructions
- the workflow benefits from progressive disclosure
- future sessions need a named trigger and durable guidance

Do not create a skill for:

- one-off project facts; put those in `AGENTS.md` or project docs
- mechanical rules better enforced by scripts, tests, or linters
- long API references better stored as docs and fetched/read when needed
- behavior that has not been observed or pressure-tested

## Skill types

| Type | Purpose | Test approach |
|---|---|---|
| Discipline | Enforce a gate or habit under pressure | pressure prompts with shortcuts/temptations |
| Technique | Teach a method | representative application tasks |
| Pattern | Help recognize/choose an approach | trigger and non-trigger examples |
| Reference | Provide lookup guidance | retrieval plus application tasks |

## Workflow

### Step 1: Capture intent

Clarify in normal chat:

1. What should this skill help agents do?
2. When should it trigger?
3. What should not trigger it?
4. What artifacts or final output should it produce?
5. What failure have we seen, or what failure do we expect without it?

Prefer assumptions plus a concise confirmation question when the repository already provides enough context.

### Step 2: RED — establish baseline

Create at least one baseline scenario before editing.

For a new skill, write scenario files under:

```text
.pi/skill-evals/<skill-name>/scenarios/
```

Suggested scenario shape:

```markdown
# Scenario: <name>

## Prompt
<task prompt to give a model>

## Expected weak baseline
<what usually goes wrong without the skill>

## Expected with skill
<observable behavior that should improve>

## Assertions
- <specific thing output must/ must not do>
```

For stronger evidence, run without the skill context using a peer:

```bash
mkdir -p .pi/skill-evals/<skill-name>/baseline
~/.pi/agent/bin/agnt invoke provider/model < .pi/skill-evals/<skill-name>/scenarios/<scenario>.md > .pi/skill-evals/<skill-name>/baseline/<model>.md
```

Use model-diverse peers for important skills:

```bash
~/.pi/agent/bin/agnt invoke --fanout -o .pi/skill-evals/<skill-name>/baseline "<self-contained scenario prompt>"
```

Document exact failure patterns in the scenario or a short `README.md` in the eval directory.

### Step 3: GREEN — write the minimal skill

Create or edit:

```text
pi/agent/skills/<skill-name>/SKILL.md
```

Use this frontmatter:

```markdown
---
name: <letters-numbers-hyphens>
description: Use when <triggering conditions only>
---
```

Description rules:

- Start with `Use when`.
- Include trigger conditions only, not workflow steps.
- Keep it concise; descriptions that summarize the workflow can cause agents to skip reading the full skill.
- Include common user phrases when they improve recall.

Body rules:

- Put the most important gate or principle near the top.
- Prefer exact commands and paths.
- Use `~/.pi/agent/bin/*` helpers instead of embedding backend-specific orchestration.
- Reference `dev-workflow-common` for shared workflow conventions instead of duplicating them.
- Avoid project-specific facts unless the skill is intentionally project-local.
- Keep `SKILL.md` under about 500 lines; put bulky references in sibling files if needed.

Do not include Claude-only assumptions: native subagents, native web tools, hooks, MCP, Claude-specific prompt tools, or Claude-specific project files.

### Step 4: Verify GREEN

Run the same scenario with the skill available or with the candidate skill text included in the prompt:

```bash
mkdir -p .pi/skill-evals/<skill-name>/with-skill
~/.pi/agent/bin/agnt invoke provider/model "$(cat pi/agent/skills/<skill-name>/SKILL.md)

Scenario:
$(cat .pi/skill-evals/<skill-name>/scenarios/<scenario>.md)" \
  > .pi/skill-evals/<skill-name>/with-skill/<model>.md
```

Then check assertions manually or with a reviewer peer:

```bash
~/.pi/agent/bin/agnt invoke provider/model "Compare baseline and with-skill outputs against the scenario assertions. Return PASS/FAIL with evidence."
```

For simple skills, minimum verification can be filesystem/static checks plus one self-contained trigger/non-trigger review. For high-stakes workflow gates, require model-run evidence.

### Step 5: REFACTOR — close loopholes

When verification fails:

1. Identify the exact rationalization or missing instruction.
2. Add the smallest countermeasure.
3. Rerun the scenario.
4. Add a regression scenario if the failure is important.

Common loopholes:

| Failure | Countermeasure |
|---|---|
| Agent acts before approval | Add hard gate and explicit allowed/disallowed tools/actions. |
| Agent claims verification without evidence | Require command output or `NOT_VERIFIED`. |
| Agent follows description only | Shorten description to triggers only. |
| Agent over-applies the skill | Add non-trigger cases. |
| Agent edits files in planning mode | Define read-only discovery before approval. |

### Step 6: Optimize trigger description

After the body works, test description recall:

Create examples:

```text
.pi/skill-evals/<skill-name>/triggers/should-trigger.md
.pi/skill-evals/<skill-name>/triggers/should-not-trigger.md
```

Ask peers to classify which skill they would use from available skill descriptions. Improve the description only if recall or precision fails.

## Static validation

Run before completion:

```bash
test -f pi/agent/skills/<skill-name>/SKILL.md
rg -n '^---$|^name:|^description: Use when' pi/agent/skills/<skill-name>/SKILL.md
rg -n 'Claude-only|Claude-specific|legacy' pi/agent/skills/<skill-name>/SKILL.md || true
```

If adding helper commands or eval scripts, also run syntax checks.

## Report format

```markdown
## Skill Created/Updated

**Skill:** `<skill-name>`
**Path:** `pi/agent/skills/<skill-name>/SKILL.md`

### Baseline scenario
- `<path>` — <failure observed or expected>

### Verification
- `<command or peer run>` → PASS/FAIL/NOT_VERIFIED

### Trigger notes
- Should trigger: <examples>
- Should not trigger: <examples>

### Remaining gaps
- <none or follow-up>
```

## Integration

Pairs with:

- `brainstorming` — decide whether a reusable workflow should become a skill
- `writing-plans` — plan multi-file skill/helper changes
- `requesting-code-review` — review non-trivial skill changes
- `verification-before-completion` — verify before claiming complete
