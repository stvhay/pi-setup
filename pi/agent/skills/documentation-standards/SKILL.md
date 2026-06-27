---
name: documentation-standards
description: Use to draft or validate project documentation updates after design or implementation changes. Checks README, docs/ARCHITECTURE.md, docs/DESIGN.md, SPEC.md, and project-declared tracked docs using filesystem-first inspection.
---

# Documentation Standards

Keep project documentation aligned with actual design and code. Use shell tools and exact paths; do not paste large docs into context unless needed.

At start, read shared conventions if needed:

```text
~/.pi/agent/skills/dev-workflow-common/SKILL.md
```

Reference material, if useful:

- `references/project-docs.md`
- `references/adr-guide.md`

## Modes

- **Draft mode:** after a design is approved, identify docs that will need updates and draft concise sections.
- **Validate mode:** after implementation/verification, check whether docs are current with the diff.

If mode is not specified, infer it:

- design/plan discussion with no implementation diff → draft
- working-tree/branch diff exists → validate
- user/task explicitly asks to write documentation → implement docs, then validate

## Discover tracked docs

Prefer project-declared tracked docs when present. Search common context files:

```bash
rg -n "Tracked Documentation|ARCHITECTURE|DESIGN|SPEC.md|README" AGENTS.md CLAUDE.md README.md docs .pi 2>/dev/null || true
find . -maxdepth 4 \( -name README.md -o -name SPEC.md -o -path './docs/*.md' -o -path './.pi/plans/*.md' \) | sort
```

Default tracked docs:

- `README.md`
- `docs/ARCHITECTURE.md` if present
- `docs/DESIGN.md` if present
- nearest relevant `SPEC.md` files for modified subsystems
- relevant `.pi/plans/*-design.md` / `*-plan.md` files as source artifacts, not necessarily committed docs

## Detect changed scope

For validate mode:

```bash
git status --short
git diff --stat
git diff --name-only
```

If reviewing a branch range, identify base carefully:

```bash
base=$(git merge-base HEAD origin/main 2>/dev/null || git merge-base HEAD main 2>/dev/null || git merge-base HEAD master 2>/dev/null || true)
if [ -n "$base" ]; then git diff --stat "$base"...HEAD; git diff --name-only "$base"...HEAD; fi
```

## What counts as documentation impact

| Change | Expected docs |
|---|---|
| Public interface / user behavior | `README.md` or user docs |
| Architectural decision | `docs/ARCHITECTURE.md` or ADR |
| New design pattern / convention | `docs/DESIGN.md` |
| Subsystem invariant / failure mode / interface | nearest `SPEC.md` |
| New subsystem | recommend creating `SPEC.md` |
| Test/quality workflow change | `CONTRIBUTING.md`, README, or project docs |

Usually no docs needed for:

- tiny bug fix with no behavior/API change
- pure refactor with no externally visible behavior change
- dependency bump with no setup/compatibility impact
- test-only change that does not alter workflow or guarantees

## Draft mode process

1. Read the approved design/plan or user-provided requirements.
2. Discover tracked docs.
3. Identify expected documentation impact.
4. Draft minimal updates with exact target files.
5. Stop for user approval; do not edit docs unless explicitly asked.

Draft output:

```markdown
## Documentation Updates

### Required
- `path/to/doc.md` — <why update is needed>

### Draft text

#### `path/to/doc.md`

<concise proposed section>

### Deferred / not needed
- `path` — <reason>
```

## Validate mode process

1. Inspect diff and changed files.
2. Discover tracked docs.
3. Compare changes against docs.
4. Verify gaps with exact paths and, where possible, line references.
5. Produce PASS / NEEDS_DOCS / NOT_SURE.
6. If docs need changes, draft minimal updates. Do not apply them unless the user asks.

Validate output:

```markdown
## Documentation Validation

**Scope:** <working tree | branch range | PR>
**Verdict:** PASS | NEEDS_DOCS | NOT_SURE

### Checked
- `README.md` — current / gap / absent but not needed
- `docs/ARCHITECTURE.md` — current / gap / absent but not needed
- `docs/DESIGN.md` — current / gap / absent but not needed
- `path/SPEC.md` — current / gap / absent but recommended

### Gaps
- `path` — <missing or stale information> — evidence from diff/code

### Draft updates
<only if gaps exist>

### Deferrals
- <item> — <reason, if user explicitly deferred>
```

## ADR-style decision snippet

For architecture/design decisions, use a compact ADR shape:

```markdown
### <Decision title>

In the context of <situation>, facing <forces/trade-off>, we decided <decision> to achieve <goal>, accepting <consequence>.

- **Context:** <facts>
- **Decision:** <choice>
- **Consequences:** <trade-offs>
```

## Rules

- Do not make documentation a dumping ground for implementation minutiae.
- Prefer links/paths to detailed duplication.
- Do not require docs for every tiny change.
- Do not edit docs in draft/validate mode unless the user explicitly asks. If the requested deliverable is documentation itself, edits are allowed after normal approval/implementation gates and must be followed by validation.
- If uncertain, report `NOT_SURE` with the specific missing context.
- Use `web-search` only for external docs/background; project documentation validation should primarily use local files and diffs.
