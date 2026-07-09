from __future__ import annotations

import json
from pathlib import Path


IMPLEMENT_META = {
    "pi": {
        "action": "implement",
        "routingTask": "implementation",
        "approved": True,
        "allowedEffects": ["read_workspace", "write_artifacts", "edit_files", "update_beads"],
        "modelPolicy": {"mode": "auto"},
        "epicId": "pi-6yg",
        "worktreePolicy": "epic-worktree",
        "writeSet": ["pi/agent/bin/agnt_lib/runner.py", "tests/test_runner.py"],
        "closeout": {
            "requiresEvidence": True,
            "requiresResolvedApprovals": True,
            "requiresFollowUpsReconciled": True,
        },
    }
}


def implement_bead(bead_id="pi-task.1", write_set=None):
    meta = json.loads(json.dumps(IMPLEMENT_META))
    if write_set is not None:
        meta["pi"]["writeSet"] = write_set
    return {
        "id": bead_id,
        "title": "Implement runner",
        "issue_type": "task",
        "status": "open",
        "acceptance_criteria": "tests pass",
        "metadata": json.dumps(meta),
    }


def test_epic_worktree_spec_is_deterministic(agnt, tmp_path):
    spec = agnt.epic_worktree_spec("pi-6yg", "Beads-first autonomous orchestration", repo_root=tmp_path)

    assert spec["policy"] == "epic-worktree"
    assert spec["epicId"] == "pi-6yg"
    assert spec["branch"] == "epic/pi-6yg-beads-first-autonomous-orchestration"
    assert spec["path"] == str(tmp_path / ".worktrees" / "epic" / "pi-6yg-beads-first-autonomous-orchestration")


def test_missing_epic_worktree_requires_explicit_creation_approval(agnt, tmp_path):
    spec = agnt.epic_worktree_spec("pi-6yg", "Beads-first autonomous orchestration", repo_root=tmp_path)

    result = agnt.resolve_epic_worktree(spec, worktrees=[], status_runner=lambda _path: (0, "", ""))

    assert result["status"] == "needs-approval"
    assert result["dispatchable"] is False
    assert "explicit approval" in result["reason"]


def test_existing_main_or_dirty_worktree_blocks_dispatch(agnt, tmp_path):
    spec = agnt.epic_worktree_spec("pi-6yg", "Beads-first autonomous orchestration", repo_root=tmp_path)
    existing_main = [{"path": spec["path"], "branch": "main"}]
    existing_branch = [{"path": spec["path"], "branch": spec["branch"]}]

    main_result = agnt.resolve_epic_worktree(spec, worktrees=existing_main, status_runner=lambda _path: (0, "", ""))
    dirty_result = agnt.resolve_epic_worktree(spec, worktrees=existing_branch, status_runner=lambda _path: (0, " M file.py\n", ""))

    assert main_result["status"] == "blocked"
    assert "main" in main_result["reason"]
    assert dirty_result["status"] == "blocked"
    assert "dirty" in dirty_result["reason"]


def test_runner_tick_blocks_implementation_when_epic_worktree_missing(agnt, tmp_path):
    ready = [implement_bead()]

    def fake_beads(args):
        assert args == ["ready"]
        return 0, ready, ""

    result = agnt.runner_tick(root=tmp_path, dry_run=True, beads_runner=fake_beads, limit=1)

    assert result["actions"][0]["action"] == "would_block"
    assert result["actions"][0]["worktree"]["status"] == "needs-approval"
    assert "explicit approval" in result["actions"][0]["context"]


def test_overlapping_write_sets_create_dependency_plan(agnt, tmp_path):
    ready = [
        implement_bead("pi-task.1", ["pi/agent/bin/agnt_lib/runner.py"]),
        implement_bead("pi-task.2", ["pi/agent/bin/agnt_lib/runner.py", "tests/test_runner.py"]),
    ]

    def fake_beads(args):
        assert args == ["ready"]
        return 0, ready, ""

    def dispatchable_worktree(_bead, _validation):
        return {"status": "ready", "dispatchable": True, "path": str(tmp_path), "branch": "epic/pi-6yg-test"}

    result = agnt.runner_tick(
        root=tmp_path,
        dry_run=True,
        beads_runner=fake_beads,
        worktree_resolver=dispatchable_worktree,
        limit=2,
    )

    assert result["actions"][0]["action"] == "would_start"
    assert result["actions"][1]["action"] == "would_add_dependency"
    assert result["actions"][1]["blockedBy"] == "pi-task.1"
    assert result["actions"][1]["overlap"] == ["pi/agent/bin/agnt_lib/runner.py"]
