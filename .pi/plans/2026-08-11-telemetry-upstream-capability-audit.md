# Telemetry Upstream Capability Audit

**Bead:** `pi-czrl.1`

**Audit cutoff:** 2026-08-11 UTC

**Scope:** Langfuse, OpenTelemetry, Pi, `pi-langfuse`, `pi-archimedes`, personal-fork PRs, and pi-setup projections. This audit uses public source/docs and tracked repository artifacts only. It contains no private telemetry, Langfuse IDs, session IDs, prompts, outputs, absolute paths, or secrets.

## Decision summary

1. Use native Langfuse release, environment, session, and OpenTelemetry resource fields. Do not recreate them in repository metadata.
2. Keep root/child classification, settled-window semantics, present-zero validation, error normalization, timing/lineage joins, and closeout read retries local to `agnt`.
3. Pi 0.84.1 supports `agent_end`, `agent_settled`, `session_shutdown`, assistant usage, and `SessionManager.getSessionId()`. Normal interactive-result absence is therefore a local loader/event defect until an integration reproducer proves otherwise. Hard process death remains unsupported lifecycle delivery.
4. `pi-langfuse` 1.5.12 already contains repository source detection. Source work must harden and normalize that existing feature, not add a duplicate collector.
5. Open exactly one new `pi-langfuse` PR for source-metadata privacy/compatibility and one separate PR for payload-byte accounting. Existing ingestion/media PRs remain separate.
6. `pi-archimedes` session correlation is merged and released. Execution-limit PRs remain personal-fork drafts and need current-base/evidence maintenance, not replacement PRs.

## Audited versions and revisions

| Component | Tracked/pinned state | Current upstream state at cutoff | Result |
|---|---|---|---|
| Pi | `@earendil-works/pi-coding-agent@0.84.1`, npm `gitHead` `53fa77c`; `package.json` | npm latest is also 0.84.1; upstream `main` `534bcbf` | Pin is current published release. Upstream changes after the pin do not change audited lifecycle semantics. |
| `pi-langfuse` | 1.5.12; base `c79c527`; vendor projection `c5da10a`; `pi/agent/settings.json`, `forks/pi-langfuse` | `main` and latest release are 1.5.12 at `c79c527` | Installed base equals upstream main/latest release. |
| Langfuse JS | `@langfuse/{client,otel,tracing}` 5.3.0; `forks/pi-langfuse/package-lock.json` | 5.3.0 API inspected from installed lock | Native environment/release/session/metadata APIs are available. |
| OpenTelemetry JS | API 1.9.1, resources 2.7.1, SDK Node 0.218.0 in lock | Current semantics verified from official docs | Resource attributes are available without a package patch. |
| `pi-archimedes` | 2.0.1; base `bdfeea3`; vendor projection `182f5d4`; `pi/agent/settings.json`, `forks/pi-archimedes` | latest release 2.0.1; upstream `main` `a2bd4d6`, 11 commits after release | Post-release commits are docs/tests/session naming, not execution limits, one-shot caps, or repeated-error stopping. |

## Capability matrix

Disposition vocabulary is the Bead-required set: **configuration**, **local normalization**, **existing-PR adjustment**, **new pi-langfuse PR**, or **unsupported Pi lifecycle behavior**.

