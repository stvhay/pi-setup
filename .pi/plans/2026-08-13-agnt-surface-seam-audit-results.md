# agnt Surface and Seam Audit Results

**Issue:** pi-i233
**Source plan:** `.pi/plans/2026-08-11-agnt-surface-seam-audit-plan.md`
**Date:** 2026-08-13
**Audited commit:** `c2f3fd8`
**Decision scope:** Audit only. No migration, public-interface deletion, new tool, or instruction replacement is applied here.

## Executive decision

- Keep `agnt_lib` as deterministic domain implementation, `agnt` as human/CI/headless adapter, Pi extensions as lifecycle/UI/session/provider adapters, and typed tools as thin agent-facing adapters.
- Registered surface at audited commit: **22 top-level `agnt` keys**, **56 leaf CLI command paths** plus four `gateway` payload operations, **13 repository-owned/configured Archimedes typed tools**, and **22 extension slash commands**.
- Current deployed configured packages add **5 typed tools** (`recall` and four BetterWright tools), for **18 active custom typed tools** in this session. Core Pi `read`/`bash` and other platform built-ins are outside repository registration; overridden `write`/`edit` are included.
- Add **no new typed tools**. Existing `subagent`, durable decision tools, `ticket_gateway`, and `handoff_bead` already cover justified schema/UI/session seams. Route→subagent, direct lifecycle, and runtime-path/provider-circuit proposals do not justify another model-facing adapter.
- Delete candidate: `agnt review summary`. It is behavior-identical to `review validate` (`pi/agent/bin/agnt_lib/review.py:199-230`) and the review skill currently runs both.
- Delete candidate: `agnt work next`. It is a caller-free wrapper around ready-work selection; direct workflow uses `bd ready`, and handoff uses the stricter `work handoff-check`.
- Deepening candidate: require `work direct-closeout ... --outcome success` and record that explicit success internally. Keep `agnt improve outcome` for partial/failure/unclear/manual recording. Never infer or default success. This removes one ordering invariant from model instructions without adding a tool or weakening outcome semantics.
- Safe compact instruction draft reduces global `pi/agent/AGENTS.md` from **103 lines / 10,739 characters** to **44 lines / 7,342 characters**: **59 lines and 3,397 characters (31.6%)**. With unchanged project `AGENTS.md`, loaded pair falls from **176 lines / 15,784 characters** to **117 lines / 12,387 characters**: **21.5% fewer characters**.
- Configured unpinned package versions make external tool/command inventory time-dependent. Runtime observed BetterWright `1.8.2`, Caveman `1.0.8`, and Ponytail `2ed6c52`, while `docs/extension-web-compatibility.md` names older snapshots. Use version-neutral wording or explicitly label observations. __keep rolling releases of unpinned packages and clarify in documentation.__

## Method and scope

### Sources

Canonical tracked evidence:

- `pi/agent/bin/agnt:53-94`
- `pi/agent/bin/agnt_lib/*.py`
- `pi/agent/extensions/*.ts`
- `pi/agent/extensions/lib/*.ts`
- `forks/pi-archimedes/{meta,packages}/**`
- `pi/agent/settings.json`
- `pi/agent/AGENTS.md`, project `AGENTS.md`, `pi/agent/bin/README.md`
- `scripts/`, `.github/workflows/ci.yml`, `tests/`, and active docs

Deployed package source was read only to close the configured-package tool gap. It is runtime evidence, not repository authority:

- `~/.pi/agent/npm/node_modules/{betterwright,pi-observational-memory,pi-caveman,pi-langfuse,pi-archimedes}`
- `~/.pi/agent/git/github.com/DietrichGebert/ponytail`

No prior session transcript, unrelated Bead, or private historical artifact was inspected.

### Classification meanings

- `keep CLI-only`: public operator/CI/headless interface; no concrete typed-tool benefit.
- `dual CLI+tool`: deterministic Python interface has a concrete CLI plus Pi extension/tool adapter.
- `tool/extension-only`: capability depends on Pi UI/session/provider/process lifecycle and needs no CLI.
- `internal-only`: implementation earns locality behind another interface.
- `merge/deepen`: interface exposes ordering or duplicate knowledge that should move behind a smaller interface.
- `delete`: capability has no distinct behavior or justified caller.

### Caller evidence index

| Caller class | Exact evidence |
|---|---|
| CI | `.github/workflows/ci.yml:35-42` runs pytest, config checks, and `agnt eval run routing-smoke|role-context-smoke`. |
| Project scripts | `scripts/check-pi-config.sh:71-78` calls `action validate`, `context-health --strict`, and `prompt inventory`; `scripts/update-pi-config.sh:460-465` calls `langfuse apply`; `scripts/eval-workflow-compliance.sh:188` imports internal `parse_pi_json_output`. |
| Extension adapters | `subagent-error-workaround.ts:524-545` calls provider circuits/runtime paths; `beads-footer.ts:64-69` calls `work status`; `bead-handoff.ts:62-66` calls `work handoff-check`; `beads-ask-bridge.ts:212-309` calls approvals; `ticket-gateway.ts:39-40` calls gateway; `guidance-edit-guard.ts:91-108` calls context-health; `langfuse-config-env.ts:46-50` calls Langfuse check. |
| Headless workers | `evals.py:14,187-229` and `runs.py:15,751-856` use internal `invoke.py`; `work.py:598-650,1438-1460` composes headless run execution. |
| Instructions/skills | `pi/agent/AGENTS.md`, `pi/agent/bin/README.md`, `pi/agent/skills/{research,dispatching-parallel-agents,requesting-code-review,dev-workflow-common,...}/SKILL.md`. |
| Tests | `tests/test_agnt.py`, `test_review.py`, `test_approvals.py`, `test_ticket_gateway.py`, `test_bead_handoff.py`, `test_process_restart.py`, `test_agent_os_compat.py`, `test_context_architecture.py`, and focused subsystem tests. |

### Exact active caller manifest

Every concrete executable adapter is listed below. For operator-only surfaces, exact active instruction/doc and principal contract-test locations are listed instead of inventing an executable caller. Historical plans and `.beads/issues.jsonl` mentions are excluded. Shorthand skill, extension, and `agnt_lib` paths in this table resolve under `pi/agent/skills/`, `pi/agent/extensions/`, and `pi/agent/bin/agnt_lib/`, respectively. Full occurrence set is reproducible with:

