# agnt Doctor and Lessons Implementation Plan

**Issue:** pi-wc0 — Implement agnt doctor operational preflight; pi-juc — Implement agnt lessons client for lesson server
**Design:** None; design captured in this plan from 2026-07-01 chat and `lesson-server/README.md`
**Date:** 2026-07-01
**Branch:** main

**Goal:** Add deterministic operational health checks and a first-class lessons client so agents stop safely when the harness environment is broken and can push lessons up to the central lesson server.

**Architecture:** Add two small `agnt_lib` command modules: `doctor.py` for local runtime preflight and `lessons.py` for JSONL lesson capture/sync/triage. Keep both tool-first and testable: command handlers should wrap pure report/record functions so tests can monkeypatch filesystem, environment, subprocess, and HTTP. The deployed FastAPI lesson server remains a separate spike artifact under `lesson-server/`; `agnt lessons` talks to it via `AGNT_LESSONS_URL` or a CLI `--url`.

**Acceptance Criteria:**
- [ ] `agnt doctor` emits a JSON report with schema version, overall status, checks, failures, warnings, and suggested actions.
- [ ] `agnt doctor --strict` exits nonzero for failed required checks and remains zero for warnings/degraded optional checks.
- [ ] Doctor checks cover core command availability, git/project root, Pi runtime, Beads health, Python version, Node LTS/nvm detection, provider env var presence/redaction, model catalog/settings sanity, and project verification command presence where practical.
- [ ] Node remediation suggestions respect home-management conventions and do not edit home files unless a future explicit repair command is implemented and approved.
- [ ] `agnt lessons capture` writes one JSONL lesson with UUID/date/hostname/project/project_dir provenance to a local runtime inbox.
- [ ] `agnt lessons push` posts JSONL to `/lesson`, preserves local data on failure, and archives/marks pushed records only after success.
- [ ] `agnt lessons pull` fetches `/lessons` as JSONL with filters and can write to a local inbox file.
- [ ] `agnt lessons triage` lists candidates and drafts Beads work; it creates Beads only with an explicit flag.
- [ ] Docs connect `doctor` and `lessons` to `pi/agent/bin/README.md`, `docs/SELF-IMPROVEMENT.md`, and the retrospective workflow.

**Verification Command(s):**
```bash
.venv/bin/python -m pytest tests/test_agnt.py tests/test_lesson_server.py
scripts/check-pi-config.sh
bash -n scripts/*.sh
pi/agent/bin/agnt context-health --strict
pi/agent/bin/agnt action validate
pi/agent/bin/agnt doctor --json
AGNT_LESSONS_URL=https://pi-lessons.st5ve.com pi/agent/bin/agnt lessons pull --limit 5 >/tmp/agnt-lessons-pull.jsonl
python -m json.tool /tmp/agnt-doctor-report.json >/dev/null  # if doctor output is captured there during implementation

git diff --check
```

---

## Design Decisions

### Doctor command shape

Primary commands:

```bash
agnt doctor [--json] [--strict] [--check NAME ...] [--skip NAME ...]
agnt doctor node [--json]
```

Deferred/future command, not in the first implementation unless explicitly approved:

```bash
agnt doctor repair node
```

Output report shape:

```json
{
  "schemaVersion": 1,
  "status": "failed|degraded|passed",
  "passed": false,
  "summary": {"failureCount": 1, "warningCount": 2, "checkCount": 10},
  "checks": [
    {
      "id": "node.version",
      "status": "warning",
      "severity": "medium",
      "message": "Node is not active LTS",
      "evidence": {"version": "v23.1.0", "path": "/opt/homebrew/bin/node"},
      "suggestedActions": ["nvm install --lts", "nvm alias default 'lts/*'"]
    }
  ],
  "suggestedActions": []
}
```

Statuses:

- `pass`: expected condition met.
- `warning`: optional or degraded condition; `--strict` remains zero unless warning is promoted by `--required` in a later version.
- `fail`: required condition failed; `--strict` exits nonzero.
- `skip`: check was explicitly skipped or not applicable.

