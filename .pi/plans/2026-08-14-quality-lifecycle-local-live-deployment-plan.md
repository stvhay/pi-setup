# Quality Lifecycle Local-Live Deployment Plan

**Issue:** None — execute under a separately approved deployment Bead
**Design:** `.pi/plans/2026-08-13-harness-quality-governance-kernel-plan.md`
**Date:** 2026-08-14
**Branch:** `main`

**Goal:** Deploy quality authority and lifecycle capture to local-live `~/.pi` in two independently approved, verified, and reversible stages.

**Architecture:** Stage 1 deploys Q1's local quality authority from exact commit `3abc69c`; Stage 2 deploys Q2's lifecycle adapter from the eventual `pi-rxo3.2` implementation commit. Each stage uses an immutable Git snapshot with the existing `scripts/update-pi-config.sh`, one dry-run, one local-live mutation approval, focused canaries, and a stage-specific rollback source. File-at-a-time copies are forbidden because Q2 depends on Q1's CLI and must remain an atomic config snapshot.

**This plan is not deployment authority.** Create or select a deployment Bead, bind exact source/target identities in `ticket_approval`, and stop if approval, identity, preview, rollback, or verification differs from this plan.

**Acceptance Criteria:**
- [ ] Q1 local capture is deployed and canaried before Q2 mutation starts.
- [ ] Q2 root startup and settlement capture work in a fresh Pi session without making pi-langfuse authoritative.
- [ ] Missing-package/service behavior remains covered by source tests; live package files are never moved or deleted for a canary.
- [ ] Runtime secrets, sessions, caches, trust, metrics, and improvement state remain excluded from managed writes/deletes.
- [ ] Each stage has exact preview, approval, post-deploy evidence, stop decision, and rollback source.

**Verification Command(s):**
```bash
scripts/check-pi-config.sh
.venv/bin/python -m pytest tests/test_quality.py tests/test_quality_lifecycle.py tests/test_subagent_workaround.py tests/test_langfuse_evaluators.py tests/test_update_pi_config.py
PI_CONFIG_DIR="$LIVE_DEST" scripts/check-pi-config.sh
git diff --check
```

---

## Fixed identities and source rules

- **Repository:** current `pi-setup` checkout; verify with `git rev-parse --show-toplevel`.
- **Stage 0 rollback source:** `5a402fc` (last commit before Q1 implementation).
- **Stage 1 source / Stage 2 rollback source:** `3abc69c` (Q1 implementation).
- **Stage 2 source:** exact task-owned `pi-rxo3.2` implementation commit recorded after this Bead commits; no later commit may be substituted.
- **Canonical source:** `<snapshot>/pi`, produced by `git archive <exact-sha> pi`.
- **Canonical target class:** `local-live`.
- **Canonical target:** resolved default `$HOME/.pi`; never set `PI_CONFIG_DEST_UNSAFE_OK`.
- **Deployment command:** `PI_CONFIG_SOURCE="$SNAPSHOT/pi" scripts/update-pi-config.sh`.
- **Preview command:** same command plus `--dry-run`.

At execution, record exact repository root, source SHA, `hostname`, `id -un`, resolved `$HOME`, and resolved `$HOME/.pi` in private evidence before requesting approval. Any mismatch is an unknown target and stops.

## Stage 0: Prepare immutable evidence [Independent]

**Context:** Build private source snapshots and evidence without changing local-live state.

**Steps:**
1. Start a dedicated deployment Bead/session. Do not reuse an implementation session.
2. Confirm `pi-rxo3.1` and `pi-rxo3.2` are closed successfully and implementation commits are ancestors of `main`.
3. Run the full source verification matrix from the parent kernel plan against current `main`.
4. Resolve local-live identity without `PI_CONFIG_DEST` overrides:
   ```bash
   LIVE_DEST=$(python3 -c 'import pathlib; print(pathlib.Path.home().joinpath(".pi").resolve(strict=False))')
   test "$LIVE_DEST" = "$(python3 -c 'import pathlib; print(pathlib.Path("~/.pi").expanduser().resolve(strict=False))')"
   printf 'host=%s user=%s home=%s dest=%s\n' "$(hostname)" "$(id -un)" "$HOME" "$LIVE_DEST"
   ```
5. Create a private temporary root with mode `0700`; export `5a402fc`, `3abc69c`, and the exact Q2 commit using `git archive`. Verify each snapshot contains executable `pi/agent/bin/agnt` and no `.git` directory.
6. Create a private evidence directory outside Git. Record source SHAs, identity, command output, dry-runs, checks, and rollback result there; store no credentials or session bodies.

**Stop conditions:** dirty tracked source, unknown Q2 commit, non-ancestor source, target identity mismatch, missing rollback snapshot, or any generated evidence under tracked Git paths.

## Stage 1: Deploy Q1 local authority [Depends on: Stage 0]

**Context:** Establish Q1 before loading Q2, because `quality-lifecycle.ts` calls Q1's `agnt quality capture` contract.

**Steps:**
1. Run and retain exact preview:
   ```bash
   PI_CONFIG_SOURCE="$Q1_SNAPSHOT/pi" scripts/update-pi-config.sh --dry-run
   ```