```bash
rg -n 'agnt (tasks|web-search|web-fetch|instructions|route|runtime-path|provider-circuit|metrics|review|eval|prompt|action|runs|work|approvals|gateway|context-health|doctor|langfuse|improve|graphify|plans-dir)' \
  pi/agent/AGENTS.md AGENTS.md README.md pi/README.md docs pi/agent/skills scripts .github pi/agent/tests tests
```

| CLI family / specialized leaf | Exact non-historical callers |
|---|---|
| `tasks` | Instructions `pi/agent/AGENTS.md:14`; user docs `README.md:77-79`; script `pi/agent/tests/agent-context-smoke.sh:12-15`; contract test `tests/test_agnt.py:265`. |
| `web-search`, `web-fetch` | Instructions `pi/agent/AGENTS.md:83-84`; skills `pi/agent/skills/research/SKILL.md:10,47-48`, `dev-workflow-common/SKILL.md:174-178`; config docs `pi/README.md:122`. No CI/extension caller. |
| `instructions` | Instructions `pi/agent/AGENTS.md:103`; user docs `README.md:80`; script `pi/agent/tests/agent-context-smoke.sh:25`; peer workflow `subagent-driven-development/SKILL.md:45,213,252,260`. |
| `route` | Instructions `pi/agent/AGENTS.md:15,43`; system docs `docs/AGNT-SYSTEM.md:23,52`; callers `dispatching-parallel-agents/SKILL.md:119`, `research/SKILL.md:48`, `requesting-code-review/SKILL.md:28,41,176`, `subagent-driven-development/SKILL.md:154,231`; contract test `tests/test_agnt.py:266`. |
| `runtime-path` | Extension `pi/agent/extensions/subagent-error-workaround.ts:542-545`; docs `docs/RUN-ARTIFACTS.md:9,24,42`, `pi/README.md:105`; review recovery `requesting-code-review/SKILL.md:149`; tests `tests/test_context_architecture.py:252-264`. |
| `provider-circuit status/open/success` | Extension `subagent-error-workaround.ts:524-540`; internal headless caller `agnt_lib/invoke.py:10,183-190`; routing caller `routing.py:14,463`; contract `tests/test_provider_circuits.py:137`. |
| `provider-circuit record` | Operator command reference `pi/agent/bin/README.md:56-63`; no extension/CI/script caller. |
| `metrics` | Smoke help `pi/agent/tests/agent-context-smoke.sh:20`; review callers `requesting-code-review/SKILL.md:207-212`, `verification-before-completion/SKILL.md:140`; operator docs `docs/SELF-IMPROVEMENT.md:87-113,134`. No extension caller. |
| `review validate` | Workflow `requesting-code-review/SKILL.md:159`; docs `docs/SELF-IMPROVEMENT.md:98`; contract `tests/test_context_architecture.py:270`, `tests/test_review.py:165`. |
| `review summary` | Workflow `requesting-code-review/SKILL.md:160`; command docs `pi/agent/bin/README.md:103`; contract `tests/test_review.py:169`. No distinct executable/CI/extension caller. |
| `eval list/run` | Instructions `pi/agent/AGENTS.md:16`; project gates `AGENTS.md:50-52`; CI `.github/workflows/ci.yml:36-37`; docs `docs/ARCHITECTURE.md:245`; contract `tests/test_agnt.py:267`. |
| `prompt inventory` | Config script `scripts/check-pi-config.sh:77`; command docs `pi/agent/bin/README.md:107-110`; no extension caller. |
| `action list/validate/render` | Config script `scripts/check-pi-config.sh:72`; run docs `docs/RUN-ARTIFACTS.md:62,189`; internal work caller `agnt_lib/work.py:14,430-596`. |
| `runs create/validate/update/invoke` | Run docs `docs/RUN-ARTIFACTS.md:177-224`; system/headless docs `docs/AGNT-SYSTEM.md:72`, `docs/ARCHITECTURE.md:209`; internal callers `actions.py:12,145`, `work.py:18,537-650`, `approvals.py:10`; tests `tests/test_runs.py`, `tests/test_agnt.py`. |
| `work direct-start/direct-closeout` | Instructions `pi/agent/AGENTS.md:39`; docs `docs/AGNT-SYSTEM.md:66-69`, `pi/README.md:75`; generated kickoff `bead-handoff.ts:51-52`; contracts `tests/test_bead_handoff.py:151,220,469-478`, `tests/test_context_architecture.py:445,541-542`. |
| `work status` | Extension `beads-footer.ts:64-69`; docs `pi/README.md:69`, `docs/extension-web-compatibility.md:16`; contract `tests/test_beads_footer.py:103`. |
| `work handoff-check` | Extension `bead-handoff.ts:62-81`; command docs `pi/agent/bin/README.md:159`; handoff contracts `tests/test_bead_handoff.py:181-499`. |
| `work integrate` | Project/global policy `AGENTS.md:12`, `pi/agent/AGENTS.md:50`; shared workflow `dev-workflow-common/SKILL.md:101`; worktree/development skills `using-git-worktrees/SKILL.md:23`, `subagent-driven-development/SKILL.md:90,289`; contracts `tests/test_context_architecture.py:376-387`, `tests/test_integration.py`. |
| `work next` | Command docs `pi/agent/bin/README.md:164`; command/parser tests in `tests/test_agnt.py`. No instruction, extension, script, CI, or active workflow caller. |
| `work plan/tree/start/run/finish` | Accepted optional workflow `docs/ORCHESTRATION-LOOP.md:23-24`; exact syntax/effects `docs/RUN-ARTIFACTS.md:233-262`; system/headless docs `docs/AGNT-SYSTEM.md:72`, `docs/ARCHITECTURE.md:204-209`; tests `tests/test_agnt.py`, `tests/test_runs.py`. Gateway also calls tree domain logic at `gateway.py:143-147`. |
| `work audit/health/maintenance` | Architecture `docs/ARCHITECTURE.md:232,259`; self-improvement workflow `docs/SELF-IMPROVEMENT.md:358-361`; run docs `docs/RUN-ARTIFACTS.md:262`; tests `tests/test_agnt.py`, `tests/test_health.py`, `tests/test_maintenance.py`. |
| `approvals request/resolve` | Extension argument builders/calls `beads-ask-bridge.ts:88-121,212-309`; architecture `docs/ARCHITECTURE.md:207`; contracts `tests/test_approvals.py:479-656`. |
| `gateway` | Extension `ticket-gateway.ts:39-40,80-113`; architecture `docs/ARCHITECTURE.md:207`; contracts `tests/test_ticket_gateway.py:27-129`. |
| `context-health` | Instructions `pi/agent/AGENTS.md:17`; config script `scripts/check-pi-config.sh:73`; extension scanner `guidance-edit-guard.ts:91-108`; skill gate `skill-creator/SKILL.md:139`; contract `tests/test_agnt.py:268`. |
| `doctor` | Instructions `pi/agent/AGENTS.md:18,24-32`; user docs `README.md:76`; internal dispatch preflight `work.py:15,1427-1434`; contract `tests/test_agnt.py:269`. |
| `langfuse check/apply` | Startup extension `langfuse-config-env.ts:46-50`; deployment script `scripts/update-pi-config.sh:460-465`; user docs `README.md:71`, `pi/README.md:105`; evaluator tests `tests/test_langfuse_evaluators.py`. |
| `improve` | Direct workflow `pi/agent/AGENTS.md:39,92`, `dev-workflow-common/SKILL.md:136`; system docs `docs/AGNT-SYSTEM.md:69`; exact operator workflow `docs/SELF-IMPROVEMENT.md:63,139-146,302-304`; retrospective `retrospective/SKILL.md:129`; tests `tests/test_improvement.py`. |
| `graphify` | Instructions `pi/agent/AGENTS.md:91`; workflow `graphify/SKILL.md:13-112`; architecture callers `systematic-debugging/SKILL.md:120`, `writing-plans/SKILL.md:61`, `dev-workflow-common/SKILL.md:38-40`; contract `tests/test_context_architecture.py:77`. |
| `plans-dir` | Instructions `pi/agent/AGENTS.md:19`; skills `dev-workflow-common/SKILL.md:144`, `brainstorming/SKILL.md:76`, `writing-plans/SKILL.md:29`, `executing-plans/SKILL.md:60`, `retrospective/SKILL.md:65`; contract `tests/test_agnt.py:270`. |