### Doctor check set v1

Required/check-fail candidates:

- `command.pi`: `pi` binary exists and `pi --help` exits.
- `command.agnt`: current command path is executable.
- `python.version`: Python is >= 3.11.
- `git.root`: current directory resolves to a git root.
- `catalog.parse`: `pi/agent/catalog.json`, `models.json`, `settings.json`, and task files parse.
- `model.targets`: enabled model targets have `provider/model` shape and known catalog entries where expected.

Warning/degraded candidates:

- `command.bd`: `bd` or `beads` exists; run `bd doctor` if `.beads/` exists.
- `direnv.status`: `.envrc` exists but `DIRENV_DIR`/loaded state appears absent.
- `node.version`: node exists and is active LTS-compatible; warn if missing or non-LTS.
- `node.manager`: detect `nvm`, `fnm`, `asdf`, Homebrew, Nix shell context.
- `provider.env`: check env vars for configured providers, redacted in evidence.
- `verification.commands`: documented command binaries exist (`bash`, `pytest`, etc.) without running expensive checks.
- `docker.daemon`: if `docker-compose.yml` exists, report Docker CLI/daemon state.
- `lesson.url`: if `AGNT_LESSONS_URL` exists, check `/healthz` with short timeout.

Node/home-management policy:

1. Detect active `node --version` and path.
2. Detect manager hints in this order: Nix shell (`IN_NIX_SHELL`), direnv, `nvm`, `fnm`, `asdf`, Homebrew.
3. If non-LTS and `nvm` exists, suggest:
   - `nvm install --lts`
   - `nvm alias default 'lts/*'`
4. If a shell initialization update is needed, prefer managed conventions:
   - if `~/.local/etc/profile.d/` exists, suggest a managed snippet path such as `~/.local/etc/profile.d/pi-node-lts.sh`;
   - if chezmoi/yadm/Home Manager markers exist, do not suggest direct file mutation; identify the likely managed file;
   - otherwise suggest `.zshrc`/`.bashrc` commands, but do not perform them.
5. `agnt doctor` v1 is read-only. Any future repair mode must require explicit command invocation and write a marked, reversible block.

### Lessons command shape

Primary commands:

```bash
agnt lessons capture --summary TEXT [--kind KIND] [--area AREA] [--evidence TEXT] [--tag TAG ...] [--payload-json JSON] [--out FILE]
agnt lessons inbox [--file FILE] [--json]
agnt lessons push [--url URL] [--file FILE] [--archive-dir DIR] [--dry-run]
agnt lessons pull [--url URL] [--status STATUS] [--since ISO] [--project NAME] [--hostname NAME] [--limit N] [-o FILE]
agnt lessons triage [--file FILE] [--status new] [--draft-beads] [--create-beads]
```

Defaults:

- Local inbox: `~/.pi/lessons/inbox.jsonl` unless `AGNT_LESSONS_INBOX` is set.
- Pushed archive: `~/.pi/lessons/pushed/<timestamp>.jsonl`.
- URL: `AGNT_LESSONS_URL`, currently tested with `https://pi-lessons.st5ve.com`.
- Lessons stay runtime state until triaged into Beads or tracked config/docs changes.

Lesson JSONL schema:

```json
{
  "uuid": "generated uuid4",
  "date": "UTC ISO timestamp",
  "hostname": "socket.gethostname()",
  "project": "git-root basename or cwd basename",
  "project_dir": "git root or cwd",
  "kind": "friction|bug|improvement|preference|success|other",
  "area": "doctor|lessons|routing|provider|skill|docs|unknown",
  "summary": "required concise summary",
  "evidence": "optional redacted evidence",
  "status": "new",
  "tags": ["..."] ,
  "payload": {}
}
```

Redaction v1:

