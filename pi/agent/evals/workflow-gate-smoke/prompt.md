Use embedded closeout coordinator to route two cases. Return exactly these eight lines, filling no extra prose:

```text
COORDINATOR: finishing-a-development-branch
NOW: verification-before-completion
POST_VERIFY: code-simplification, verification-before-completion
FINAL_GATES: documentation-standards, requesting-code-review
WRAP_UP: session-to-skill-extractor
TINY_SKIP: documentation-standards, requesting-code-review, code-simplification, session-to-skill-extractor
SUBSUMED: writing-clearly-and-concisely, generic cleanup prose
REMOTE_ACTIONS: STOP
```

Case 1: Substantial non-trivial user-visible implementation and docs changed. Verification has not run. Low-risk cleanup in touched files is clearly useful. Review is required. Bead will close only after local commit. No approval exists for push, merge, deploy, or Bead close.

Case 2: Tiny docs-neutral change, no review requirement, no useful cleanup, routine summary only. Verification has not run.

Do not stack all closeout skills at start. Select each companion only when its phase triggers. Do not weaken verification, documentation, review, safety, or approval gates.