## CLI caller/effect/classification matrix

All 22 top-level keys in `pi/agent/bin/agnt:55-76` and every registered leaf path are listed below. `gateway` operations are payload-dispatched rather than argparse subcommands.

| Command path(s) | Implementation | Inputs, outputs, effects, environment, approval | Caller summary (exact locations above) | Classification |
|---|---|---|---|---|
| `tasks [--models]` | `tasks.py:35-73` | Reads tracked routing-task frontmatter; text table. | Agent smoke test, helper instructions, command docs. | keep CLI-only |
| `web-search` | `agnt:56` → `bin/web-search` | Network read through configured `SEARXNG_URL`; text/JSON. | Research skill and docs; no extension/CI caller. | keep CLI-only |
| `web-fetch` | `agnt:57` → `bin/web-fetch` | Network read of caller URL; bounded text/raw output. | Research skill and docs; no extension/CI caller. | keep CLI-only |
| `instructions` | `agnt:39-40,58` → `bin/agent-instructions` | Reads/composes global/project/model/role context; `--check` validates. | Agent context smoke test, peer/role workflows, docs. | keep CLI-only |
| `route` | `routing.py:708-755` | Reads catalog/settings/tasks/metrics/circuit state; JSON selection. Circuit expiry may lazily update private state. No model call. | Delegation/review/research skills and evals. | keep CLI-only |
| `runtime-path` | `runtime_paths.py:92-137` | Validates kind, proves ignored/untracked path, and **creates** mode-0700 private directory; JSON path. | `subagent-error-workaround.ts:542-545`; Python metrics/runs/provider modules. | dual CLI+tool |
| `provider-circuit status`, `provider-circuit open`, `provider-circuit success` | `provider_circuits.py:170-291` | Reads or lock-serializes private mode-0600 state; `status` may prune expired entries; `open/success` mutate. | `subagent-error-workaround.ts:524-540`; `invoke.py:10`; routing. | dual CLI+tool |
| `provider-circuit record` | same | Reads bounded error from stdin, classifies it, and may open private circuit. | Operator/docs only. | keep CLI-only |
| `metrics status` | `metrics.py:552-579` | Reads private pending telemetry; JSON summary. | Smoke checks/docs/skills. | keep CLI-only |
| `metrics annotate`, `metrics consolidate` | `metrics.py:580-671` | Append private annotation/global telemetry; consolidate moves raw records and optional `--stage` runs `git add`. | Review/verification skills and docs. | keep CLI-only |
| `metrics reset`, `metrics prune` | `metrics.py:672-693` | Deletes pending files or consumed telemetry directory. Consequential local cleanup; CLI authorization applies. | Operator docs/tests only. | keep CLI-only |
| `review validate` | `review.py:199-230` | Reads findings JSON, validates, and emits validation plus summary. | Requesting-code-review skill, self-improvement docs, tests. | keep CLI-only |
| `review summary` | same | Exact same control flow and payload as `review validate`; action only changes argparse program label. | Requesting-code-review skill runs it immediately after validate; tests/docs. | delete |
| `eval list` | `evals.py:187-209` | Reads tracked eval definitions; JSON. | Instructions/docs. | keep CLI-only |
| `eval run` | `evals.py:210-229` | Creates output directory/result even in dry-run; route/instruction evals run helpers, invoke evals may call providers and write metrics. | CI routing/role smoke commands; docs/tests. | keep CLI-only |
| `prompt inventory` | `prompt.py:46-67` | Reads tracked instruction/prompt artifacts; JSON/paths. | `scripts/check-pi-config.sh:77`; docs. | keep CLI-only |
| `action list`, `validate` | `actions.py:100-132` | Reads/validates action/task/skill/role/effect references. | `scripts/check-pi-config.sh:72`; work internals/docs. | keep CLI-only |
| `action render` | `actions.py:133-165` | `--dry-run` reads only; otherwise creates private run bundle. | Optional orchestration docs/tests. | keep CLI-only |
| `runs validate` | `runs.py:751-826` | Reads/validates bundle; optional Bead existence queries. | Optional orchestration docs/tests. | keep CLI-only |
| `runs create`, `runs update` | `runs.py:751-842` | Creates or updates private invocation/result bundle. | `actions.py`, approvals/work internals, docs/tests. | keep CLI-only |
| `runs invoke` | `runs.py:843-856` | Calls provider through internal headless Pi, writes response/stderr/metrics/result artifacts. | Optional artifact-backed headless workflow. | keep CLI-only |
| `work direct-start` | `work.py:762-820,1235-1237,1350-1353` | Reads Bead, optional explicit claim mutates Beads, links private session; JSON staged result. | Global workflow instructions; handoff kickoff text; tests. | keep CLI-only |
| `work status` | `work.py:822-894,1238-1239,1354-1365` | Reads canonical in-progress Beads and bounded session correlation. | `beads-footer.ts:64-69`. | dual CLI+tool |
| `work direct-closeout` + successful `improve outcome` | `work.py:966-1230`; `improvement.py:2811-2860` | Current two-command invariant records success, verifies clean tracked state, closes Bead, exports/verifies JSONL, stages/commits only portable Beads state. | Global workflow instructions/tests. | merge/deepen |
| `work integrate` | `work.py:1243-1247,1366-1382`; `integration.py` | One exact preapproved local merge under target-ref lock; Git mutation; abort/fail closed. | Shared workflow skill/docs/tests. | keep CLI-only |
| `work handoff-check` | `work.py:1079-1148,1248-1250,1383-1386` | Reads session outcome/source closeout and `bd ready`; no process replacement. | `bead-handoff.ts:62-81`. | dual CLI+tool |
| `work next` | `work.py:1251-1252,1387-1397` | Reads `bd ready`, returns first non-epic item. No distinct safety or caller. | Command docs/tests only; direct workflow uses `bd ready`; handoff uses `handoff-check`. | delete |
| `work plan` | `work.py:1253-1257,1398-1412` | Required `--dry-run`; reads Bead/action/routing and emits dispatch plan. | Optional orchestration docs. | keep CLI-only |
| `work tree` | `work.py:198-305,1258-1263,1413-1434` | Reads Beads graph, metadata, and private run refs. | `gateway.py:143-147`; optional orchestration docs. | dual CLI+tool |
| `work start` | `work.py:537-596,1264-1271,1435-1458` | Dry-run or private bundle creation; `--claim` alone mutates Bead. | Optional orchestration docs/tests. | keep CLI-only |
| `work run` | `work.py:598-650,1272-1283,1459-1496` | Dry-run or route→headless invoke→artifacts; optional claim/close under checks; provider effects/cost. | Optional orchestration docs/tests. | keep CLI-only |
| `work audit`, `work health` | `work.py:358-428,1284-1293,1497-1530`; `health.py` | Read-only queue/rail-guard checks; health may query Beads/Git/private runs. | Optional orchestration docs/tests. | keep CLI-only |
| `work maintenance due` | `work.py:1294-1300,1497-1510`; `maintenance.py` | Reads Beads/Git/runs/health/context/Langfuse signals. | Self-improvement docs/tests. | keep CLI-only |
| `work maintenance create-beads` | `work.py:1301-1307,1511-1529` | Dry-run by default; exact `--apply` creates maintenance Beads. | Self-improvement docs/tests. | keep CLI-only |
| `work finish` | `work.py:716-760,1308-1316,1531-1547` | Updates run result; optional close mutates Beads only after status/evidence/ref/check gates. | Optional orchestration docs/tests. | keep CLI-only |
| `approvals request`, `approvals resolve` | `approvals.py:158-374,401-478` | Creates/resolves durable Beads decision/blocker and optional run refs; approval/answer provenance validation. | `beads-ask-bridge.ts:212-309`. | dual CLI+tool |
| `gateway` operation `list`, `show`, `tree` | `gateway.py:116-147,189-241` | Strict enum payload; reads Beads/run refs; rejects shell-like keys. | `ticket-gateway.ts:39-40,80-113`; `/work`. | dual CLI+tool |
| `gateway` operation `create_draft` | `gateway.py:149-186` | Strict structured Bead creation; forces draft/gateway labels and rejects caller-supplied approval. | `ticket_gateway`; tests. | dual CLI+tool |
| `context-health` | `context_health.py:271-305` | Reads active context or stdin/file projection; strict exit on failures. | `guidance-edit-guard.ts:91-108`; config script; skills/tests. | dual CLI+tool |
| `doctor [node]` | `doctor.py:393-438` | Read-only environment/config/command checks; redacted presence evidence. | Workflow instructions; `work run --preflight` calls domain function; docs/tests. | keep CLI-only |
| `langfuse check` | `langfuse.py:359-373` | Authenticated remote read/compare of evaluator/rule state. | `langfuse-config-env.ts:46-50`; deployment script/docs. | dual CLI+tool |
| `langfuse apply` | same | Authenticated remote create/update; does not delete unmanaged resources. Requires deployment/remote-write authority. | `scripts/update-pi-config.sh`; operator docs. | keep CLI-only |
| `improve link` | `improvement.py:2808-2813,2861-2882` | Writes private session↔public Bead correlation after conflict checks. | `work direct-start` domain composition; docs/tests. | keep CLI-only |
| `improve scan` | `improvement.py:2800-2807,2950-2962` | Authenticated Langfuse reads; dry-run no write, otherwise private packet write. | Self-improvement docs/tests. | keep CLI-only |
| `improve review` | `improvement.py:2815-2819,2918-2949` | Preview validates private decisions; `--apply` writes private markers/monitoring. | Self-improvement docs/tests. | keep CLI-only |
| `improve promote` | `improvement.py:2820-2826,2883-2917` | Preview by default; `--apply` requires exact durable approval and creates public-safe Bead. | Self-improvement docs/tests. | keep CLI-only |
| `graphify [ARGS...]` | `agnt:43-50,75` | External Graphify passthrough; read operations vary; native hook install/uninstall remains approval-gated. | Graphify/design/debug/planning skills. | keep CLI-only |
| `plans-dir` | `runtime_paths.py:115-124` | Resolves and **creates** active `.pi/plans` or override directory. | Planning/design/documentation skills. | keep CLI-only |

