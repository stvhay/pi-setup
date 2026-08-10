# Archimedes 2.0.1 Guardrail Stack Design and Implementation Plan

**Issue:** pi-7lyd — Enforce provider output caps for one-shot subagents
**Design:** This file
**Date:** 2026-08-09
**Root branch:** `feature/one-shot-provider-output-caps`
**Upstream base:** `pi-archimedes v2.0.1` at `bdfeea3ed77392a2d02617fa1e0d4aa5fd8317e3`

**Goal:** Rebuild only still-needed subagent guardrail behavior on stable pi-archimedes 2.0.1, add best-effort provider-native one-shot output caps, preserve every available output, keep model names visible in both execution modes, and migrate pi-setup to the current package base.

**Architecture:** Build three clean current-base candidates rather than replaying v1.8.3 commits. PR 1 owns shared bounded execution, truthful usage/termination, Pi 0.84 partial-stream preservation, visible parallel results, adaptive token progress, and shared model rendering. PR 2 stacks mode resolution and one-shot provider output caps on PR 1. PR 3 independently stacks the private repeated-error breaker on PR 1. A vendor branch fast-forwards from the existing vendor lineage through a v2.0.1 merge and the verified current-base behavior. pi-setup remains the billing-policy adapter: it reads canonical catalog billing class and injects a 16,384-token default only for metered one-shot children.

## Source profile

- Profile: `.pi/upstream-profiles/github.com--danielcherubini--pi-archimedes.md`
- Last checked: `2026-08-09T22:09:49Z`
- v2.0.1 is stable, non-draft, non-prerelease, and latest.
- Clean v2.0.1 baseline: frozen install PASS, subagent TypeScript PASS, 54 subagent tests PASS.
- Upstream `main` is ahead only by a plan-archive commit; any actual upstream draft still requires a fresh profile and express approval.

## Behavior relevance matrix

| Existing behavior | v2.0.1 status | Destination |
|---|---|---|
| Child logical Pi session ID | **Superseded upstream** | Omit candidate code; retain native `childSessionId` |
| Single compact/expanded model label | **Superseded upstream** | Reuse native renderers |
| Parallel compact/live model label | **Still missing** | PR 1 shared renderer/progress fix |
| Request/tool/token/cost/time limits | **Still missing** | PR 1 |
| Operator defaults and `maxParallel` | **Still missing** | PR 1 |
| Structured termination and offender-only cancellation | **Still missing** | PR 1 |
| Canonical cache/cost/turn usage | **Still missing** | PR 1 |
| Parallel child output in model-visible tool content | **Still missing** | PR 1 |
| Adaptive current-turn/cumulative token progress | **Still missing** | PR 1 |
| Pi 0.84 delta-only partial output and authoritative final usage | **Still missing** | PR 1, required for output preservation under forced stops |
| Malformed final-event partial preservation | **Still missing** | PR 1 |
| One-shot mode, isolation, thinking precedence, one-request invariant | **Still missing** | PR 2 |
| Effective execution/provider evidence | **Still missing** | PR 2 |
| Provider-native `maxOutputTokens` | **New approved contract** | PR 2 |
| Repeated identical failed-tool breaker | **Still missing** | PR 3 |
| child-context recursion suppression for Pi 0.74 | **Still needed for stated floor** | PR 1 |

## Public contract

### Shared agentic limits — PR 1

`limits` remains optional and unlimited by default:

- `maxProviderRequests`
- `maxToolCalls`
- `maxTotalTokens`
- `maxCostUsd`
- `maxDurationMs`

Agentic cumulative token/cost limits observe authoritative completed-turn usage and may overshoot by one provider response. They preserve the triggering response and stop only before or after later work according to the existing structured termination contract. Subscription models receive no automatic limits; explicit caller/operator limits remain allowed.

### One-shot — PR 2