- Never read or upload arbitrary files by default.
- CLI `--evidence` and `--payload-json` are caller-provided; apply best-effort redaction for common secret patterns before writing/sending.
- Redact env-like tokens matching `*_API_KEY=...`, `Authorization: Bearer ...`, `sk-...`, `ghp_...`, `xox...`, and long high-entropy strings.
- Store original unredacted content nowhere unless a future explicit `--no-redact` exists; do not add `--no-redact` in v1.

Triage behavior:

- `triage` reads JSONL and groups by `area`/`kind`/similar summaries with a simple exact/slug heuristic in v1.
- `--draft-beads` prints `bd create` commands and markdown descriptions to stdout or `.pi/lessons/drafts/`.
- `--create-beads` is an explicit state mutation. It should create Beads with title, context, problem, suggested improvement, and evidence; no GitHub issues.
- After Beads are created, optionally patch remote lesson `status=accepted` only with a separate explicit `--patch-remote` flag in a later version.

## Task Plan

### Task 1: Finalize lesson server spike [Depends on: current dirty spike]

**Context:** The FastAPI lesson server exists under `lesson-server/`, tests pass, and remote `https://pi-lessons.st5ve.com` is smoke-tested. Before starting `agnt doctor`/`lessons`, finish or consciously keep this spike as a separate commit.

**Files:**
- Existing: `lesson-server/app/main.py`
- Existing: `lesson-server/docker-compose.yml`
- Existing: `lesson-server/README.md`
- Existing: `tests/test_lesson_server.py`
- Existing: `.gitignore`
- Existing: `.beads/issues.jsonl`

**Steps:**
1. Run focused verification for the spike.
2. Decide whether to keep local Docker stack running or stop it; do not remove volumes unless explicitly approved.
3. Commit the lesson server spike separately if committing is approved.
4. Close bead `pi-3ef` only after verification and commit policy are satisfied.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_lesson_server.py
python -m compileall -q lesson-server/app
docker compose -f lesson-server/docker-compose.yml config >/tmp/lesson-compose-config.yml
curl -fsS https://pi-lessons.st5ve.com/healthz
```

**Expected result:** Tests pass, Compose config renders, and remote health returns `{"status":"ok"}`.

### Task 2: Add `agnt doctor` report engine [Independent after Task 1 commit]

**Context:** Implement pure check/report functions before CLI wiring so tests can monkeypatch subprocess/env/path behavior.

**Files:**
- Create: `pi/agent/bin/agnt_lib/doctor.py`
- Modify: `pi/agent/bin/agnt`
- Test: `tests/test_agnt.py` or new `tests/test_doctor.py`

**Steps:**
1. Write failing tests for report schema, strict exit behavior, command check pass/fail, and redacted env evidence.
2. Implement `CheckResult`-like dictionaries, `doctor_report()`, and `cmd_doctor()`.
3. Wire `doctor` into the front controller import/command map.
4. Keep checks read-only and time-bounded.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_agnt.py tests/test_doctor.py
pi/agent/bin/agnt doctor --json >/tmp/agnt-doctor-report.json
python -m json.tool /tmp/agnt-doctor-report.json >/dev/null
```

**Expected result:** Tests pass; `agnt doctor --json` emits valid JSON with `schemaVersion: 1`.

### Task 3: Add Node LTS/nvm/home-convention checks [Depends on: Task 2]

**Context:** Node version mismatch is a known harness failure mode. The check must diagnose and suggest safe fixes without editing home files.

**Files:**
- Modify: `pi/agent/bin/agnt_lib/doctor.py`
- Test: `tests/test_doctor.py`
- Docs: `pi/agent/bin/README.md`