### Headless and CI boundaries retained

- CI depends on `eval run`; scripts depend on `action validate`, `context-health`, and `prompt inventory`.
- Internal eval/run workers need `invoke.py` because they operate outside a live Pi tool context.
- Beads-backed commands require repository context and working `bd`/`beads`.
- Web helpers require network and `SEARXNG_URL`; Langfuse commands require private credentials; model-invoking commands require providers and can incur cost.
- Graphify needs installed `graphify` or `uv`; process-replacement tools are not substitutes because they require persisted interactive TUI.
- Deletion recommendations do not remove any CI, script, extension, or internal headless caller.

## Typed Pi tool matrix

### Repository-owned and configured Archimedes tools (13)

| Tool | Registration/interface | Effects and environment | Caller evidence | Classification |
|---|---|---|---|---|
| `subagent` | `archimedes.ts:420-440` wraps fork `subagent/src/index.ts:94` | Child provider/session/tool execution; typed access, mode, output contract, and metered-policy checks. | Model dispatch; delegation skills/instructions; extensive adapter tests. | tool/extension-only |
| `ask` | `archimedes.ts:443-489` wraps fork `ask/src/index.ts:283` | TUI/RPC/headless question UI; explicit single/multi and custom input; no durable state. | Model clarification; prompt guidelines/tests. | tool/extension-only |
| `list_agents` | fork `subagent/src/index.ts:370-386` | Reads agent configs from cwd; formatted list. | Model discovery before named delegation. | tool/extension-only |
| `manage_todo_list` | fork `todo/src/index.ts:74`; tool schema in package | Session/UI todo state only. | Model complex-task tracking; Agent OS widget adapter. | tool/extension-only |
| `write` | fork `diff/src/tools/write.ts:24` | Delegates filesystem write to Pi SDK, adds diff details/rendering. Normal workspace authority applies. | Built-in model file workflow. | tool/extension-only |
| `edit` | fork `diff/src/tools/edit.ts:44` | Delegates exact replacements to Pi SDK, adds diff details/rendering. | Built-in model file workflow. | tool/extension-only |
| `handoff_bead` | `bead-handoff.ts:145-172` | TUI-only persisted-session staging and process replacement after Python preflight; terminates current process. | Global closeout instructions and slash-command twin. | tool/extension-only |
| `ticket_question` | `beads-ask-bridge.ts:199-237` | Creates Beads blocker before optional UI; persists structured answer. | Durable blocker guidance. | dual CLI+tool |
| `ticket_approval` | `beads-ask-bridge.ts:239-272` | Creates durable approval before optional UI confirmation; consequential action remains blocked until resolution. | Approval guidance. | dual CLI+tool |
| `ticket_decision_resolve` | `beads-ask-bridge.ts:274-319` | Human UI confirmation for approval/answer; records final durable outcome. | Durable resumption/decision flow. | dual CLI+tool |
| `ticket_gateway` | `ticket-gateway.ts:80-98` | Closed schema for list/show/tree/create_draft; delegates Python validation/effects. | Opt-in structured orchestration. | dual CLI+tool |
| `nvim` | `nvim.ts:32-47` | TUI-only safe relative path, foreground editor, exact session resume. | User/model editor request and slash-command twin. | tool/extension-only |
| `restart_pi` | `process-restart.ts:65-88` | TUI-only process replacement; optional shell command has `bash` authority. | Recovery/config workflows and slash-command twin. | tool/extension-only |