2. Confirm preview writes only managed `pi/` config, preserves documented rsync exclusions, performs no package version change, and names no unexpected deletion. Stop on drift.
3. Create one exact `ticket_approval` for Stage 1. Bind deployment Bead, source SHA `3abc69c`, repository, local-live identity, preview digest/output ref, command, expected effects, checks, and rollback command using the `5a402fc` snapshot.
4. After approval, run the deployment command once. First mutation attempt consumes Stage 1 authority; do not retry automatically.
5. Verify live layout:
   ```bash
   PI_CONFIG_DIR="$LIVE_DEST" scripts/check-pi-config.sh
   "$LIVE_DEST/agent/bin/agnt" quality capture --help
   ```
6. Run a payload-free local authority canary from repository cwd with a unique opaque session ID and the deployment Bead ID:
   ```bash
   "$LIVE_DEST/agent/bin/agnt" quality capture --payload "$Q1_CANARY_PAYLOAD" --json
   "$LIVE_DEST/agent/bin/agnt" work status --session-id "$Q1_CANARY_SESSION"
   ```
   Payload must contain only schema version, `recordType: invocation`, opaque session ID, deployment Bead ID, and bounded `invocation:` EvidenceRef.
7. Record PASS only when output is schema-valid, active ownership matches the deployment Bead, and private ledger permissions remain `0700` directory / `0600` file.

**Rollback:** If mutation completes but any Stage 1 check fails, use the preapproved `5a402fc` snapshot command once, rerun live layout checks, record exact result, and stop. Do not proceed to Stage 2.

## Stage 2: Deploy Q2 lifecycle adapter [Depends on: Stage 1]

**Context:** Add root lifecycle capture while keeping pi-langfuse projection optional and subagent peer behavior intact.

**Steps:**
1. Re-run focused Q2 source tests immediately before preview:
   ```bash
   .venv/bin/python -m pytest tests/test_quality_lifecycle.py tests/test_subagent_workaround.py tests/test_langfuse_evaluators.py
   ```
2. Run and retain exact Q2 preview:
   ```bash
   PI_CONFIG_SOURCE="$Q2_SNAPSHOT/pi" scripts/update-pi-config.sh --dry-run
   ```
3. Require preview to add `agent/extensions/quality-lifecycle.ts`, update only expected managed Q2/Q1 files, preserve runtime exclusions, and show no package reinstall/version change or unexpected deletion.
4. Create a new exact `ticket_approval` for Stage 2. Bind exact Q2 commit, same verified local-live identity, new preview, command, expected effects, checks, and rollback command using `3abc69c`. Stage 1 approval cannot authorize Stage 2.
5. After approval, run the deployment command once. No automatic retry.
6. Verify live layout and exact source equality for Q2-owned extension files:
   ```bash
   PI_CONFIG_DIR="$LIVE_DEST" scripts/check-pi-config.sh
   cmp "$Q2_SNAPSHOT/pi/agent/extensions/quality-lifecycle.ts" "$LIVE_DEST/agent/extensions/quality-lifecycle.ts"
   cmp "$Q2_SNAPSHOT/pi/agent/extensions/subagent-error-workaround.ts" "$LIVE_DEST/agent/extensions/subagent-error-workaround.ts"
   cmp "$Q2_SNAPSHOT/pi/agent/extensions/langfuse-config-env.ts" "$LIVE_DEST/agent/extensions/langfuse-config-env.ts"
   ```
7. Start one fresh persisted Pi canary session in this repository. Link it to the deployment Bead, run one read-only prompt, wait for `agent_settled`, then verify `agnt work status --session-id "$PI_SESSION_ID"` still reports that Bead. Startup must settle or emit bounded `quality-capture` / `langfuse-projection` gap evidence within the adapter's five-second local deadline; it must not hang.
8. Run one ordinary unnamed read-only peer canary. Verify subagent result/artifact output and provider-circuit status remain available; no root interactive handler may reappear in `subagent-error-workaround.ts`.
9. Do not remove or rename live pi-langfuse files. Treat missing package/service behavior as proven by `tests/test_quality_lifecycle.py` and `tests/test_langfuse_evaluators.py`; runtime mutation to simulate absence is outside this plan.

**Rollback:** If mutation completes but any Stage 2 check fails, use the preapproved `3abc69c` snapshot command once, rerun Stage 1 live checks, preserve private evidence, and stop. Do not improvise partial file restoration.

## Observation window and promotion

1. Keep Q2 at local-live only through at least three settled root turns and one unnamed peer result across fresh sessions.
2. Check for bounded gap messages, startup latency, local ledger growth/permissions, missing root projections, peer artifact/metric continuity, and provider-circuit continuity.
3. Classify result `validated`, `rollback-complete`, or `blocked`; absence of Langfuse projection is an explicit gap, not local capture failure.
4. Do not deploy Q3 or later kernel slices until Q2 is validated or a follow-up Bead resolves observed failure.

## Execution Handoff

Plan saved to: `.pi/plans/2026-08-14-quality-lifecycle-local-live-deployment-plan.md`.

Recommended skills: `approval-confirmation` before each mutation, `verification-before-completion` for each stage, and `failure-choreography` for rollback/blocked closeout.
