# Pi-to-Nvim Reload Design and Implementation Plan

**Issue:** pi-tj4h — Investigate and design Pi-to-nvim reload command
**Design:** Human-approved Bead design
**Date:** 2026-08-13
**Branch:** main

**Goal:** Add a reusable command-then-resume restart path, then expose `/nvim` and agent-callable `nvim` entrypoints that run Nvim from the Pi session root and resume the exact persisted session afterward.

**Architecture:** Keep existing graceful Node process replacement. Command mode replaces the stopped Pi process with a fixed `/bin/sh` relay; the relay changes to `ctx.cwd`, runs one caller-supplied POSIX shell command in a child shell, prints its status, then `exec`s the exact Node/Pi resume argv. Nvim remains a thin extension that validates one optional relative path, safely quotes it, and calls the shared restart function. No daemon, detached process, wrapper service, package, or Pi-core change.

**Acceptance Criteria:**
- [ ] Existing `/restart` and `restart_pi` direct restart behavior remains unchanged when no command is supplied.
- [ ] `/restart -- <command>` and optional `restart_pi.command` run from `ctx.cwd`, then resume the exact session on command success, nonzero exit, or a child-only SIGINT status that leaves the relay alive.
- [ ] `/nvim` and `nvim` accept zero paths or one relative path; spaces are part of that path, not extra arguments.
- [ ] Absolute paths, NUL/CR/LF, and normalized traversal outside `ctx.cwd` fail before shutdown.
- [ ] Nvim receives `--` before any path and shell metacharacters in the path cannot become command syntax.
- [ ] Predictable pre-shutdown failures leave current Pi running; post-shutdown failures preserve exact-session recovery.
- [ ] Focused harness tests and one persisted-TTY probe demonstrate command-then-resume without a reload loop.
- [ ] Pi README and extension compatibility matrix describe the new TUI-only behavior and boundary.

**Verification Commands:**
```bash
.venv/bin/python -m pytest -p no:cacheprovider tests/test_process_restart.py
.venv/bin/python -m ruff check tests/test_process_restart.py
scripts/check-pi-config.sh
bash -n scripts/*.sh
```

---

## Current Lifecycle

1. Pi startup resolves `--session-dir`, then resolves `--session`. An argument containing `/`, `\\`, or ending in `.jsonl` is treated as a path and opened with `SessionManager.open`; using the current exact JSONL path avoids session-ID rediscovery.
2. Extension contexts expose session root as `ctx.cwd`, exact persisted JSONL path through `ctx.sessionManager.getSessionFile()`, and session storage through `getSessionDir()`.
3. `pi/agent/extensions/process-restart.ts` rejects non-TUI mode, unsupported runtime/platform, missing `process.execve`, missing Pi entrypoint, and ephemeral sessions before requesting shutdown.
4. `pi/agent/extensions/lib/process-replacement.ts` permits one pending replacement, registers one process `exit` listener, then calls `ctx.shutdown()`. A synchronous shutdown request failure removes the listener and clears pending state.
5. Interactive `ctx.shutdown()` waits for idle, drains terminal input, stops the TUI (restoring cooked terminal state), emits session shutdown through runtime disposal, and exits. The registered exit listener then calls `process.execve`.
6. Direct restart currently execs exact current Node executable, `process.execArgv`, Pi entrypoint, `--session-dir`, and exact session-file path. The replacement process opens that same JSONL and starts a new extension runtime.
7. In-memory `replacementPending` resets naturally because resumed Pi is a new process. A one-shot relay between old and new Pi therefore cannot recurse unless another command explicitly requests replacement.

`ctx.cwd` is authoritative for the session root; do not infer a Git root. The relay must explicitly `cd` to captured `ctx.cwd` rather than assume OS process cwd still matches session cwd.

## Integration Decision

Use `process-restart.ts` as the shared public seam:

- Export its restart request function and add optional command input.
- Keep `requireProcessReplacement` and `requestProcessReplacement` unchanged unless implementation tests prove a missing invariant.
- For command mode, pass a copy of the validated replacement descriptor whose executable is `/bin/sh`; pass shell relay argv separately.
- Let later `nvim.ts` import the shared function. Importing the module does not invoke its default extension factory.

Rejected extra machinery:

- Pi's external-editor shortcut edits prompt text, not an arbitrary project file.
- The upstream interactive-shell example suspends live TUI around `spawnSync`; it does not provide approved exact-session command/tool handoff.
- A daemon, tmux wrapper, or generated shell script adds lifecycle and cleanup state without improving this one-command relay.

## Generic Restart Contract

### Slash command

| Input | Result |
|---|---|
| `/restart` | Existing direct restart. |
| `/restart -- <POSIX shell command>` | Run full remainder as one shell command, then resume. |
| `/restart --` or whitespace-only command | Reject with usage; no listener or shutdown. |
| `/restart anything` | Reject; explicit `--` is required. |
| `/restart --anything` | Reject; `--` must be a standalone delimiter. |

