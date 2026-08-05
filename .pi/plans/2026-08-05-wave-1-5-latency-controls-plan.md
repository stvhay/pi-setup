# Wave 1.5 Latency Controls Implementation Plan

**Issues:** pi-4tg9.32, pi-4tg9.33, pi-4tg9.30, pi-4tg9.29, pi-4tg9.17 (`pi-4tg9.18` deferred)
**Design:** Approved conversation decisions plus Bead acceptance criteria
**Date:** 2026-08-05
**Branch:** `main`, with one sequential isolated worktree per item

**Goal:** Reduce avoidable compaction, progress, verification, and provider-failure latency without weakening memory, safety, or completion evidence.

**Architecture:** Execute and integrate five atomic items strictly in dependency order. Keep observational-memory configuration in tracked Pi settings, workflow behavior in existing root/skill seams, and provider circuits in private runtime state consumed by deterministic routing. Use focused TDD during each item and run one complete project gate on the final integrated candidate. Do not modify upstream-package source; `pi-4tg9.18` remains deferred because live sibling-local subagent budgets have no supported pi-setup seam.

**Acceptance Criteria:**
- [ ] `pi-4tg9.32`: ratio-mode compaction uses `0.5`; 272,000-token models trigger at 136,000; package fallback remains 81,000 when context is unavailable.
- [ ] `pi-4tg9.33`: observational-memory observer/reflector/dropper workers use `openai-codex/gpt-5.6-sol` at `low`; compaction remains model-free.
- [x] `pi-4tg9.18` scope decision: defer owner-package work; no source patch, fork, PR, push, release, pin, deployment, or installed-package edit.
- [ ] `pi-4tg9.30`: phase progress remains visible without micro-step todo turns; independent reads/checks batch; writes, approvals, and safety gates remain serialized.
- [ ] `pi-4tg9.29`: workflow distinguishes baseline-once, focused repair, pre-existing failure, and final-gate-once phases without weakening final evidence.
- [ ] `pi-4tg9.17`: deterministic quota/credit/auth/availability failures open expiring provider-venue circuits; routes visibly exclude only affected venue; success/expiry closes safely.
- [ ] Each in-scope item is reviewed, focused-verified, locally committed, integrated, and closed before the next starts.
- [ ] Final integrated candidate passes one complete project release gate.

**Established Baseline (2026-08-05):**

```text
scripts/check-pi-config.sh && bash -n scripts/*.sh                PASS
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests       PASS
.venv/bin/python -m pytest -p no:cacheprovider tests/             484 passed
agnt eval run routing-smoke                                      PASS
agnt eval run role-context-smoke                                 PASS
agnt context-health --strict                                     PASS; known 5-character discovery headroom warning
git diff --check && git status --short --branch                  PASS; clean main
```

Do not rerun this complete matrix during repair. Run task-focused checks below; run the complete matrix once on the final candidate. If the final candidate changes after that gate, rerun only then.

---

## Execution Order

`pi-4tg9.32` → `pi-4tg9.33` → `pi-4tg9.30` → `pi-4tg9.29` → `pi-4tg9.17`

For each item:

1. Create one ignored `.worktrees/` checkout from current integrated `main`.
2. Write the smallest failing test first.
3. Implement only that Bead.
4. Run focused checks and inspect diff/status.
5. Run one bounded independent review when risk warrants it.
6. Commit task-owned changes.
7. Integrate into `main`, rerun focused checks, close Bead, record outcome, then clean its worktree/branch under existing authorization.
8. Start the next item only after integration.

No upstream PR, fork, push, release, history rewrite, or unapproved remote deployment.

### Task 1: Scale observational-memory compaction [pi-4tg9.32]

**Context:** Installed `pi-observational-memory@3.0.3` exactly matches upstream commit `27a5195eaf90e4e2ca1302e3a31d4bb14df982a5`. Its ratio resolver computes `floor(contextWindow * ratio)` and falls back to calibrated `compactAfterTokens` when context is missing/non-positive.

**Files:**
- Modify: `pi/agent/settings.json`
- Modify: `tests/test_pi_packages.py`
- Modify: `tests/test_model_config.py` only if needed for the 272,000 catalog invariant
- Modify: `pi/README.md`

