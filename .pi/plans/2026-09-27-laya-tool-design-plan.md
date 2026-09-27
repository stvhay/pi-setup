# Laya tool design and implementation plan

Issue: pi-x59h
Branch: feat/laya-tool
Design: user-approved explicit local HTTP adapter; no deployment.

## Boundary

Add `pi/agent/extensions/laya.ts`: one `laya_predict` tool, fixed loopback endpoint `http://127.0.0.1:8001/v1/systemone`, explicit English checkpoint. Text state and typed questions only. Use native fetch, no redirects, 30-second deadline including response consumption, caller cancellation, byte-bounded input/output, validated answers. No process startup, download, retries, cloud fallback, routing-policy changes, or permission decisions. Local server is trusted to run offline; client does not configure server runtime. Scores and probabilities are advisory, not verified calibration.

## Steps

1. Add focused loader-based tests in `tests/test_laya.py`, confirm red for missing tool.
2. Implement schema and bounded transport; test success for all types, invalid inputs/results, HTTP failures/redirect refusal, timeout/cancellation and stream limits.
3. Document installation/startup, endpoint, limits, privacy and failure behavior in `pi/README.md`; add compatibility matrix entry.
4. Run focused and repository checks; independent review; commit task-owned files and close Bead. Preserve unrelated telemetry plan. No deployment/merge/push.

## Verification

```bash
.venv/bin/python -m pytest tests/test_laya.py -q
scripts/check-pi-config.sh
bash -n scripts/*.sh
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
.venv/bin/python -m pytest tests/ --durations=15
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
```

Use test transport stubs for deterministic CI (no weights, model, port, or network required). Run one explicit real-local adapter smoke when available, not as an automated CI dependency.
