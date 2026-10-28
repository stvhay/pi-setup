# Scenario: Preserve local-only Beads

## Prompt
Audit a repository using native `bd init --stealth`: `.beads/` is ignored through `.git/info/exclude`, no Beads files are tracked, and canonical Beads is healthy. Code still goes through ordinary approved commits and remote PRs. Explain closeout and required remediation. Contrast a second repository with tracked `.beads/issues.jsonl` and a third with only tracked `.beads/config.yaml`.

## Expected weak baseline
Project-init BEADS-3 and shared workflow guidance require exported, committed Beads for every successful handoff and push. Agent either blocks valid local-only use or proposes publishing internal Beads. Branch-finishing guidance may confuse local-only Beads with a project having no remote workflow.

## Expected with skill
Both publication choices are valid. Local-only verifies canonical closure, ownership, outcome, authority and clean tracked code without exporting/staging/committing Beads; shared retains export/parity/commit. Mixed tracking needs explicit resolution, never automatic untracking or force-add.

## Assertions
- Preserve local-only choice; no Beads publication or automatic migration.
- Shared mode remains supported; tracked export is not silently downgraded by ignore rules.
- Local-only requires ignored `.beads/` and no tracked Beads paths, not merely a missing export.
- Code commits and approved PR/push workflows remain independent of Beads publication.
- Existing published history is not removed by ignoring files; local-only data does not travel in Git clones.
- Dolt sync/backups, hooks and live deployment remain separately authorized.

## Static verification
`tests/test_context_architecture.py::test_beads_publication_guidance_allows_both_modes` checks owning guidance. Executable behavior is covered by `tests/test_local_beads.py` and native stealth/worktree journeys in `tests/test_beads_workspace.py`. No model behavioral canary requested.
