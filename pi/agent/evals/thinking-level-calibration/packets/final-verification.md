Return JSON only: `{"schemaVersion":1,"caseId":"final-verification","result":"PASS|FAIL","findings":["ID"],"completed":true}`.

Release requires unit tests and routing smoke to pass. Evidence:

```
pytest tests/test_routing.py: 42 passed
agnt eval run routing-smoke: case repository-access FAILED (exit 1)
ruff: passed
```

Decide release gate. Use finding `V1` only when required verification failed.
