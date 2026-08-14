---
name: skill-creator
description: Use when creating, updating, evaluating, or improving a Pi skill or its trigger description.
---

# Skill Creator

Create and improve Pi skills with an eval-first process. Skills change agent behavior; treat them like code: establish a weak baseline, make the smallest useful change, then rerun the same scenario.

Announce: "I'm using the skill-creator skill to design and test this skill change."

Read shared conventions when needed:

```text
~/.pi/agent/skills/dev-workflow-common/SKILL.md
```

## Hard gates

- No new skill or meaningful skill edit without a baseline scenario.
- Confirm ownership before editing. Change repository-owned skills directly; leave package-installed, generated, vendored, or external skills alone unless the user approves an upstream, fork, or overlay strategy.
- Preserve security, destructive-action, accessibility, data-loss, approval, and verification constraints.
- Before adding rules, inspect adjacent context layers for conflicting or duplicated guidance. Prefer deleting or consolidating instructions over adding precedence rules.
- Do not chase a vendor's context-reduction percentage. Reduce context only when behavior stays equal or improves.

## When a skill should exist

Create a skill when the method is reusable, agents will not reliably infer it, and on-demand loading is useful.

Do not create one for:

- one-off project facts; use `AGENTS.md` or project docs
- mechanical rules better enforced by code, tests, linters, or tool schemas
- long API/reference material that can be retrieved directly
- behavior without an observed or plausible failure

Keep each skill focused on one job. Split unrelated jobs rather than adding modes and exceptions.

## Progressive-disclosure model

Use the smallest layer that can carry the information:

1. **Description:** discovery only—triggers, common phrases, and important boundaries.
2. **`SKILL.md`:** decisions, workflow, invariants, failure handling, and retrieval pointers.
3. **`references/`:** theory, large tables, schemas, worked examples, rubrics, and detailed procedures.
4. **`scripts/` or tools:** deterministic validation, parsing, transformations, and repeatable actions.

Keep rich references when they reduce ambiguity. Code, tests, HTML mockups, schemas, rubrics, and edge-case examples are often stronger than more instructions.

## Interface before instruction

Before adding prose, ask whether the tool or file interface can express the behavior:

- enums instead of prose-defined states
- typed parameters instead of example-only conventions
- clear names and help text instead of repeated reminders
- validation errors that explain recovery
- one focused tool instead of several overlapping tools

Remove repetitive examples when an expressive interface replaces them. Keep examples that define a schema, edge case, safety boundary, or required output shape.

## Workflow

### 1. Define behavior and boundaries

Record:

- what agents should do
- positive triggers
- negative triggers
- expected artifact/output
- observed or expected weak behavior
- ownership: repository, package, vendor, or generated source

Prefer assumptions over unnecessary questions when repository evidence is clear.

### 2. RED — establish baseline

For an existing tracked skill, create the scenario before editing:

```text
.pi/skill-evals/<skill-name>/scenarios/<scenario>.md
```

For a new skill that is still an unapproved draft, keep the scenario, candidate,
and model output in ignored draft storage:

```text
.pi/reviews/skill-drafts/<skill-name>/evals/scenarios/<scenario>.md
```

Only after promotion is approved, move durable scenarios to
`.pi/skill-evals/<skill-name>/scenarios/` in the same task-owned commit. Do not
create new unapproved candidate skills or raw model output under
`.pi/skill-evals/`; preserve pre-existing evidence until its owner approves
relocation or deletion.

Use this compact shape:

```markdown
# Scenario: <name>

## Prompt
<representative task>

## Expected weak baseline
<observable failure>

## Expected with skill
<observable improvement>

## Assertions
- <must or must-not behavior>
```

A written baseline is enough for a small change. For high-stakes gates or uncertain behavior, run model-diverse peers and save outputs under `baseline/`.

### 3. GREEN — make minimum change

Use supported single-line frontmatter:

```markdown
---
name: <letters-numbers-hyphens>
description: Use when <triggering conditions and boundaries only>.
---
```

Description rules:

- Start with `Use when` unless the skill is a hidden helper.
- Front-load likely trigger terms.
- Include boundaries that prevent nearby skills from over-triggering.
- Do not summarize workflow; that encourages skipping `SKILL.md`.
- Keep it short enough for discovery budgets.
- Avoid folded/literal YAML; Pi's dependency-free parser supports simple single-line scalars.

Body rules:

- Put hard gates and core decisions near the top.
- Trust model judgment for local style choices; constrain only real invariants.
- Prefer exact paths, commands, and output contracts.
- Link bulky material instead of embedding it.
- Reference shared workflow conventions instead of repeating them.
- Avoid backend- or vendor-specific assumptions unless scope requires them.

### 4. Verify with same scenario

Run static checks first:

```bash
pi/agent/bin/agnt context-health --strict
.venv/bin/python -m pytest tests/test_context_architecture.py
```

For behavior evidence, run the original scenario with the candidate skill available. Compare against its assertions; do not substitute a new, easier prompt.

### Isolated loaded-skill check

For a self-contained no-tool scenario, run direct Pi JSON mode with only the candidate skill available and force-load its body:

```bash
pi --provider <provider> --model <model> --thinking <level> \
  --mode json --print --no-tools --no-skills --skill <skill-directory> \
  --no-extensions --no-context-files --no-prompt-templates --no-session \
  "/skill:<skill-name> <original scenario prompt>" > <events.jsonl>
```

Explicit `--skill` remains additive with `--no-skills`; `/skill:<skill-name>` force-loads the body and requires skill commands to be enabled. Do not use helper one-shot mode for this check because it disables skills.

Validate output and scenario assertions locally. Read usage only from assistant `message_end` events that contain usage: `input` is fresh input, `cacheRead` is reused input, and `output` is output. Count those events as model calls and `auto_retry_start` events as provider retries. Report `unavailable` for any requested field absent from the event stream. If the scenario needs tools, replace `--no-tools` with the smallest explicit `--tools` allowlist.

For important skills, test more than one model family. Newer models may need less prescription, while other models still benefit from explicit scope and output constraints.

### 5. Test trigger precision

Include both:

- prompts that should select the skill
- near-neighbor prompts that should not

Improve the description only when recall or precision fails. Avoid keyword stuffing: it consumes discovery context and increases collisions.

### 6. Refactor after green

- Remove duplicated instructions.
- Move bulky reference material out of `SKILL.md`.
- Replace prose with deterministic checks where practical.
- Re-run the same scenario and context-health checks.
- Remove any large-skill allowlist entry only after the top-level file fits the normal budget.

## Common failures

| Failure | Smallest correction |
|---|---|
| Agent acts before approval | Keep one explicit hard gate and allowed/disallowed actions. |
| Agent claims success without evidence | Require fresh command output or `NOT_VERIFIED`. |
| Agent follows description only | Shorten description to triggers. |
| Skill triggers too broadly | Add one clear boundary and negative scenario. |
| `SKILL.md` is large | Move reference material; keep decisions and invariants. |
| Examples constrain exploration | Replace repetitive examples with an expressive interface. |
| External skill needs improvement | Record evidence; choose upstream contribution, fork, or local overlay separately. |

## Completion report

```markdown
## Skill Created/Updated

**Skill:** `<name>`
**Owned source:** `<path or package>`
**Baseline:** `<scenario>` — <observed/expected weakness>
**Verification:** `<command or peer run>` → PASS/FAIL/NOT_VERIFIED
**Trigger notes:** should trigger <cases>; should not trigger <cases>
**Remaining gaps:** <none or follow-up>
```

Pairs with `brainstorming`, `writing-plans`, `requesting-code-review`, and `verification-before-completion`.