**Steps:**
1. Add a failing settings contract asserting package pin, `compactAfterTokensMode: ratio`, and ratio `0.5`.
2. Add deterministic assertions for Sol context `272000`, effective threshold `136000`, and installed-source fallback contract `81000` without duplicating package production logic.
3. Add only ratio fields to tracked configuration; preserve V3 defaults.
4. Document exact package/README provenance, formula, threshold, and fallback.
5. Focused verify and commit.

**Focused verification:**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider tests/test_pi_packages.py tests/test_model_config.py
scripts/check-pi-config.sh
git diff --check
```

### Task 2: Pin memory workers to low-thinking Sol [pi-4tg9.33]

**Context:** Package exposes one shared worker model for observer, reflector, and dropper. `model.thinking` does not control compaction; compaction renders prepared ledger state without inference.

**Files:**
- Modify: `pi/agent/settings.json`
- Modify: `tests/test_pi_packages.py`
- Modify: `pi/README.md`

**Steps:**
1. Add failing assertions for provider `openai-codex`, id `gpt-5.6-sol`, and exactly `low` thinking.
2. Add model override to existing namespace; do not duplicate observer/reflection/pool defaults.
3. Document shared worker scope and model-free compaction.
4. Deploy tracked config with `scripts/update-pi-config.sh` after focused checks.
5. In a fresh bounded Pi process/session, inspect `/om:status` or equivalent effective status and confirm 136,000 next-compaction threshold. Do not wait an hour or claim a compaction-model test.
6. Focused verify and commit.

**Focused verification:**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider tests/test_pi_packages.py tests/test_update_pi_config.py
scripts/check-pi-config.sh
bash -n scripts/*.sh
```

### Deferred: Live per-child subagent budgets [pi-4tg9.18]

Human decision on 2026-08-05: do not modify upstream-package source. Evaluation confirmed live limits require the package-owned per-child stream and cancellation seam. Pi-setup sees only the outer tool lifecycle; parent cancellation is not sibling-local, and post-completion accounting would not satisfy the acceptance criteria. Keep the Bead open and deferred. Do not create a local source patch, fork, PR, push, release, pin, deployment, or installed-package edit.

### Task 4: Reduce progress-only turns and batch independent tools [pi-4tg9.30]

**Files:**
- Modify: `pi/agent/AGENTS.md`
- Modify: `pi/agent/skills/token-saver/SKILL.md`
- Modify: `pi/agent/extensions/agent-os-compat.ts`
- Modify: `tests/test_agent_os_compat.py`
- Modify: `tests/test_context_architecture.py`

**Steps:**
1. Add failing deterministic contracts requiring phase-boundary progress, execution-derived status, independent read-only batching, and serialization of writes/approvals/safety gates.
2. Add two concise always-on rules to global instructions; do not load token-saver by default or change its discovery description.
3. Add detailed batching/progress method to token-saver.
4. Reuse existing RPC tool execution events to show/clear bounded non-todo activity without exposing payloads; preserve todo and subagent widgets.
5. Run a fresh bounded telemetry-backed workflow after deployment. Compare against the 79 todo-only-turn baseline; prove representative independent reads have no intervening progress-only turn while phase visibility remains.
6. Focused verify and commit.

**Focused verification:**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider tests/test_agent_os_compat.py tests/test_context_architecture.py
pi/agent/bin/agnt context-health --strict
scripts/check-pi-config.sh
git diff --check
```

### Task 5: Separate baseline, repair, and final verification [pi-4tg9.29]

**Files:**
- Modify: `pi/agent/skills/verification-before-completion/SKILL.md`
- Modify: `pi/agent/skills/finishing-a-development-branch/SKILL.md`
- Modify: `pi/agent/skills/executing-plans/SKILL.md`
- Modify: `pi/agent/skills/using-git-worktrees/SKILL.md`
- Modify: `tests/test_context_architecture.py`
- Create: `pi/agent/evals/verification-phases-smoke/eval.json`
- Create: `pi/agent/evals/verification-phases-smoke/prompt.md`

**Steps:**
1. Replace obsolete unconditional full-matrix rerun assertions with RED phase-contract tests.
2. Define baseline once, focused repair, unchanged-baseline classification, final stable-candidate gate, and candidate invalidation consistently across workflow skills.
3. Preserve hard rule: unresolved required final gate means `NOT VERIFIED`; any final-candidate change requires a new final gate.
4. Add bounded eval requiring exact phase decisions for a representative pre-existing-failure scenario.
5. Run focused deterministic checks and one Luna eval; commit.

**Focused verification:**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider tests/test_context_architecture.py tests/test_agnt.py
pi/agent/bin/agnt eval run verification-phases-smoke --models openai-codex/gpt-5.6-luna
pi/agent/bin/agnt context-health --strict
git diff --check
```