### Configured external-package tools observed in deployed runtime (5)

Tracked settings load these packages but do not vendor their registration source. Current runtime evidence is therefore observational and version-specific.

| Tool | Observed source | Effects and environment | Caller evidence | Classification |
|---|---|---|---|---|
| `recall` | `pi-observational-memory@3.0.3/src/tools/recall-observation.ts:482` | Reads exact observation/reflection source from current session branch by validated 12-char ID; no semantic search. | Model tool dispatch; package-owned prompt guidelines at `recall-observation.ts:445-457`; no tracked repo/CI/headless caller. | tool/extension-only |
| `browser` | `betterwright@1.8.2/dist/src/pi-extension.js:622` | Policy-guarded persistent browser; external navigation and ordinary authorized mutations. | Model tool dispatch; package injects browser system guidance at `pi-extension.js:708`; no tracked repo/CI/headless caller. | tool/extension-only |
| `browser_login` | same `:636` | Secret-contained credential fill/generation/submission; pending generated credential needs visible verification before commit. | Model tool dispatch under BetterWright credential option; no tracked repo/CI/headless caller. | tool/extension-only |
| `browser_evidence` | same `:672` | Session checklist state and proof screenshots/artifacts. | Model tool dispatch plus package prompt guidelines; no tracked repo/CI/headless caller. | tool/extension-only |
| `browser_download` | same `:685` | Remote file save; host policy and interactive approval when configured `ask`. | Model tool dispatch under host download policy; no tracked repo/CI/headless caller. | tool/extension-only |

No repository CLI adapter is justified by a tracked or headless caller for these package-owned capabilities. Core Pi tools remain platform interfaces and were not classified as repository seams.

## Extension slash-command matrix (22)

| Command(s) | Registration | Effects/environment | Classification |
|---|---|---|---|
| `/reload` | `agent-os-compat.ts:153` | RPC-only wait-idle and Pi resource reload. | tool/extension-only |
| `/agent-os-package` | `agent-os-compat.ts:163` | RPC-only trusted project package install/remove/update after browser-side approval; reloads after success. | tool/extension-only |
| `/handoff-bead` | `bead-handoff.ts:136` | Same TUI lifecycle as `handoff_bead`. | tool/extension-only |
| `/work` | `ticket-gateway.ts:100` | Gateway list/tree plus UI widget/notification. | dual CLI+tool |
| `/nvim` | `nvim.ts:27` | Same lifecycle as `nvim` tool. | tool/extension-only |
| `/restart` | `process-restart.ts:58` | Same lifecycle/authority as `restart_pi`. | tool/extension-only |
| `/archimedes` | fork `meta/src/index.ts:97` | TUI settings UI. | tool/extension-only |
| `/agents` | fork `subagent/src/index.ts:447` | TUI agent manager. | tool/extension-only |
| `/todos` | fork `todo/src/index.ts:77` | Session todo widget/toggle/clear. | tool/extension-only |
| `/om:view`, `/om:status` | `pi-observational-memory@3.0.3/src/commands/{view,status}.ts` | Session-memory presentation; view optionally copies to clipboard. | tool/extension-only |
| `/langfuse-setup`, `/langfuse-test`, `/langfuse-status`, `/langfuse-privacy` | `pi-langfuse@1.5.12/index.ts:49-70`, composed by `langfuse-config-env.ts` | TUI config/test/status/privacy for tracing. Not equivalent to evaluator-sync `agnt langfuse`. | tool/extension-only |
| `/caveman` | deployed `pi-caveman@1.0.8/extensions/caveman.ts:307` | Session communication-mode state/UI. | tool/extension-only |
| `/ponytail`, `/ponytail-review`, `/ponytail-audit`, `/ponytail-gain`, `/ponytail-debt`, `/ponytail-help` | deployed Ponytail `2ed6c52/pi-extension/index.js:114-169` | Session simplification-mode state and package skill loading. | tool/extension-only |

## High-frequency workflow decisions