After command delimiter, preserve command body, including spaces, quotes, shell operators, and embedded newlines. Strip only syntax-leading whitespace after delimiter. Reject all-whitespace and NUL before shutdown.

### Tool

`restart_pi` keeps a strict object schema (`additionalProperties: false`) and adds one optional `command: string` property:

- omitted: existing direct restart;
- present: same POSIX shell command path as slash command;
- empty/whitespace or NUL: reject before shutdown;
- any extra property: reject during schema validation.

Tool description/guidance must state that `restart_pi.command` is equivalent to `bash` for authorization, safety review, and approval. It must not become a bypass for bash restrictions. Result remains terminating so Pi does not start a follow-up model turn while shutdown is pending.

## Relay Contract

Use a fixed script as `/bin/sh -c` input. Pass cwd, command text, and exact resume argv as separate `execve` arguments; never interpolate caller text into relay source.

Equivalent shell logic:

```sh
cwd=$1
command=$2
shift 2
if cd "$cwd"; then
  /bin/sh -c "$command"
  status=$?
else
  status=125
  printf '%s\n' 'Command not run: Pi session working directory is unavailable.' >&2
fi
printf 'Command exited with status %d; resuming Pi.\n' "$status" >&2
exec "$@"
```

Outer argv shape:

```text
/bin/sh
-c
<FIXED_RELAY>
pi-command-relay        # $0 sentinel
<ctx.cwd>               # $1
<command>               # $2
<node executable>       # first argv after shift; exec target
<process.execArgv...>
<Pi entrypoint>
--session-dir
<exact session dir>
--session
<exact session JSONL path>
```

Properties:

- Shell quoting in command text is handled only by inner `/bin/sh -c "$command"`; outer relay source remains fixed.
- `cd` failure skips caller command, reports status 125, and still attempts exact Pi resume.
- Every ordinary child status, including nonzero and SIGINT-style 130, is printed before resume.
- Relay uses `exec "$@"`, replacing itself with Pi rather than leaving a supervisor or recursive wrapper.
- Environment, stdio, controlling terminal, and process group are inherited. Nvim receives terminal only after old Pi stopped its TUI.

## Nvim Contract

### Entry points

| Input | Generated command |
|---|---|
| `/nvim` | `nvim` |
| `/nvim src/main.ts` | `nvim -- 'src/main.ts'` |
| `/nvim docs/file name.md` | `nvim -- 'docs/file name.md'` |
| tool `{}` | `nvim` |
| tool `{ "path": "docs/file name.md" }` | `nvim -- 'docs/file name.md'` |

Slash-command remainder is one path, not whitespace-split argv. Slash and tool paths both trim leading/trailing whitespace; spaces inside remain. This deliberately does not support filenames whose names begin or end with whitespace. No Nvim flags are accepted: a value such as `-u NONE` is a filename because generated invocation inserts `--`. Tool schema is strict (`additionalProperties: false`), so a call contains only zero properties or one optional `path`.

### Path rules

1. Omitted or trimmed-empty path means no path.
2. Reject NUL, CR, or LF.
3. Reject `node:path.isAbsolute(path)`.
4. Normalize relative path, resolve it against `ctx.cwd`, then compute `relative(ctx.cwd, resolvedPath)`.
5. Reject relative result `..` or any result beginning with `..${sep}`.
6. Permit `.` and paths that do not exist so Nvim can open a directory or create a file.
7. Pass normalized relative path, not resolved absolute path, after `nvim --`.
8. POSIX-single-quote path and replace each embedded `'` with `'\''`.

Boundary is lexical, not a filesystem sandbox: symlinks are not resolved and Nvim may follow them. This matches requested relative-path validation while avoiding rejection of new files.

## Exit, Signal, and Failure Behavior

| Point | Required behavior |
|---|---|
| Invalid syntax/path, unsupported mode/runtime, missing persisted session | Throw before listener registration or shutdown; current TUI remains active. |
| Duplicate replacement request | Reject before adding another listener or calling shutdown. |
| `ctx.shutdown()` throws synchronously | Remove listener, clear pending state, keep current process active. |
| Graceful shutdown exits nonzero | Do not start relay; emit bounded credential-redacted diagnostic and exact-session recovery hint. |
| Initial Node `execve` to `/bin/sh` fails | Emit bounded credential-redacted diagnostic and exact-session recovery hint; same session JSONL path remains recoverable. |
| Session cwd disappears | Skip command, report status 125, still exec exact Pi resume argv. |
| Command exits 0/nonzero or inner shell reports command-not-found | Print status and always exec exact Pi resume argv. |
| Child-only SIGINT leaves relay alive and inner shell returns 130 | Print 130 and resume. This is the narrow SIGINT-like unit case. |
| Foreground terminal sends Ctrl-C to relay and child process group | Treat as relay termination: resume is not guaranteed. Do not claim a child-only 130 test proves this case. |
| Relay itself receives terminating SIGHUP/SIGTERM/SIGKILL, or terminal disappears | Resume is not guaranteed; no daemon is present. Reopen exact JSONL manually. |
| Relay's final `exec` or resumed Pi startup fails | Shell/CLI reports failure; exact JSONL path remains recovery source. |

