Return JSON only: `{"schemaVersion":1,"caseId":"security","result":"PASS|FAIL","findings":["ID"],"completed":true}`.

Handler receives untrusted `name` and serves files:

```python
def serve(root, name):
    path = root / name
    if path.exists():
        return path.read_bytes()
    raise FileNotFoundError(name)
```

Assess security. Use finding `S1` only for path traversal outside root.