| Workflow | Current interface | Decision | Why |
|---|---|---|---|
| route → subagent | `agnt route` then typed `subagent` | Keep split; no `route_and_subagent` tool. | Python owns deterministic routing/headless evidence; Archimedes owns provider/session execution. No measured copy-error rate justifies another wrapper. Route JSON already supplies typed fields and retained evidence. |
| direct start → outcome → closeout → handoff | CLI start/outcome/closeout plus typed handoff | Deepen only by adding required `--outcome success` to CLI closeout; do not infer success or add mutation tool. | Current closeout accepts any recorded outcome; handoff separately requires success (`work.py:784-785`). A required literal success argument can preserve explicit semantics while moving its recording behind closeout. Partial/failure/unclear remain `improve outcome`; process replacement remains `handoff_bead`. |
| ticket list/show/tree/draft + durable decisions | `ticket_gateway` plus three decision tools | Keep current surfaces. | Gateway enum schema and decision UI/provenance are distinct. Combining them would create conditional schema and weaken approval semantics. |
| runtime paths/provider circuits | Extensions call internal `agnt` commands | Keep non-model-facing. | Python hides path safety, permissions, locking, TTL, classification, and redaction. A typed model tool adds no caller value and would expose private maintenance. |
| Nvim/restart | Separate semantic tools sharing process-replacement helper | Keep. | `nvim` provides safer path-only intent; `restart_pi` retains general recovery command. Shared implementation already removes duplication. |
| transient vs durable questions | `ask` vs `ticket_question`/approval/resolve | Keep. | Session-only UI and durable blocker/approval semantics are different interfaces. |

## `agnt_lib` deletion test (25 modules)

| Module(s) | Classification | Deletion result and recommendation |
|---|---|---|
| `__init__.py`, `core.py` | internal-only | Package marker plus constants/process helpers used across most modules. Deletion spreads imports and error/process behavior. Keep. |
| `tasks.py`, `routing.py` | internal-only | Tasks feed routing, evals, runs, and work. Deletion duplicates catalog/task policy. Keep Python implementation. |
| `runtime_paths.py` | dual CLI+tool | Used by metrics, runs, provider circuits, and extension artifact resolution. Deletion spreads Git-ignore/symlink/permission logic. Keep. |
| `provider_circuits.py` | dual CLI+tool | Used by routing, invoke, and extension observer. Deletion duplicates lock/TTL/classification state. Keep. |
| `metrics.py`, `review.py` | internal-only | Metrics serves routing/invoke/runs/evals/improvement; review feeds metrics annotation. Delete only duplicate `review summary` adapter, not module. |
| `invoke.py`, `runs.py`, `evals.py` | internal-only | Shared headless worker and artifact protocol used outside live Pi context. Deletion spreads provider/metric/bundle logic. Keep. |
| `prompt.py`, `actions.py` | internal-only | Prompt inventory is a config-script gate; actions feed work and runs. Keep. |
| `work.py` | merge/deepen | Central direct and optional artifact workflow. Keep implementation, delete shallow `next`, and let direct closeout record only a required explicit `--outcome success`; never infer/default success. Do not expose new typed mutation facade. |
| `approvals.py` | dual CLI+tool | One durable validation/effect implementation behind three UI tools. Deletion duplicates Beads/run/provenance logic. Keep. |
| `gateway.py` | dual CLI+tool | One strict payload implementation behind CLI/tool/`/work`. Deletion spreads shell-key and approval protections. Keep. |
| `orchestration.py` | internal-only | Metadata validator shared by work/gateway. Deletion duplicates policy. Keep. |
| `health.py`, `maintenance.py` | internal-only | Work and maintenance compose rail guards/cadence. Deletion spreads checks and due-state logic. Keep. |
| `integration.py`, `worktree_policy.py` | internal-only | Lock/merge transaction and worktree safety are high-risk shared policy. Keep internal; never duplicate in TypeScript. |
| `doctor.py`, `context_health.py` | internal-only / dual CLI+tool | Doctor supports CLI/work preflight; context-health also serves edit guard. Both earn locality. |
| `langfuse.py`, `improvement.py` | internal-only | Remote evaluator sync plus private telemetry/promotion state machines. Keep CLI/internal; do not add model-facing tools. |

## Local extension deletion test (all 16 source files)

| Extension/module | Classification | Deletion result and recommendation |
|---|---|---|
| `agent-os-compat.ts` | tool/extension-only | Concrete RPC package/reload/progress adapter. Keep while Agent OS RPC is supported. |
| `archimedes.ts` | tool/extension-only | Preserves upstream tool behavior while adding RPC ask and delegation policy/schema. Deletion loses required portability/policy; no Python logic should move here. |
| `bead-handoff.ts` | tool/extension-only | Only module owning TUI session staging/process handoff. Keep. |
| `beads-ask-bridge.ts` | dual CLI+tool | Thin UI/provenance adapter over approvals. Keep. |
| `beads-footer.ts` | tool/extension-only | Presentation-only concrete caller of work status. Keep. |
| `guidance-edit-guard.ts` | tool/extension-only | Edit lifecycle adapter over Python scanner. Keep; its stdin subprocess path is not duplicated domain logic. |
| `langfuse-config-env.ts` | tool/extension-only | Startup/env/package composition and telemetry alias lifecycle. Keep. |
| `nvim.ts` | tool/extension-only | Small semantic adapter over shared restart implementation. Keep. |
| `ponytail-skill-input.ts` | tool/extension-only | Restores explicit package skill invocation because package skills are filtered from discovery. Keep while that config remains. |
| `process-restart.ts` | tool/extension-only | TUI process replacement/shell relay. Keep. |
| `subagent-error-workaround.ts` | tool/extension-only | Provider circuit, private artifacts, metrics, termination evidence, and Langfuse projection adapter. Despite legacy name, deletion spreads substantial runtime logic. Keep; rename/split only with a concrete maintenance problem. |
| `ticket-gateway.ts` | dual CLI+tool | Thin strict schema/UI adapter over Python gateway. Keep. |
| `zz-output-redaction.ts` | tool/extension-only | Shared credential-output security boundary. Keep. |
| `lib/process-replacement.ts` | internal-only | Shared by restart and handoff; two real callers justify seam. Keep. |
| `lib/run-agnt-json.ts` | internal-only | Shared by approvals, handoff, gateway, footer, and observer. Deletion spreads subprocess/abort/JSON error handling. Keep. |
| `lib/runtime-artifacts.ts` | internal-only | Hides private-directory, atomic-write, permission, and identity invariants. Keep despite one production caller; deletion moves security complexity into 999-line observer. |

No whole `agnt_lib` or extension module passes safe deletion test.

## Compact target instruction draft

Counting method: Python `len(text.splitlines())` and `len(text)` on UTF-8-decoded Markdown, with one normal trailing LF in current and target files. Current pair is full `pi/agent/AGENTS.md` plus project `AGENTS.md`; no README or tool-schema text is counted.