| Gap/capability | Verified native or upstream evidence | Disposition | Required boundary |
|---|---|---|---|
| Release/build identity | Langfuse JS reads `LANGFUSE_RELEASE`; release may be a semantic version or commit. `LangfuseSpanProcessor` 5.3.0 exposes `release`. [L1] | **configuration** | Set once at deployment/runtime. Do not duplicate commit as repository metadata unless explicitly needed. |
| Deployment environment | Langfuse supports `LANGFUSE_TRACING_ENVIRONMENT`; OTel `deployment.environment.name` also maps to Langfuse environment. [L2] [L6] [O3] | **configuration** | Prefer first-class environment. Do not add custom `environment` metadata. |
| Service identity/version | OTel JS accepts `OTEL_SERVICE_NAME` and `OTEL_RESOURCE_ATTRIBUTES`; stable attributes include `service.name` and `service.version`. Langfuse retains resource attributes under `metadata.resourceAttributes`. [O1] [O2] [L6] | **configuration** | Resource attributes are retained but not top-level/filterable by default. Add explicit metadata only when filtering is a demonstrated requirement. |
| Logical Pi session ID | Pi exposes `SessionManager.getSessionId()`; Langfuse accepts a session ID under 200 characters. `pi-langfuse` PR #9 and Archimedes PR #25 are merged and included in pinned releases. [P1] [P2] [L3] [F9] [A25] | **configuration** | Reuse one logical UUID. Do not add invocation or trace IDs for the same join. Keep IDs out of Beads/Git. |
| Parent/child/root classification | Archimedes 2.0.1 emits optional `childSessionId`; pi-setup already projects parent/child IDs and declared trace availability. `agnt` currently groups every session as a review candidate, including discovered child roots. | **local normalization** | Classify exact child sessions from bounded discovered projections before root outcome coverage. No extra Langfuse call or upstream field. |
| Settled window and ingestion watermark | Langfuse reads are time-bounded but ingestion and score visibility can lag. Neither Pi events nor Langfuse query bounds make a just-ended cohort settled. | **local normalization** | Apply a fixed settlement lag/watermark to cohort selection; report late/active exclusion and lower bounds. Re-running the same settled window must be stable. |
| Closeout outcome visibility | Score IDs are deterministic locally; upstream `pi-langfuse` PR #10 makes ingestion retry IDs stable. Immediate score reads can still be briefly empty. [F10] | **local normalization** | Retry only the exact unavailable-after-success read, using one monotonic bounded deadline/backoff. Never duplicate the write or retry ownership/transport failures. |
| Objective interactive lifecycle | Pi documents `agent_end` messages and `agent_settled` after retry, compaction, and queued continuations. Pinned source emits `agent_settled` in `_runAgentPrompt` `finally`. [P1] | **local normalization** | Use actual loader/event integration. Derive objective status from final assistant messages; `agent_settled` itself has no outcome payload. Exactly one projection per supported prompt run. |
| Abrupt process death | Pi awaits `session_shutdown` for graceful quit/reload/session replacement, but no extension event can survive SIGKILL, host death, or process failure before handler execution. [P1] | **unsupported Pi lifecycle behavior** | Record outcome as unavailable. No polling, transcript scraping, or claim of exactly-once delivery for hard death. Prepare Pi evidence only if a supported normal/error path fails. |
| Usage: present zero versus missing | Pi assistant messages require a `usage` object; `pi-langfuse` maps usage into generation `usageDetails`. Current `agnt` treats absent/empty usage as missing but silently coerces missing individual fields to zero. | **local normalization** | Validate required keys and numeric ranges before summing. Preserve valid zero. Mark only affected dimensions unavailable. Do not infer provider usage. |
| Error classification | Pi supplies assistant `stopReason`/`errorMessage`, tool `isError`, and usage; `pi-langfuse` retains finish/status/error metadata; local projections add provider/process/artifact evidence. | **local normalization** | Normalize allowlisted categories from existing metadata. Keep unknown rather than guessing. Keep error class separate from outcome-blocking and evaluator quality. |
| Timing and lineage | Langfuse observations have start/end/latency and trace parentage; OTel preserves resource attributes; Archimedes supplies child session ID; local metrics already hold parent/child IDs and start/end/duration. | **local normalization** | Retain existing fields and provenance. Do not introduce a second lineage key. Public summaries remain count-only. |
| Repository source metadata | `pi-langfuse` commit `ea4ff09` added source detection and is already in 1.5.12. Current code captures repo/root names, branch, commit, and sanitized remote host/path by default, lacks dirty/disabled/detached semantics, and README still calls shipped behavior a “local prototype.” OTel has release-candidate `vcs.*` names. [F1] [F2] [O4] | **new pi-langfuse PR** | Harden existing collector only: reuse release/environment/service fields; define opt-in/default privacy, detached/dirty/non-Git/disabled behavior, override precedence, and compatibility. Never emit remote URLs, usernames, absolute paths, or private repo names by default. |
| Tool payload byte accounting | `pi-langfuse` currently shapes, applies capture policy, then measures `captured.toolInput/toolOutput`; disabled capture therefore measures replacement/absence rather than the bounded source representation. Langfuse accepts numeric observation metadata but defines no privacy guarantee or tool-payload-byte semantic. [F3] [L4] [L5] | **new pi-langfuse PR** | Compute bounded UTF-8 byte counts before replacement, but export exact counts only under a dedicated metadata capture control. Tool-I/O-disabled/redacted defaults suppress exact counts and report unavailable state; explicit opt-in may retain numbers plus captured/redacted/absent/truncated/unknown state. No raw/reversible payload. Version semantics instead of silently reinterpreting existing `inputBytes`/`outputBytes`. |
| Archimedes execution limits | Personal-fork PR #1 contains bounded execution limits; upstream main does not. PR is clean against fork `main@bdfeea3`, but fork main is 11 commits behind upstream main. [A1] | **existing-PR adjustment** | Sync/restack without force update; then attach public-safe request-limit/parent-completion evidence. |
| Archimedes one-shot/output caps | Personal-fork PR #2 is stacked on PR #1 at `61955d2`. Deployed vendor commit `182f5d4` contains a later exact output-limit fix not in PR #2. [A2] | **existing-PR adjustment** | Port only reviewed output-cap fixes/tests into PR #2; do not pull repeated-error scope into it. Keep unsupported Codex handling truthful. |
| Archimedes repeated-error stop | Personal-fork PR #3 is stacked on PR #1 at `5e0e66c`; upstream main has no overlap. [A3] | **existing-PR adjustment** | Preserve bounded/privacy-safe detection. Claim only tested evidence; absence of live recurrence is not validation. |
| Existing `pi-langfuse` ingestion/media PRs | Fork PR #2 (`9c4103d`) and PR #3 (`bcaa42a`) are clean, one-commit drafts based on current upstream `c79c527`. [LF2] [LF3] | **existing-PR adjustment** | Keep them current and separate. Do not fold repository metadata or tool accounting into ingestion batching/media bounds. |