- `mode: "one-shot"` means at most one provider request with provider retries disabled.
- `limits.maxOutputTokens` is a per-provider-response cap. It is distinct from cumulative `maxTotalTokens`.
- The explicit child guard uses `before_provider_request` to clamp recognized existing payload fields; it never raises a lower provider/model cap.
- Recognized payloads report payload-free `outputLimit.enforcement = "applied"`; unknown shapes run unchanged and report `"unsupported"`. Pi's current Codex Responses adapter exposes no output-cap field, so its distinctive payload runs unchanged as unsupported.
- Caller-supplied one-shot `maxTotalTokens` or `maxCostUsd` is rejected with guidance to use `maxOutputTokens`; operator agentic defaults for those fields are omitted from one-shot resolution.
- Post-response one-shot usage is recorded but never used to discard output or pretend to prevent already-spent tokens.
- Provider `length` completion reports structured `output-limit` evidence while preserving full/partial text and canonical usage.
- Parent cancellation and optional `maxDurationMs` may interrupt the in-flight call; available text/usage remains returned.

### Billing policy — pi-setup

- Canonical billing class comes only from deployed `catalog.json`; nominal prices do not infer billing.
- Configurable default: `meteredOneShotMaxOutputTokens = 16_384`.
- Apply only to effective metered one-shot targets and only as a ceiling; a tighter explicit child limit wins.
- Subscription and unknown billing classes receive no automatic token or cost limit.
- Unsupported provider cap shapes are accepted as best effort and surfaced truthfully.

### Model display

- Reuse native v2.0.1 `SubagentProgress.model` / `SubagentResult.model` and compact/expanded render seams.
- Resolve initial effective model as agent override, then task/top-level model, then active parent model.
- Display model in live and completed single and parallel output for both `agentic` and `one-shot`.
- Capture Pi 0.84 `message_start.model` so model appears before the authoritative final `message_end` when available.

## Branch stack

| Branch | Base | Purpose |
|---|---|---|
| `rebuild/subagent-execution-limits-v2` | v2.0.1 | Clean PR 1 replacement |
| `rebuild/subagent-one-shot-v2` | rebuilt PR 1 | Clean PR 2 replacement |
| `rebuild/subagent-repeated-errors-v2` | rebuilt PR 1 | Clean PR 3 replacement |
| `rebuild/vendor-pi-setup-v2` | existing `vendor/pi-setup` lineage merged with v2.0.1 | Fast-forwardable combined runtime |

Existing remote draft heads remain untouched until final verification and explicit history-rewrite approval. Updating fork `main` from v1.8.3 to v2.0.1 and force-updating draft heads are separate remote gates. No upstream repository action is authorized.

## Acceptance criteria

- [x] Every old PR/vendor behavior is classified and only still-needed behavior appears in rebuilt diffs.
- [x] PR 1 preserves native v2.0.1 child IDs/model management and passes agentic limit, output, usage, Pi 0.84, model-label, Windows, cancellation, malformed-stream, ordering, and compatibility tests.
- [x] PR 2 enforces one provider request, best-effort `maxOutputTokens`, applied/unsupported evidence, mode-correct cumulative-limit behavior, one-shot isolation, thinking precedence, output preservation, and model labels.
- [x] PR 3 stops only the offending agentic child after three identical failed tools with bounded privacy-safe state and preserved partial evidence.
- [x] pi-setup uses exact pi-archimedes 2.0.1 package bases and applies no automatic token/cost limit to subscription children.
- [x] Metered one-shot default is 16,384 and explicit tighter limits win.
- [x] Existing local output contracts, artifact persistence, child trace semantics, Langfuse projection, and package repair remain compatible.
- [x] No remote draft/vendor update occurred before final local gates; history replacement remains approval-gated.

---

### Task 1: Refresh profile and preserve baseline [Completed]

**Files:**
- Modify: `.pi/upstream-profiles/github.com--danielcherubini--pi-archimedes.md`

