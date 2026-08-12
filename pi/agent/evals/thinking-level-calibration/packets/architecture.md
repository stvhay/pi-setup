Return JSON only: `{"schemaVersion":1,"caseId":"architecture","result":"PASS|FAIL","findings":["ID"],"completed":true}`.

Architecture contract: billing admission and dispatch must use one shared policy function so every caller enforces identical limits.

Design:
- CLI route calls `admit_metered()` before dispatch.
- Background runner duplicates price checks locally and dispatches directly.
- Both currently use same constants.

Assess contract. Use finding `A1` only if design violates it.
