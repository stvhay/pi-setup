---
name: codify-subsystem
description: Use when a subsystem directory or high-value module needs a SPEC.md that captures purpose, interfaces, invariants, failure modes, and testing guidance for future agent work.
---

# Codify Subsystem

Create or update a `SPEC.md` for a subsystem. A subsystem can be a directory that groups related files or a single high-value module that is frequently modified.

Announce: "I'm using the codify-subsystem skill to create a specification for <target>."

At start, read shared conventions if needed:

```text
~/.pi/agent/skills/dev-workflow-common/SKILL.md
```

## Core principles

- Analyze code before asking questions.
- Batch independent questions in normal chat.
- Prefer durable spec indexes in `docs/specs/MANIFEST.md`.
- Update `AGENTS.md` only when project-wide agent instructions or required loading rules change.
- Do not refactor code, move modules, or rename tests unless explicitly approved.
- Specs are load-bearing artifacts and should be version-controlled.

## Target types

### Directory target

Example: `src/fetcher/` creates or updates:

```text
src/fetcher/SPEC.md
```

### File target

Example: `src/store.py` usually creates a sibling file-scoped spec:

```text
src/store.SPEC.md
```

If the module is clearly outgrowing one file, propose a promoted directory design, but do not move files without explicit approval.

## Step 1: Identify and inspect target

If no target is provided, ask which directory or file to codify.

Verify the path:

```bash
test -e <target>
find <target> -maxdepth 2 -type f | sort  # for directory targets
```

For a file target, also look for nearby tests and imports:

```bash
rg -n "<module-name>|from <package>|import <module>" . 2>/dev/null || true
```

## Step 2: Check existing specs

Walk upward from the target to find an existing governing spec:

```bash
dir="<target-directory>"
while [ "$dir" != "." ] && [ "$dir" != "/" ]; do
  if [ -f "$dir/SPEC.md" ]; then
    echo "Found SPEC.md at $dir/SPEC.md"
    break
  fi
  dir=$(dirname "$dir")
done
```

If a parent spec exists, ask whether to create a more specific spec or update the parent.

## Step 3: Analyze code

Read the target source and relevant tests. Identify:

- purpose and problem solved
- entry points and public API
- data/control flow
- internal conventions
- dependencies and neighboring specs
- existing tests and gaps
- likely invariants and known failure modes

Use filesystem-first commands:

```bash
rg -n "class |def |function |export |interface |type |TODO|FIXME" <target> 2>/dev/null || true
find . -path '*SPEC.md' -print | sort
rg -n "<target-name>" test tests src lib 2>/dev/null || true
```

## Step 4: Draft from evidence

Draft the spec from code analysis alone. Mark uncertainty with `[NEEDS INPUT]`. Do not write the final file yet unless the user already approved writing.

Template:

````markdown
# <Subsystem Name>

## Purpose

<What this subsystem does and why it exists.>

## Core Mechanism

<The mental model and key design choices needed to modify this subsystem safely.>

**Key files:**
- `path` — <role>

## Public Interface

| Export/API | Used By | Contract |
|---|---|---|
| | | |

## Invariants

| ID | Invariant | Enforcement | Why It Matters |
|---|---|---|---|
| INV-1 | | structural / reasoning-required / operational | |

## Failure Modes

| ID | Symptom | Cause | Fix |
|---|---|---|---|
| FAIL-1 | | | |

## Decision Framework

| Situation | Action | Spec Item |
|---|---|---|
| | | INV-N / FAIL-N |

## Testing

**Traceability:** Test names or inline comments should identify covered spec items, for example `test_inv1_description` or `# Tests INV-1`.

| Spec Item | Verification | Notes |
|---|---|---|
| INV-1 | `command` / structural / review / operational | |

## Dependencies

| Dependency | Type | Spec Path |
|---|---|---|
| | internal / external | |
````

## Step 5: Interview developer

Ask batched questions only after presenting the evidence-based draft.

Batch 1, independent:

- What must always be true for this subsystem?
- What known failure modes or symptoms have you seen?
- What command verifies this subsystem?
- What purpose or design history is not obvious from the code?

Batch 2, after invariants/testing are known:

- Which invariants are structural, reasoning-required, or operational?
- Which existing tests cover which invariant or failure mode?
- Which spec items are intentionally verified outside tests?

Batch 3, only for reasoning-required items:

- What situation-action recipe should future agents follow?

## Step 6: Finalize and write

After user answers or approves the draft:

1. Write or update the target spec.
2. Keep it concise; if it exceeds about 350 lines, recommend splitting.
3. Add `# Tests INV-N` / `# Tests FAIL-N` comments to existing tests only if approved or clearly in scope.
4. Record untested or operational items in the Testing section instead of hiding gaps.
5. Create or update `docs/specs/MANIFEST.md` with an index entry.
6. Update `AGENTS.md` only if agents must always load the spec or follow new project-wide instructions.

Manifest shape:

```markdown
# Subsystem Specifications

## Index

| Subsystem | SPEC.md Path | Summary |
|---|---|---|
| <name> | `<path>` | <one-line summary> |
```

## Verification

Run focused checks:

```bash
test -f <spec-path>
rg -n "^## Purpose|^## Public Interface|^## Invariants|^## Failure Modes|^## Testing" <spec-path>
test -f docs/specs/MANIFEST.md && rg -n "<spec-path>|<subsystem>" docs/specs/MANIFEST.md
```

If tests or typechecks are documented for the subsystem, run them too.

## Report format

```markdown
## SPEC Created/Updated

**Target:** `<target>`
**Spec:** `<spec-path>`
**Manifest:** `<manifest status>`

### Key invariants
- INV-1 — <summary>

### Known gaps
- <missing tests, uncertain failure modes, or none>

### Verification
- `<command>` → PASS/FAIL/NOT_VERIFIED
```

## Integration

Related skills:

- `writing-plans` — include relevant specs in task context
- `executing-plans` — load nearest specs before modifying code
- `subagent-driven-development` — provide specs to implementation workers
- `verification-before-completion` — check changed code against spec invariants
- `documentation-standards` — validate docs impacted by spec or public behavior changes