### Task 6: Add provider-venue circuits [pi-4tg9.17]

**Files:**
- Create: `pi/agent/bin/agnt_lib/provider_circuits.py`
- Modify: `pi/agent/bin/agnt`
- Modify: `pi/agent/bin/agnt_lib/invoke.py`
- Modify: `pi/agent/bin/agnt_lib/metrics.py`
- Modify: `pi/agent/bin/agnt_lib/routing.py`
- Modify: `pi/agent/extensions/subagent-error-workaround.ts`
- Create: `tests/test_provider_circuits.py`
- Modify: `tests/test_route_feedback.py`
- Modify: `tests/test_agnt.py`
- Modify: `tests/test_subagent_workaround.py`
- Modify: `pi/agent/bin/README.md`

**Design constraints:**
- Key by exact provider venue, never model family.
- Persist only bounded enum/reason/timestamps in private runtime; never raw errors, prompts, URLs, IDs, or payloads.
- Classify deterministic quota, credit, auth, and explicit 502/503/504 availability failures; ignore cancellation, timeout, and unknown process errors.
- Use short class-specific TTLs with hard cap; prune expired state on every read/write.
- Serialize mutation with stdlib file lock plus atomic replace and mode-0600 file under mode-0700 runtime directory.
- Any successful call on a venue closes its circuit. Expiry also closes lazily.
- Route JSON visibly includes reason and expiry while same-family local/subscription venues remain eligible.

**Steps:**
1. Add RED pure classifier/state/expiry/concurrency tests.
2. Implement private circuit store and `agnt provider-circuit` structured command.
3. Integrate `invoke.py` open/close and preserve provider failure subclass in metrics.
4. Filter active provider circuits before family scoring in routing.
5. Integrate equivalent bounded classification/open/close through existing TypeScript `runAgntJson` bridge for subagent results.
6. Add provider-isolation, visible-reason, success/expiry, and parallel mutation tests.
7. Focused verify and commit.

**Focused verification:**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider \
  tests/test_provider_circuits.py tests/test_route_feedback.py tests/test_agnt.py tests/test_subagent_workaround.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
scripts/check-pi-config.sh
git diff --check
```

## File Conflicts

| File | Tasks | Resolution |
|---|---|---|
| `pi/agent/settings.json` | 1, 2 | Strict sequence; Task 2 starts from integrated Task 1. |
| `tests/test_pi_packages.py` | 1, 2 | Strict sequence. |
| `pi/README.md` | 1, 2 | Strict sequence; preserve prior documentation. |
| `tests/test_context_architecture.py` | 4, 5 | Task 5 starts after Task 4 integration. |

## Final Release Gate

Run once after Task 6 is integrated and no further candidate edits remain:

```bash
scripts/check-pi-config.sh
bash -n scripts/*.sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider tests/
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
pi/agent/bin/agnt eval run workflow-gate-smoke --models openai-codex/gpt-5.6-luna
pi/agent/bin/agnt eval run verification-phases-smoke --models openai-codex/gpt-5.6-luna
pi/agent/bin/agnt context-health --strict
git diff --check
git status --short --branch
```

Classify any failure against the established baseline. Do not rerun the complete gate unchanged; use one focused repair and focused rerun, then rerun the complete gate only because the final candidate changed.

## Execution Handoff

Plan saved to: `.pi/plans/2026-08-05-wave-1-5-latency-controls-plan.md`

Recommended execution: `test-driven-development` for each behavior change, `executing-plans` for strict serial integration, and `verification-before-completion` once at final closeout.