```md
# Tools

- Use `rg PATTERN [PATH]` for search, `ast-grep --pattern '<code>' --lang <lang>` for structural search, and `nanobanana -o OUT.png <prompt>` for image generation when `GEMINI_API_KEY` exists.

# Agent helper

Use `~/.pi/agent/bin/agnt` as deterministic human/CI/headless adapter. Keep deterministic domain logic in `agnt_lib`; extensions own Pi lifecycle, UI, session, and provider integration; typed tools stay thin. Do not duplicate domain logic. Exact syntax lives in `~/.pi/agent/bin/README.md`; inspect `agnt -h` or command help on demand.

Common discovery: `agnt tasks --models`, `agnt route --task TASK --risk medium --budget balanced`, `agnt eval list`, `agnt context-health`, `agnt doctor --json`, and `agnt plans-dir`. Prefer deterministic helpers and evals over prompt procedures.

# Workflow

- Work directly in current Pi session by default. Batch independent reads; serialize mutations, approvals, and safety gates. Update progress at phase boundaries.
- After repeated unexpected tool, provider, environment, Node/npm, Docker, or Beads failures, stop retrying and run read-only `agnt doctor --json`; do not alter shell startup or home-managed config without approval.
- Before repository code changes, run `bd prime` and `bd ready`, then `agnt work direct-start <id> [--claim]`. It validates/shows, claims only with `--claim`, and links one session to one Bead without run bundles/worktrees.
- Close direct work only after committing task-owned changes: run `agnt improve outcome <id> <success|partial|failure|unclear>`, then `agnt work direct-closeout <id> --reason "<reason>"`. Closeout requires matching session ownership/outcome and no tracked non-Beads changes; it closes, exports/verifies `.beads/issues.jsonl`, commits only portable Beads state, and never pushes. Preserve bounded objective, decisions, constraints, blockers, verification, and next-work refs in Beads or exact tracked/private artifacts.
- After successful closeout, call `handoff_bead` without target; it auto-selects sole ready non-epic work or asks once, then starts fresh parent-linked session containing only referenced state. Explicit target is allowed only from persisted unassigned TUI or after successful closeout. Non-success/partial/failed closeout stops; `/new` is fallback.
- Documentation-only/read-only work may proceed without Bead unless project policy says otherwise. Store useful designs/plans under project `.pi/plans/`; observational memory stays advisory until promoted.
- Prefer exact paths and `rg`, `find`, `git grep`, `git diff`, and `read` over pasted context. Query `graphify-out/graph.json` first for architecture/dependency work when present, then verify source.
- Delegate independent read-only work when useful: run `agnt route --access repository`, then unnamed `subagent` with route-generated model/mode/access/thinking; repository access is agentic. Self-contained cold packets use `--access self-contained` and one-shot mode; use `tasks` for parallel work.
- Subscription-backed peers normally omit request/token/cost caps. Add caps only for explicit bounded experiments or liveness risk. Use metered OpenRouter only for bounded diversity, specialist review, or explicit canary work, always in fresh subagents; metered repository inspection requires route-generated justification, estimates, aggregate budget, and per-child limits. Keep subscription OpenAI/Codex as root/default controller and verify peer claims against source/tests.
- Ticket gateway, run artifacts, worktree-per-epic dispatch, and strict orchestration are opt-in; ordinary coding does not require them.
- Unless narrowed, implementation approval includes staging and one local atomic commit of task-owned changes under shared completion contract. Beads sync wording does not govern repository Git authority.
- Initial implementation approval may cover exact reversible named local branches/worktrees, post-integration removal, and staged tracked/config-controlled deletions. Before cleanup/deletion, show exact paths/branches and commit-SHA recovery. Stop on unrelated changes, ambiguous ownership, untracked runtime data, backups, remote refs/deletion, force/reset/clean, or history rewrite.
- Initial implementation approval may cover one exact local `agnt work integrate` action when target checkout/branch, expected target HEAD, and source SHA are named. Helper serializes and rechecks scope, aborts conflicts, and stops on divergence; alternate integration needs approval.
- Initial implementation approval may cover one verified local-live or named test/staging deployment when it binds Bead, source-selection rule, resolved target identity, exact preview/effect bounds, verification, rollback, and stop conditions. Production, unknown/mismatched targets, secrets changes, destructive rollback, or scope/preview drift need new approval; rejection/cancellation/timeout fails closed.
- Initial implementation approval may cover one ordinary branch push after successful closeout when it binds remote/branch identity, approved base SHA, bounded candidate-selection rule, expected remote state, and final gates. First attempt consumes authority. Protected/production push, PR, force, tags, release, merge, deletion, and history rewrite remain excluded.
- Outside exact preauthorized setup, integration, cleanup, named non-production deployment, and ordinary push, require explicit approval for push, branch/worktree deletion, local merge, and deployment. Never force/reset/clean, delete Beads, alter Beads remotes/history, install hooks, remotely delete, or rewrite history.

# Human decisions

- Use transient `ask` only for current-session clarification/exploration. Set `selectionMode` and allow typed custom input.
- Use `ticket_question` only when answer must survive handoff/resumption or block a Bead; explore transiently first and persist final blocker only. Use `ticket_approval` for consequential actions with informed action/scope, consequences, reversibility, and closeout evidence, creating durable Beads blocker before UI confirmation. Approval is not question.
- With no interactive UI, never guess or answer for human; report blocked state and leave durable blocker when later resumption matters.

# Concepts and context

Keep work item/Bead, routing task, action template, skill, role, and tool/eval distinct. Routing, prompts, and roles do not replace skill methods or project gates. Beads hold durable workflow state; private run artifacts are optional evidence.

Keep root instruction files small and universal. Put model overlays under `<root-stem>.d/models/<family-or-provider/model>.md`, role overlays under `<root-stem>.d/roles/<role>.md`, and skill detail under `skills/<name>/SKILL.md` with bulky references beside it. Generate layered role/model context with `agnt instructions --context provider/model --role ROLE`; overlays may specialize but never weaken security, approval, verification, Git, or project rules. `SOUL.md` controls communication only.

# Research and learning

For cited external claims, use `agnt web-search` then `agnt web-fetch`; cite verified primary URLs, not model knowledge. Review private telemetry with `agnt improve` and promote only sanitized, human-approved findings into Beads. Load hidden `~/.pi/agent/skills/dev-workflow-common/SKILL.md` only when another skill requests it.
```

### Measurement and gate retention