## Upstream PR and merge state

### Merged and released; do not duplicate

| Repository | Change | Merge/release state |
|---|---|---|
| `gooyoung/pi-langfuse` | PR #9 logical Pi session ID | merged as `a827ae4`; included in 1.5.12 [F9] |
| `gooyoung/pi-langfuse` | PR #10 stable score entity IDs | merged as `dab5e19`; included in 1.5.12 [F10] |
| `gooyoung/pi-langfuse` | PR #16 Langfuse v4 shutdown | merged as `b1adf5b`; included in 1.5.12 [F16] |
| `danielcherubini/pi-archimedes` | PR #25 child Pi session ID | merged as `e3fda45`; included in 2.0.1 [A25] |

### Open personal-fork drafts at cutoff

| PR | Base | Head | State |
|---|---|---|---|
| `stvhay/pi-langfuse#2` | `main@c79c527` | `fix/ingestion-byte-batches@9c4103d` | clean, 1 commit, 4 files [LF2] |
| `stvhay/pi-langfuse#3` | `main@c79c527` | `fix/media-safe-payload-bounds@bcaa42a` | clean, 1 commit, 12 files [LF3] |
| `stvhay/pi-archimedes#1` | fork `main@bdfeea3` | `feat/subagent-execution-limits@c717d96` | clean against stale fork base; upstream main is 11 commits ahead [A1] |
| `stvhay/pi-archimedes#2` | `feat/subagent-execution-limits@c717d96` | `feat/subagent-one-shot-mode-stacked@61955d2` | clean stacked draft; missing later deployed output-limit fix [A2] |
| `stvhay/pi-archimedes#3` | `feat/subagent-execution-limits@c717d96` | `fix/subagent-repeated-errors@5e0e66c` | clean stacked draft [A3] |

No upstream `gooyoung/pi-langfuse` or `danielcherubini/pi-archimedes` PR was open at cutoff. New source and byte-accounting work must therefore use new focused personal-fork branches/PRs.

## Child issue routing

| Child | Audit result |
|---|---|
| `pi-czrl.2` | Local normalization only. Reuse existing session, usage, error, timing, lineage, release/environment/resource fields. |
| `pi-czrl.3` | Local bounded read retry only. Upstream stable score IDs are already released. |
| `pi-czrl.4` | Supported Pi lifecycle; local loader/event fix unless integration proof identifies a Pi defect. Hard death remains unavailable. |
| `pi-czrl.5` | Maintain/restack existing Archimedes PRs; session ID is already upstream. |
| `pi-czrl.6` | New focused `pi-langfuse` PR that hardens existing source metadata and removes native-field duplication. |
| `pi-czrl.7` | Separate new focused `pi-langfuse` PR for versioned privacy-safe byte accounting. |
| `pi-czrl.8` | Monitor settled cohorts; distinguish coverage, missingness, zero, lower bounds, and released-projection retirement. |

## Privacy and backward compatibility constraints

