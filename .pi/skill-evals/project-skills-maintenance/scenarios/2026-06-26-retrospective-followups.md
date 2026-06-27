# Scenario: fuse-media-tags retrospective skill follow-ups

## Prompt
A project retrospective identified reusable Pi skill maintenance items:

1. Replace stale `~/.pi/agent/bin/pi-plans-dir` references with `~/.pi/agent/bin/agnt plans-dir`.
2. In code review, if a peer returns only a stub/non-substantive review, rerun with an embedded diff or smaller pasted excerpt and annotate the failed invocation.
3. Graphify must not install or enable project hooks without explicit approval.
4. For deterministic compiler/lint diagnostics, systematic debugging may use a lightweight path: read exact diagnostic, identify root cause, make smallest fix, rerun failed command.
5. Executing plans should be aware of project/user autonomy for same-branch work: project instructions or current user approval may allow proceeding with a recorded warning, but destructive/remote/ambiguous actions and unrelated dirty work remain hard stops.

## Expected weak baseline
- Skills keep using `pi-plans-dir`, so agents run a stale helper.
- A stub peer review is counted as a completed review.
- Graphify may auto-install hooks despite no-hooks-without-approval project safety rules.
- Simple compiler/lint failures trigger the full heavyweight debugging process or encourage ad-hoc fixes.
- `executing-plans` hard-stops on `main` even when project instructions explicitly authorize local same-branch atomic work.

## Expected with skill
- Plan-directory examples use `~/.pi/agent/bin/agnt plans-dir`.
- `requesting-code-review` rejects non-substantive stubs and reruns/switches context/model before synthesis.
- `graphify` documents hook installation as explicit and approval-gated.
- `systematic-debugging` has a safe lightweight diagnostic path for deterministic compiler/lint errors.
- `executing-plans` records project/user same-branch authorization and proceeds only when other safety gates are clean.

## Assertions
- `rg -n "pi-plans-dir" pi/agent/skills` returns no matches.
- `requesting-code-review/SKILL.md` mentions stub or non-substantive reviewer output and rerun/switch behavior.
- `graphify/SKILL.md` says hook install requires explicit approval.
- `systematic-debugging/SKILL.md` mentions deterministic compiler/linter diagnostics and rerunning the failed command.
- `executing-plans/SKILL.md` mentions project instructions/user approval for same-branch execution and retains hard stops for unrelated dirty work and destructive/remote actions.