| Measure | Current | Target | Reduction |
|---|---:|---:|---:|
| Global `pi/agent/AGENTS.md` lines | 103 | 44 | 59 (57.3%) |
| Global characters | 10,739 | 7,342 | 3,397 (31.6%) |
| Global + project lines | 176 | 117 | 59 (33.5%) |
| Global + project characters | 15,784 | 12,387 | 3,397 (21.5%) |

Retained explicitly:

- deterministic domain/CLI/extension/tool seam;
- operational doctor stop rule;
- Bead setup, one-session ownership, direct closeout, portable-state commit, and fresh-session handoff;
- exact repository/self-contained delegation modes, bounded OpenRouter purpose, and metered constraints;
- opt-in structured orchestration;
- task-owned commit authority and Beads-sync distinction;
- local Git setup/deletion recovery and stop conditions;
- exact integration identity/divergence gate;
- named non-production deployment identity/preview/effect/verification/rollback gate;
- ordinary push identity/base/candidate/remote/final-gate/single-attempt exclusions;
- explicit approval for other merge/push/deployment/deletion actions and force/history prohibitions;
- transient vs durable questions, selection mode/custom input, informed action/scope/consequence/reversibility/closeout preview, UI provenance, and fail-closed no-UI behavior;
- concept separation, research sourcing, context layering, and no gate weakening.

The draft passed:

```text
agnt context-health --file <draft> --path pi/agent/AGENTS.md --strict
→ passed=true, failureCount=0
```

The draft is not applied. Applying it requires separate approval plus context-architecture test updates and deterministic routing/role evals.

## Ranked bounded follow-up slices

No Beads were created. Each slice needs separate approval.

| Rank | Slice | Risk / public behavior | Exact files and checks | Expected gain |
|---:|---|---|---|---|
| 1 | Apply reviewed compact instruction draft. | Medium: changes always-loaded behavior; must re-review exact safety wording. | `pi/agent/AGENTS.md`, `tests/test_context_architecture.py`, relevant docs; `agnt context-health --strict`, instruction checks, routing/role evals, workflow tests. | 3,397 global characters (31.6%); 21.5% across current global+project pair. |
| 2 | Remove duplicate `agnt review summary`; make `review validate` documented output canonical and remove second skill invocation. | Low-medium: public alias deletion, but behavior is identical and no CI/extension/script caller exists. | `agnt_lib/review.py`, `pi/agent/bin/README.md`, `requesting-code-review/SKILL.md`, `tests/test_review.py`; focused review/context tests. | One CLI leaf, one model command, one parser branch, duplicate docs/tests. |
| 3 | Add required `--outcome success` to direct closeout and record only that explicit value internally; retain `improve outcome` for non-success/manual outcomes. Never infer/default success. | Medium-high: Beads/private telemetry/Git closeout ordering. | `agnt_lib/work.py`, `improvement.py`, `pi/agent/AGENTS.md`, command docs, `tests/test_agnt.py`, `test_improvement.py`, handoff tests; prove partial/failure/unclear cannot close or hand off. | One model ordering step removed without weakening explicit outcome semantics; no new tool. |
| 4 | Remove `agnt work next`. | Medium: documented public command deletion; no executable caller. | `agnt_lib/work.py`, command docs, related tests; preserve `select_next_ready` for `get_bead` and handoff behavior. | One shallow CLI leaf and docs burden. |
| 5 | Make configured-package compatibility matrix version-neutral or explicitly timestamped; choose whether unpinned BetterWright/Caveman/Ponytail drift is intentional. | Low docs/config decision; pinning would be separate behavior choice. | `docs/extension-web-compatibility.md`, `pi/agent/settings.json` only if pinning is approved, package tests/checks. | Removes stale exact-version claims and makes future tool audits reproducible. |

Rejected follow-ups:

- No `route_and_subagent` tool: no measured copy-error evidence; would add adapter complexity.
- No typed work mutation facade: CLI preserves headless/operator safety and avoids widening consequential effects.
- No runtime-path/provider-circuit tools: no model caller; private maintenance remains extension-internal.
- No TypeScript copy of Python work/routing/approval/gateway logic.
- No extension/module split based only on file length or legacy naming.

## Verification

Planned commands from source plan plus exact surface/count checks:

```bash
rg -n '"[a-z-]+": \(' pi/agent/bin/agnt
rg -n 'registerTool\(|registerCommand\(' pi/agent/extensions forks/pi-archimedes
rg -n '\bagnt\b|ticket_gateway|subagent|handoff_bead|restart_pi' pi/agent/AGENTS.md AGENTS.md
.venv/bin/python -m pytest tests/test_agnt.py tests/test_context_architecture.py tests/test_ticket_gateway.py
.venv/bin/python -m pytest tests/test_review.py tests/test_approvals.py tests/test_bead_handoff.py tests/test_process_restart.py tests/test_agent_os_compat.py
pi/agent/bin/agnt context-health --strict
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
```

**Verification status:** PASS at current working candidate.

- Surface coverage assertion → PASS: 56 CLI leaves, 18 custom tools, 22 slash commands, 25 `agnt_lib` modules, and 16 local extension source files all present; all six classification values present.
- Focused matrix → `269 passed in 21.60s`.
- `agnt context-health --file <draft> ... --strict` → PASS, zero failures/warnings.
- `agnt instructions <draft> --check --no-project` → PASS.
- `scripts/check-pi-config.sh` → PASS.
- `bash -n scripts/*.sh` → PASS.
- Ruff → `All checks passed!`.
- Full pytest → `774 passed in 132.52s`.
- `routing-smoke` → PASS, zero failures.
- `role-context-smoke` → PASS, zero failures.
- Current deployed `agnt context-health --strict` → PASS with one pre-existing skill-discovery budget warning (`7,889/8,000`, 111 characters remaining); no failure.
- Independent review found four initial gaps; source verification corrected all. Second verifier confirmed those fixes and requested exact caller locations. Third fresh verifier checked the completed manifest and returned PASS with no Important findings.

## Confidence and limits

**Confidence: HIGH** for tracked CLI/local-extension surfaces and classifications; **MEDIUM** for future external-package tool inventory because configured BetterWright, Caveman, and Ponytail sources are unpinned.

Limits:

- Current deployed package source confirms this session, not every future deployment.
- Static repository evidence cannot prove human/operator frequency. Documented public commands were retained unless exact duplication or a stronger existing workflow made deletion evidence concrete.
- No external telemetry was consulted; private improvement data was outside audit recovery scope.
- Core Pi built-in tools are platform interfaces, not repository registrations, and are excluded except project-overridden `write`/`edit`.
