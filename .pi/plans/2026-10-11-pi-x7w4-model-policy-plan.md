# October model policy alignment

**Bead:** pi-x7w4
**Decision:** Owner selected completing October upgrades, not reverting settings.
**Goal:** Restore coherent enabled models, catalog facts, overrides and task routing without weakening authorization/circuit guards.

## Evidence and boundary

- Five named failures reproduced before edits (5 failed in 0.23s).
- Commit 776f79eadc13d1ea628032573bebf7427b98376c changed only enabledModels: Sol 5.6 → 6.1, Luna 5.6 → 6, Opus 5 → 5.5. Old task candidates are rejected as disabled before budget/circuit checks. Luna fallback also affected.
- Metadata read offline from installed Pi 1.1.0, `node_modules/@earendil-works/pi-ai/dist/providers/{openai-codex,openrouter}.models.js` under `/Users/hays/.local/lib/node_modules/@earendil-works/pi-coding-agent/` (generated local catalog, no network/model calls).
- Sol 6.1 and Luna 6: subscription, 272000 context, text/image, native low/medium/high/xhigh/max; minimal maps to low. Sol off unsupported; Luna off maps to none. Do not retain old audio capability.
- Opus 5.5: metered, 1000000 context, text/image; off/minimal unsupported; low/medium/high/xhigh/max native; rates per million input 4, output 20, cacheRead .2, cacheWrite 5.
- Luna 6 OpenRouter opportunity rates: input .1, output .5, cacheRead .01, cacheWrite .125. Local OpenRouter catalog also has tiers above 272000; Codex route stays capped at 272000, so use base opportunity rates only. No OpenRouter Luna venue added.
- Astra startup/effort matrix, Terra challenger, spend caps, circuit precedence and fresh-worker constraints unchanged. No routing algorithm change.

## Files and steps

1. Update current-policy tests in `tests/test_agnt.py`, `test_model_config.py`, `test_catalog.py`, `test_pi_packages.py`; add task/settings/catalog/override/worker consistency regression and explicit upgraded metadata assertions. Observe RED before config edits.
2. Migrate `pi/agent/catalog.json`, `models.json`, memory worker in `settings.json`, all seven `tasks/*.md`, active deterministic/behavior eval defaults and workflow canary script. Sync current model references in review skill, `pi/README.md`, bin README, portfolio amendment, SELF-IMPROVEMENT and shell smoke check. Update integration fixtures only where tied to current catalog.
3. Preserve historical calibration manifests/results, generic old-version telemetry fixtures, and retired catalog entries: past evidence must not be relabeled as new-model measurements. Retired catalog facts are needed by paid_review_spend to avoid miscounting subscription provider-reported opportunity cost as paid spend. Review reproduced $22.25 instead of $6.25 when old Sol/Luna facts were removed; retain exact original entries without enabled targets/routes. No new family aliases or abstractions.
4. Run focused regressions, full deterministic suite, layout/shell/ruff, routing-smoke, role-context-smoke and context-health. Review diff locally; no peer model calls authorized. Commit task-owned files, record evidence in Bead, direct-closeout then handoff.

## Verification

```bash
.venv/bin/python -m pytest tests/test_agnt.py tests/test_model_config.py tests/test_catalog.py tests/test_pi_packages.py tests/test_route_feedback.py -q
.venv/bin/python -m pytest tests/ --durations=15
scripts/check-pi-config.sh
bash -n scripts/*.sh
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
pi/agent/bin/agnt context-health --strict
```

No installs, model canaries, remote operations, live deployment, or unrelated plan edits. Provider availability/performance remains unverified. One local implementation commit plus portable Beads closeout commit authorized by normal completion contract.