**Steps:**
1. Write tests for active LTS, non-LTS with nvm present, missing node, and home-management convention detection.
2. Implement semver/LTS heuristic. Prefer simple policy: major versions known active LTS in a table or env-overridable `AGNT_NODE_LTS_MAJORS`; do not require network.
3. Implement manager detection with monkeypatchable filesystem/env helpers.
4. Emit suggested actions, not mutations.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_doctor.py -k 'node or home'
pi/agent/bin/agnt doctor --check node --json
```

**Expected result:** Node scenarios produce deterministic pass/warning/fail statuses and safe suggested actions.

### Task 4: Add provider/model/project checks and invoke/work preflight hooks [Depends on: Task 2]

**Context:** Doctor should catch missing provider env vars and broken model config before workers go rogue. Integration into `invoke`/`work` should start as opt-in or warning-only to avoid breaking existing flows.

**Files:**
- Modify: `pi/agent/bin/agnt_lib/doctor.py`
- Modify: `pi/agent/bin/agnt_lib/invoke.py`
- Modify: `pi/agent/bin/agnt_lib/work.py`
- Test: `tests/test_doctor.py`, `tests/test_agnt.py`

**Steps:**
1. Add provider-env checks using configured models/providers. Redact values and report only presence/absence/source.
2. Add model target shape/catalog sanity checks.
3. Add `agnt invoke --preflight` or warning-only default when obvious provider env is missing. Avoid making ordinary help/list commands slower.
4. Add `agnt work run --preflight` or a pre-dispatch warning path.
5. Ensure peer invocation still works when preflight is skipped.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_doctor.py tests/test_agnt.py -k 'doctor or invoke or work'
pi/agent/bin/agnt doctor --json >/tmp/agnt-doctor-report.json
```

**Expected result:** Missing provider env is reported before invocation when preflight is requested; existing command behavior remains compatible.

### Task 5: Add `agnt lessons` local capture/inbox [Depends on: Task 1]

**Context:** Capture is local runtime state. It should be usable in any project even when the remote lesson server is unavailable.

**Files:**
- Create: `pi/agent/bin/agnt_lib/lessons.py`
- Modify: `pi/agent/bin/agnt`
- Test: new `tests/test_lessons.py`

**Steps:**
1. Write tests for UUID/date/provenance defaults, JSONL append, `AGNT_LESSONS_INBOX`, and redaction.
2. Implement `lesson_record()`, `redact_text()`, JSONL read/write helpers, and `cmd_lessons capture/inbox`.
3. Ensure no secrets or arbitrary files are read by default.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_lessons.py -k 'capture or inbox or redact'
AGNT_LESSONS_INBOX=/tmp/agnt-lessons-test.jsonl pi/agent/bin/agnt lessons capture --summary "test lesson" --kind smoke --area lessons
cat /tmp/agnt-lessons-test.jsonl
```

**Expected result:** One valid JSONL record is written with provenance and redacted evidence.

### Task 6: Add `agnt lessons push/pull` HTTP client [Depends on: Task 5]

**Context:** The server contract is documented in `lesson-server/README.md`: `POST /lesson` accepts JSON/JSONL and `GET /lessons` returns JSONL.

**Files:**
- Modify: `pi/agent/bin/agnt_lib/lessons.py`
- Test: `tests/test_lessons.py`
- Docs: `pi/agent/bin/README.md`

**Steps:**
1. Write tests using monkeypatched `urllib.request` or a tiny local HTTP server; do not require the production server in unit tests.
2. Implement URL resolution from `--url` or `AGNT_LESSONS_URL`.
3. Implement `push`: post JSONL to `/lesson`; on success copy records to archive and truncate or rotate the inbox only after a successful response.
4. Implement `pull`: call `/lessons` with filters and write JSONL to stdout or `-o`.
5. Add a manual smoke command for `https://pi-lessons.st5ve.com`, but keep it out of default tests.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_lessons.py -k 'push or pull'
AGNT_LESSONS_URL=https://pi-lessons.st5ve.com pi/agent/bin/agnt lessons pull --project pi-setup --limit 5 >/tmp/agnt-lessons-pull.jsonl
test -s /tmp/agnt-lessons-pull.jsonl
```

**Expected result:** HTTP behavior is unit-tested without network; manual smoke can fetch remote JSONL.

### Task 7: Add lessons triage and Beads draft/create flow [Depends on: Task 5]

**Context:** Lessons should trickle up into this repository as Beads work, not tracked raw telemetry. Beads creation is state mutation and must be explicit.

**Files:**
- Modify: `pi/agent/bin/agnt_lib/lessons.py`
- Test: `tests/test_lessons.py`
- Docs: `docs/SELF-IMPROVEMENT.md`, `pi/agent/bin/README.md`

**Steps:**
1. Write tests for grouping/listing candidate lessons and draft Beads output.
2. Implement `triage --draft-beads` to emit markdown descriptions and safe `bd create` commands.
3. Implement `triage --create-beads` with explicit flag and subprocess wrapper; unit-test by monkeypatching the runner.
4. Include provenance, problem, suggested improvement, evidence, and source UUID in Beads descriptions.
5. Do not patch remote statuses in v1 unless separately approved.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_lessons.py -k triage
pi/agent/bin/agnt lessons triage --file /tmp/agnt-lessons-pull.jsonl --draft-beads
```

