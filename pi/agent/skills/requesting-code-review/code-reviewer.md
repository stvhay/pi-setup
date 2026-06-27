# Pi Code Reviewer Prompt

The shared role package is the source of truth for reviewer stance and output contract:

```bash
agnt instructions --role code-reviewer --context provider/model
```

When constructing a concrete review prompt, append only task-specific context:

```text
Repository: <repo path>
Scope: <working tree diff | PR #N | commit range>
Requirement/plan: <short requirement or path to plan/design>
Diff artifacts:
- <path/to/diffstat.txt>
- <path/to/diff.patch>
```

Keep process orchestration in `requesting-code-review/SKILL.md`; keep reviewer persona/output details in `AGENTS.d/roles/code-reviewer.md`.
