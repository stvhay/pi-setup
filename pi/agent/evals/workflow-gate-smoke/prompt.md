Use embedded closeout coordinator to route two scenarios from their facts. Return exactly these lines, replacing angle-bracket placeholders with decisions and adding no prose:

```text
CLEAN_COORDINATOR: <coordinator-skill-id>
CLEAN_INITIAL_VERIFY: <verification-skill-id>
CLEAN_LOAD: <optional-skill-ids-or-none>
CLEAN_SKIP: <optional-skill-ids-or-none>
CLEAN_RERUN_VERIFY: <fix-sources-or-none>
CHANGED_COORDINATOR: <coordinator-skill-id>
CHANGED_INITIAL_VERIFY: <verification-skill-id>
CHANGED_LOAD: <optional-skill-ids-or-none>
CHANGED_SKIP: <optional-skill-ids-or-none>
CHANGED_RERUN_VERIFY: <fix-sources-or-none>
REMOTE_ACTIONS: <STOP-or-ALLOW>
```

Use exact skill IDs. For `LOAD` and `SKIP`, list optional skills in matrix order and use `none` when empty. For `RERUN_VERIFY`, list applicable fix sources in matrix order (`simplification`, `review`, `documentation`) or use `none`. Use `STOP` when remote actions lack approval and `ALLOW` only when approved.

`CLEAN`: Working tree is clean after a tiny internal, documentation-neutral, low-risk change. Initial verification has not run. No review is required, no useful simplification exists, summary is routine, and Bead remains open. No later phase will change files.

`CHANGED`: User-visible, risky code and documentation changed. Initial verification has not run. Documentation validation and code review are required; each produces a tracked-file fix. No useful simplification exists, summary is routine, and Bead remains open.

No approval exists for push, merge, deploy, branch deletion, worktree removal, or Bead close.

Do not stack all closeout skills at start. Select each companion only when its phase triggers. Do not weaken verification, documentation, review, safety, or approval gates.
