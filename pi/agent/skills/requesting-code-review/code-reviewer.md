# Pi Code Review Packet Template

For ordinary interactive review, generate the shared role package:

```bash
agnt instructions --role code-reviewer --context provider/model
```

For cost-bounded cold discovery, use the compact `finding-discoverer` role and tracked JSON schema instead of the full layered context package:

```text
Review ID: <id>
Scope: behavioral | boundary
Reviewer target: <provider/model>
Reviewer family: <family>
Requirement: <embedded requirement/design excerpt>
Changed behavior: <concise neutral description>
Relevant diff: <embedded diff hunks>
Callers/dependents: <embedded source or graph evidence>
Relevant tests/results: <embedded test source and command output>
Output contract: review-findings.schema.json; status unverified
```

A one-shot peer cannot read artifact paths. Embed the needed contents, keep each packet behavior-focused, and exclude secrets and unrelated proprietary context.

Keep process orchestration in `requesting-code-review/SKILL.md`; keep role behavior in `AGENTS.d/roles/finding-discoverer.md` and `AGENTS.d/roles/finding-verifier.md`.