**Evidence:**
- Exact profile hashes checked against v2.0.1.
- Frozen install, package TypeScript, and 54 baseline tests passed.
- Disposable old-PR cherry-pick exposed conflicts rather than being treated as a rebuild strategy.

### Task 2: Rebuild bounded execution PR 1 [Completed]

**Context:** Start from v2.0.1 and port behavior through current interfaces. Preserve top-level `execute` import, current TypeBox package, model validation, agent manager, native child IDs, and current model renderer structure.

**Files:**
- Create/modify under `packages/subagent/src/`: `child-guard.ts`, `config.ts`, `dispatch-policy.ts`, `limits.ts`, `usage.ts`, `execute.ts`, `handlers.ts`, `index.ts`, `spawn.ts`, `stream.ts`, `types.ts`, compact/expanded/format files, and focused tests.
- Modify: `meta/src/config.ts`, `meta/src/settings.ts`, `packages/subagent/package.json`, `packages/subagent/README.md`, `README.md`, `pnpm-lock.yaml`.
- Create then complete: `docs/plans/2026-08-09-bounded-subagent-execution-v2.md`; update `docs/plans/README.md`.

**Steps:**
1. Commit current-base upstream plan before production edits.
2. Add RED tests for limits, retry policy, partial output/usage, Pi 0.84 events, parallel outputs, adaptive tokens, effective initial model, and compact parallel model labels.
3. Port the smallest shared modules; do not replace v2 agent discovery/model validation/session correlation.
4. Resolve `handlers.ts`, `index.ts`, and `stream.ts` semantically rather than from conflict markers.
5. Run focused tests and package typecheck; commit one implementation/documentation change.

**Focused verification:**
```bash
corepack pnpm --filter @pi-archimedes/subagent exec vitest run
corepack pnpm --filter @pi-archimedes/subagent exec tsc --noEmit
```

### Task 3: Rebuild one-shot/output-cap PR 2 [Completed]

**Files:**
- Create/modify: `packages/subagent/src/execution-profile.ts`, output-cap payload/control helper if needed, `child-guard.ts`, `limits.ts`, `execute.ts`, `index.ts`, `spawn.ts`, `stream.ts`, `types.ts`, focused tests.
- Modify docs/README files.
- Create then complete: `docs/plans/2026-08-09-subagent-one-shot-output-caps-v2.md`; update plan index.

**Steps:**
1. Commit current-base stacked plan.
2. Add RED schema/profile tests for one-shot limit resolution and invalid cumulative limits.
3. Add RED payload-shape tests for OpenAI responses/completions, Anthropic-style, Pi Messages, Google-style, existing lower cap, malformed/unsupported payloads, and payload-free evidence.
4. Add RED stream/result tests proving output and usage survive `length`, unsupported caps, cancellation, timeout, malformed final events, and parallel ordering.
5. Add RED live/completed model-label tests for single/parallel one-shot; retain agentic PR 1 coverage.
6. Implement through existing resolved execution, child guard, spawn environment, stream, and render seams.
7. Run focused/full subagent checks and commit one implementation/documentation change.

### Task 4: Rebuild repeated-error PR 3 [Completed]

**Files:**
- Modify: `packages/subagent/src/stream.ts`, `types.ts`, `stream.test.ts`, package README, plan index.
- Create then complete: `docs/plans/2026-08-09-repeated-error-breaker-v2.md`.

**Steps:**
1. Commit current-base stacked plan.
2. Add RED tests for exact threshold, reset behavior, opaque malformed evidence, depth/node/ID caps, partial output/usage, offender-only termination, and sibling completion.
3. Port the private digest/counter implementation onto PR 1 stream/usage state.
4. Keep one-shot unaffected because it has no tools.
5. Run focused/full subagent checks and commit implementation/documentation.

### Task 5: Assemble fast-forwardable vendor v2 runtime [Completed]

**Context:** Preserve remote vendor ancestry without carrying obsolete production code into the v2 tree.