- Private telemetry stays in Langfuse/private runtime only. Beads, Git, commits, and PRs may contain public code facts and aggregate-safe evidence only.
- Never publish session, trace, observation, prompt, output, tool payload, local path, private repository identity, or private Langfuse URL/ID.
- Commit/repository identity is not universally public. `LANGFUSE_RELEASE`, `service.*`, and `vcs.*` values need explicit operator/deployment policy for private repositories.
- Current `pi-langfuse` source metadata sanitizes credentials and protocols but still reveals owner/repo/remote path by default. New work must fail closed for privacy and document migration/rollback for dashboards using old keys.
- Langfuse masking applies to input, output, and metadata before export, but numeric length remains a side channel. Use a dedicated byte-metadata capture control; suppress exact counts by default when tool I/O is disabled/redacted, expose unavailable state, and require explicit opt-in for exact bounded counts. Do not call numeric metadata inherently safe. [L5]
- Preserve existing privacy presets and explicit operator overrides. Additive optional fields are preferred; when semantics change, add schema/status metadata rather than silently changing old values.
- Preserve old Pi contexts without newer APIs, historical records without child IDs, non-Git operation, detached HEAD, and unavailable usage/error metadata.
- `agent_settled` indicates quiescence, not success. Objective execution, human outcome, evaluator quality, and telemetry availability remain separate dimensions.

## Verified primary sources

- [L1] [Langfuse releases and versioning](https://langfuse.com/docs/observability/features/releases-and-versioning)
- [L2] [Langfuse environments](https://langfuse.com/docs/observability/features/environments)
- [L3] [Langfuse sessions](https://langfuse.com/docs/observability/features/sessions)
- [L4] [Langfuse metadata](https://langfuse.com/docs/observability/features/metadata)
- [L5] [Langfuse masking](https://langfuse.com/docs/observability/features/masking)
- [L6] [Langfuse OpenTelemetry mapping](https://langfuse.com/integrations/native/opentelemetry)
- [O1] [OpenTelemetry JS resources](https://opentelemetry.io/docs/languages/js/resources/)
- [O2] [OpenTelemetry service attributes](https://opentelemetry.io/docs/specs/semconv/registry/attributes/service/)
- [O3] [OpenTelemetry deployment attributes](https://opentelemetry.io/docs/specs/semconv/registry/attributes/deployment/)
- [O4] [OpenTelemetry VCS attributes](https://opentelemetry.io/docs/specs/semconv/registry/attributes/vcs/)
- [P1] [Pi 0.84.1 extension lifecycle docs](https://github.com/earendil-works/pi/blob/v0.84.1/packages/coding-agent/docs/extensions.md)
- [P2] [Pi 0.84.1 session API](https://github.com/earendil-works/pi/blob/v0.84.1/packages/coding-agent/docs/session-format.md)
- [F1] [`pi-langfuse` source metadata commit](https://github.com/gooyoung/pi-langfuse/commit/ea4ff094453fd9ad32845b24e23d324d9ea8256d)
- [F2] [`pi-langfuse` 1.5.12 source metadata](https://github.com/gooyoung/pi-langfuse/blob/c79c527a7294e1d4b8153525d5218e87354cbcb1/src/source-metadata.ts)
- [F3] [`pi-langfuse` 1.5.12 tool accounting](https://github.com/gooyoung/pi-langfuse/blob/c79c527a7294e1d4b8153525d5218e87354cbcb1/src/handlers/tool.ts)
- [F9] [`pi-langfuse` upstream PR #9](https://github.com/gooyoung/pi-langfuse/pull/9)
- [F10] [`pi-langfuse` upstream PR #10](https://github.com/gooyoung/pi-langfuse/pull/10)
- [F16] [`pi-langfuse` upstream PR #16](https://github.com/gooyoung/pi-langfuse/pull/16)
- [LF2] [`stvhay/pi-langfuse` PR #2](https://github.com/stvhay/pi-langfuse/pull/2)
- [LF3] [`stvhay/pi-langfuse` PR #3](https://github.com/stvhay/pi-langfuse/pull/3)
- [A25] [`pi-archimedes` upstream PR #25](https://github.com/danielcherubini/pi-archimedes/pull/25)
- [A1] [`stvhay/pi-archimedes` PR #1](https://github.com/stvhay/pi-archimedes/pull/1)
- [A2] [`stvhay/pi-archimedes` PR #2](https://github.com/stvhay/pi-archimedes/pull/2)
- [A3] [`stvhay/pi-archimedes` PR #3](https://github.com/stvhay/pi-archimedes/pull/3)

All listed URLs returned HTTP 200 and their content/API metadata matched the cited claim at audit time.