**Expected result:** Draft Beads are useful, deterministic, and no Beads are created without `--create-beads`.

### Task 8: Documentation, instructions, and eval/check updates [Depends on: Tasks 2-7]

**Context:** Agents need to know when to run doctor and how lessons flow into this repo.

**Files:**
- Modify: `pi/agent/bin/README.md`
- Modify: `docs/AGNT-SYSTEM.md`
- Modify: `docs/SELF-IMPROVEMENT.md`
- Modify: `pi/agent/AGENTS.md` or relevant skill docs only if needed
- Possibly modify: `pi/agent/skills/retrospective/SKILL.md`
- Test: existing tests/evals

**Steps:**
1. Document command reference for `doctor` and `lessons`.
2. Add a self-improvement section explaining capture anywhere, push to server, triage here into Beads.
3. Add operational guidance: after repeated tool/env failures, stop and run `agnt doctor`; do not improvise.
4. Update retrospective skill to mention `agnt lessons capture` for reusable Pi config lessons, without making it mandatory.
5. Run context-health and instruction checks.

**Focused verification:**
```bash
scripts/check-pi-config.sh
pi/agent/bin/agnt context-health --strict
pi/agent/bin/agent-instructions --check
pi/agent/bin/agnt action validate
.venv/bin/python -m pytest tests/
```

**Expected result:** Docs are aligned, context checks pass, and tests pass.

## File Conflicts

| File | Tasks | Resolution |
|---|---|---|
| `pi/agent/bin/agnt` | Tasks 2, 5 | Task 5 depends on Task 2 or edits the command map after doctor is wired. |
| `pi/agent/bin/README.md` | Tasks 3, 6, 7, 8 | Do final docs pass in Task 8 after command behavior stabilizes. |
| `docs/SELF-IMPROVEMENT.md` | Task 8 | Single docs pass after implementation. |
| `tests/test_agnt.py` | Tasks 2, 4 | Prefer new `tests/test_doctor.py` to reduce churn; only touch `test_agnt.py` for front-controller integration. |

## Peer Review Notes

Useful review prompts after the plan is saved:

```bash
~/.pi/agent/bin/agnt invoke --task review openrouter-localish/google/gemma-4-31b-it .pi/plans/2026-07-01-agnt-doctor-lessons-design-plan.md
~/.pi/agent/bin/agnt invoke --task review openrouter-localish/qwen/qwen3.5-9b .pi/plans/2026-07-01-agnt-doctor-lessons-design-plan.md
```

Ask reviewers to focus on:

- whether `doctor` is too broad for v1;
- whether `lessons push` can lose records;
- redaction gaps;
- whether any command creates hidden state mutations.

## Execution Handoff

Plan saved to: `.pi/plans/2026-07-01-agnt-doctor-lessons-design-plan.md` (verify with `test -f`).
Recommended next skill: `test-driven-development` for behavior changes; `verification-before-completion` before claiming completion.