**Steps:**
1. Branch from existing vendor head, merge exact v2.0.1, and resolve current-base files deliberately.
2. Integrate rebuilt PR 1, PR 2, and PR 3 behavior.
3. Verify final production delta from v2.0.1 contains only still-needed guardrail/one-shot/runtime behavior.
4. Confirm native v2 child ID/model features are not duplicated.
5. Run package/workspace TypeScript, subagent/full tests, and clean diff checks.

### Task 6: Migrate pi-setup package projection [Completed]

**Files:**
- Modify exact pins and projection patches under `patches/pi-packages/`.
- Modify `scripts/update-pi-config.sh`, `pi/agent/extensions/archimedes.ts`, `pi/agent/catalog.json`, relevant docs and tests, and `forks/pi-archimedes` gitlink.

**Steps:**
1. Add RED package-base migration and rollback tests for 1.8.3 → 2.0.1 while preserving pi-langfuse 1.5.10.
2. Add RED billing-policy tests: metered one-shot gets 16,384; tighter explicit wins; subscription/unknown and agentic get none.
3. Regenerate exact production-only v2.0.1 patches from pristine npm package to verified vendor tree.
4. Update revision detection so stale exact v2.0.1 and old 1.8.3 projections repair atomically.
5. Verify isolated migration, rollback, repeat idempotence, package patch exactness, and local wrapper output contracts.

### Task 7: Review, verify, and stage [Completed]

**Upstream gates:**
```bash
corepack pnpm install --frozen-lockfile
corepack pnpm --filter @pi-archimedes/subagent exec tsc --noEmit
corepack pnpm -r exec -- tsc --noEmit
corepack pnpm --filter @pi-archimedes/subagent exec vitest run
corepack pnpm test
git diff --check
```

**Root gates:**
```bash
npm ci --ignore-scripts
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
.venv/bin/python -m pytest tests/
scripts/check-pi-config.sh
bash -n scripts/*.sh
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
git diff --check
```

**Remote gates:**
- Refresh upstream profile and fork/draft state.
- Obtain explicit approval before fork-main fast-forward or any force-with-lease draft replacement.
- Verify remote SHAs, OPEN+DRAFT state, bases, files, commit lists, body, and zero reviewer requests.
- Vendor branch may update only by verified normal fast-forward.
- No upstream PR, Ready action, reviewer request, merge, release, deletion, or pi-setup push.

**Staging evidence:** Fork `main` matches exact v2.0.1. Draft PR 1 is `c717d96`, stacked draft PR 2 is `61955d2`, independent draft PR 3 is `5e0e66c`, and `vendor/pi-setup-v2` is `ac70804`. All three PRs remain OPEN+DRAFT, mergeable, and without reviewer requests; archived v1.8.3 and pre-live-fix v2 heads remain available; no upstream PR exists.

**Live-rollout finding:** Two separately approved, non-retried subscription Codex one-shot calls produced no output because the initial payload heuristic treated any Responses-style `input` array as cap-capable. Pi's Codex adapter does not serialize an output cap, so the injected field caused a provider error; Pi JSON mode exited zero and the initial stream parser mislabeled that assistant error as completed. Test-first follow-ups now classify Codex as unsupported and propagate assistant provider errors even on zero process exit. No third call was made.

**Deployment gate:** Corrected runtime redeployment and any post-fix live call require separate informed approval. Manual `/quit` and restart are required; `/reload` is insufficient.

## File conflicts and ordering

PR 2 and PR 3 both touch `stream.ts`/`types.ts` and depend on PR 1, so implementation is serial. They remain separate branches and are not merged into each other. Vendor integration occurs only after both clean candidates pass. Root pi-setup edits occur in the existing isolated root worktree.

## Execution handoff

Plan saved to `.pi/plans/2026-08-09-archimedes-2.0.1-guardrail-stack-design-plan.md` and verified before implementation. Use `test-driven-development` for every behavior change and `verification-before-completion` before commits or staging.
