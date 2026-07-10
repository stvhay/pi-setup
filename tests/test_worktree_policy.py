from __future__ import annotations

import json
import subprocess
from pathlib import Path


IMPLEMENT_META = {
    "pi": {
        "action": "implement",
        "routingTask": "implementation",
        "approved": True,
        "humanApproval": {"decisionBead": "pi-approval.1", "resolver": {"kind": "human-ui", "sessionId": "pi-session-1"}},
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


def test_dirty_epic_worktree_requires_explicit_checkpoint_continuation(agnt, tmp_path):
    spec = agnt.epic_worktree_spec("pi-6yg", "Beads-first autonomous orchestration", repo_root=tmp_path)
    existing_branch = [{"path": spec["path"], "branch": spec["branch"]}]

    result = agnt.resolve_epic_worktree(
        spec,
        worktrees=existing_branch,
        status_runner=lambda _path: (0, " M e2e-test/challenge.py\n", ""),
        continuation={"mode": "checkpoint", "predecessor": "pi-6yg.1", "approvalRef": "pi-5eu"},
    )

    assert result["status"] == "checkpoint-required"
    assert result["dispatchable"] is False
    assert result["continuation"]["predecessor"] == "pi-6yg.1"
    assert "checkpoint" in result["reason"]


def test_checkpoint_epic_worktree_creates_scoped_local_commit(agnt, tmp_path):
    worktree = {
        "status": "checkpoint-required",
        "path": str(tmp_path),
        "branch": "epic/pi-6yg",
        "dirtyStatus": " M e2e-test/challenge.py\n",
        "continuation": {"mode": "checkpoint", "predecessor": "pi-6yg.1", "approvalRef": "pi-5eu"},
    }
    calls = []
    heads = iter(["baseline-sha\n", "checkpoint-sha\n"])
    statuses = iter([" M e2e-test/challenge.py\n", ""])

    def git_runner(args, cwd):
        calls.append((args, cwd))
        if args == ["rev-parse", "HEAD"]:
            return 0, next(heads), ""
        if args == ["status", "--short", "--untracked-files=all"]:
            return 0, next(statuses), ""
        if args == ["add", "--", "e2e-test"]:
            return 0, "", ""
        if args == ["diff", "--cached", "--quiet"]:
            return 1, "", ""
        if args == ["diff", "--cached", "--stat"]:
            return 0, " e2e-test/challenge.py | 1 +\n", ""
        if args == ["commit", "-m", "runner checkpoint pi-6yg.1 before pi-6yg.2"]:
            return 0, "[epic/pi-6yg checkpoint-sha] checkpoint\n", ""
        raise AssertionError(args)

    result = agnt.checkpoint_epic_worktree(
        worktree,
        bead_id="pi-6yg.2",
        write_set=["e2e-test"],
        git_runner=git_runner,
    )

    assert result["ok"] is True
    assert result["baselineSha"] == "baseline-sha"
    assert result["checkpointSha"] == "checkpoint-sha"
    assert result["approvalRef"] == "pi-5eu"
    assert result["diffStat"] == " e2e-test/challenge.py | 1 +\n"
    assert result["statusAfter"] == ""
    assert (["add", "--", "e2e-test"], str(tmp_path)) in calls


def _init_checkpoint_repo(path):
    subprocess.run(["git", "init", "-b", "epic/pi-6yg"], cwd=path, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "Pi Test"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "pi-test@example.invalid"], cwd=path, check=True)
    (path / "seed.txt").write_text("baseline\n", encoding="utf-8")
    subprocess.run(["git", "add", "seed.txt"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "baseline"], cwd=path, check=True, capture_output=True, text=True)


def _checkpoint_worktree(path):
    return {
        "status": "checkpoint-required",
        "path": str(path),
        "branch": "epic/pi-6yg",
        "continuation": {"mode": "checkpoint", "predecessor": "pi-6yg.1", "approvalRef": "pi-5eu"},
    }


def test_checkpoint_epic_worktree_accepts_file_scoped_untracked_directory(agnt, tmp_path):
    _init_checkpoint_repo(tmp_path)
    challenge_dir = tmp_path / "e2e-test"
    challenge_dir.mkdir()
    write_set = [
        "e2e-test/README.md",
        "e2e-test/edabit_challenges.py",
        "e2e-test/test_edabit_challenges.py",
    ]
    for item in write_set:
        (tmp_path / item).write_text(f"{item}\n", encoding="utf-8")

    result = agnt.checkpoint_epic_worktree(
        _checkpoint_worktree(tmp_path),
        bead_id="pi-6yg.2",
        write_set=write_set,
    )

    assert result["ok"] is True
    assert result["statusAfter"] == ""
    assert all(f"?? {item}" in result["statusBefore"] for item in write_set)
    assert result["writeSet"] == write_set


def test_checkpoint_epic_worktree_rejects_real_path_outside_file_scope(agnt, tmp_path):
    _init_checkpoint_repo(tmp_path)
    challenge_dir = tmp_path / "e2e-test"
    challenge_dir.mkdir()
    approved = "e2e-test/edabit_challenges.py"
    (tmp_path / approved).write_text("def return_sum(a, b): return a + b\n", encoding="utf-8")
    (tmp_path / "outside.txt").write_text("outside\n", encoding="utf-8")

    result = agnt.checkpoint_epic_worktree(
        _checkpoint_worktree(tmp_path),
        bead_id="pi-6yg.2",
        write_set=[approved],
    )

    assert result["ok"] is False
    assert result["reason"] == "dirty worktree changes are outside the approved continuation writeSet"
    assert "?? outside.txt" in result["dirtyStatus"]


def test_checkpoint_epic_worktree_rejects_unsafe_write_set(agnt, tmp_path):
    worktree = {
        "status": "checkpoint-required",
        "path": str(tmp_path),
        "branch": "epic/pi-6yg",
        "continuation": {"mode": "checkpoint", "predecessor": "pi-6yg.1", "approvalRef": "pi-5eu"},
    }

    result = agnt.checkpoint_epic_worktree(worktree, bead_id="pi-6yg.2", write_set=["../outside"])

    assert result["ok"] is False
    assert "unsafe" in result["reason"]


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
