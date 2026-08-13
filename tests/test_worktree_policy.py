from __future__ import annotations


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


def test_missing_epic_worktree_uses_initial_approval_without_second_gate(agnt, tmp_path):
    spec = agnt.epic_worktree_spec("pi-6yg", "Beads-first autonomous orchestration", repo_root=tmp_path)

    result = agnt.resolve_epic_worktree(
        spec,
        worktrees=[],
        status_runner=lambda _path: (0, "", ""),
        creation_approval={"decisionBead": "pi-approval.1", "resolver": {"kind": "human-ui"}},
    )

    assert result["status"] == "needs-creation"
    assert result["dispatchable"] is False
    assert result["creationAuthorized"] is True
    assert result["approvalRef"] == "pi-approval.1"
    assert "without another approval" in result["reason"]


def test_missing_worktree_rejects_unproven_creation_authority(agnt, tmp_path):
    spec = agnt.epic_worktree_spec("pi-6yg", repo_root=tmp_path)

    result = agnt.resolve_epic_worktree(
        spec,
        worktrees=[],
        creation_approval={"decisionBead": "pi-approval.1", "resolver": {"kind": "caller"}},
    )

    assert result["status"] == "needs-approval"
    assert result["dispatchable"] is False
    assert "creationAuthorized" not in result


def test_worktree_snapshot_carries_initial_human_approval_to_creation(agnt, tmp_path):
    spec = agnt.epic_worktree_spec("pi-6yg", repo_root=tmp_path)
    validation = {
        "normalized": {
            "action": "implement",
            "approved": True,
            "humanApproval": {"decisionBead": "pi-approval.1", "resolver": {"kind": "human-ui"}},
            "epicId": "pi-6yg",
            "worktreePolicy": "epic-worktree",
        }
    }

    result = agnt.worktree_snapshot_for_bead(
        {},
        validation,
        repo_root=tmp_path,
        worktrees=[],
    )

    assert result["path"] == spec["path"]
    assert result["status"] == "needs-creation"
    assert result["approvalRef"] == "pi-approval.1"


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


def test_removed_runner_helpers_are_not_public(agnt):
    assert not hasattr(agnt, "checkpoint_epic_worktree")
    assert not hasattr(agnt, "write_sets_overlap")
    assert not hasattr(agnt, "write_conflict_for")