Recovery guidance must identify exact session file and session directory, not only session ID:

```bash
pi --session-dir '<session-dir>' --session '<session-file>'
```

Diagnostics produced while Node still exists continue through `redactOutputText(...).slice(0, 1000)`. Fixed relay source must not interpolate or intentionally print caller command text. After Node is replaced, child stdout/stderr and inner-shell diagnostics have the same disclosure boundary as `bash`; they are inherited directly and are not passed through Node redaction.

## Minimal Follow-up Files

### Generic command-then-resume prerequisite

- Modify `pi/agent/extensions/process-restart.ts`
  - export shared restart function;
  - add command parser/validation and relay argv;
  - add optional tool field plus bash-equivalent guidance;
  - preserve direct-restart argv.
- Modify `tests/test_process_restart.py`
  - extend current loader harness and failure tests.
- Modify `pi/README.md`
  - document `/restart -- CMD` and tool command boundary.
- Modify `docs/extension-web-compatibility.md`
  - document TUI-only relay and mode/platform limits.

`pi/agent/extensions/lib/process-replacement.ts` should remain unchanged if copying the validated replacement descriptor with `executable: "/bin/sh"` satisfies tests.

### Nvim follow-up (depends on generic prerequisite)

- Create `pi/agent/extensions/nvim.ts`
  - path validation, one shell-quote helper, `/nvim`, `nvim` tool, shared restart call.
- Modify `tests/test_process_restart.py`
  - keep related replacement/nvim lifecycle coverage in one test module.
- Modify `pi/README.md`
  - document zero/one-path behavior and exact resume.
- Modify `docs/extension-web-compatibility.md`
  - add `nvim.ts` TUI-only row and headless boundary.

No settings, package, dependency, runtime deployment, or Pi-core source change is needed.

## Follow-up Tasks

### Task 1: Generic command-then-resume [Independent]

**Context:** Extend current restart extension without changing direct mode. Use TDD in existing Node extension harness.

**Steps:**
1. Add failing assertions for direct compatibility, slash delimiter handling, optional tool schema/guidance, command validation, and exact relay argv.
2. Add executable relay tests for quoted command text, cwd selection, exit 0/nonzero, child-only SIGINT-style status, and exact resume sentinel. Do not represent this as a real foreground-PTY Ctrl-C test.
3. Export shared restart function and implement minimum fixed relay.
4. Extend existing duplicate, shutdown, exec-failure, redaction, and documentation checks to command mode.
5. Run focused verification commands.

**Expected result:** Direct restart remains byte-for-byte equivalent in argv; command mode always reaches exact resume sentinel after ordinary child termination.

### Task 2: Nvim extension [Depends on: Task 1]

**Context:** Keep extension thin; generic restart owns lifecycle and exact-session behavior.

**Steps:**
1. Add failing harness tests for slash/tool zero path, one raw path with spaces, strict extra-property rejection, boundary trimming, and generated `nvim --` command.
2. Add rejection tests for absolute paths, normalized traversal, NUL, CR, and LF before shutdown.
3. Add shell-quote coverage for spaces and embedded single quotes.
4. Implement `nvim.ts` with one validator and one POSIX shell-quote helper.
5. Update docs and run focused verification.
6. In a persisted TTY, run a harmless generic command first, verify same JSONL resumes, then open/exit Nvim and verify same JSONL resumes again. Do not deploy tracked config during this test unless separately approved.

**Expected result:** Nvim owns only path-to-command translation; restart extension owns every process/session transition.

## Persisted-TTY Acceptance Probe

Use tracked extensions from repository checkout in a disposable persisted Pi session:

1. Record `/session` exact file and current cwd.
2. Invoke `/restart -- printf 'relay-ok\\n'`.
3. Verify `relay-ok`, status 0, new Pi process, same exact session-file path, and no second relay.
4. Invoke `/nvim docs/file name.md`, then quit Nvim without saving.
5. Verify terminal restores, Pi resumes once, cwd matches recorded session root, and exact session-file path is the same (file contents may have appended shutdown/tool state).
6. Repeat generic probe with `exit 7`; verify status 7 remains visible and Pi still resumes.

Any live `~/.pi` deployment or restart of this working session remains separately approval-gated.

## Design-only Boundary

This Bead authorizes investigation and this tracked plan only. Follow-up tasks above are not implementation authorization: do not modify extension/test/runtime files, deploy config, or restart a working Pi session until separate implementation work is started and approved.

## Execution Handoff

Plan saved to: `.pi/plans/2026-08-13-pi-to-nvim-reload-design-plan.md`

Recommended next skill: `test-driven-development` for each behavior slice; `verification-before-completion` before commit/closeout.
