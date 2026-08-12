from __future__ import annotations

import importlib
import json
import multiprocessing
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "pi" / "agent" / "bin"
AGNT = BIN / "agnt"


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=check,
        capture_output=True,
        text=True,
    )


def init_repo(path: Path) -> str:
    path.mkdir(parents=True)
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "user.name", "Pi Test")
    git(path, "config", "user.email", "pi-test@example.invalid")
    (path / "shared.txt").write_text("base\n", encoding="utf-8")
    (path / "preserved.txt").write_text("preserved\n", encoding="utf-8")
    git(path, "add", "shared.txt", "preserved.txt")
    git(path, "commit", "-q", "-m", "base")
    return git(path, "rev-parse", "HEAD").stdout.strip()


def add_worktree(repo: Path, path: Path, branch: str, base: str) -> None:
    git(repo, "worktree", "add", "-q", "-b", branch, str(path), base)


def commit_file(worktree: Path, relative: str, content: str, message: str) -> str:
    destination = worktree / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")
    git(worktree, "add", relative)
    git(worktree, "commit", "-q", "-m", message)
    return git(worktree, "rev-parse", "HEAD").stdout.strip()


def integration_module():
    sys.path.insert(0, str(BIN))
    return importlib.import_module("agnt_lib.integration")


def run_integrate(
    repo: Path,
    *,
    branch: str,
    expected_head: str,
    source_sha: str,
    timeout: float = 5,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            str(AGNT),
            "work",
            "integrate",
            "--target-branch",
            branch,
            "--expected-head",
            expected_head,
            "--source-sha",
            source_sha,
            "--timeout-seconds",
            str(timeout),
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
    )


def _lock_worker(
    bin_path: str,
    repo: str,
    entered,
    release,
    reports,
) -> None:
    sys.path.insert(0, bin_path)
    from agnt_lib.integration import integration_semaphore

    with integration_semaphore(repo, target_branch="main", timeout_seconds=5) as evidence:
        reports.put(evidence)
        entered.set()
        release.wait(5)


def _start_holder(repo: Path):
    context = multiprocessing.get_context("spawn")
    entered = context.Event()
    release = context.Event()
    reports = context.Queue()
    process = context.Process(
        target=_lock_worker,
        args=(str(BIN), str(repo), entered, release, reports),
    )
    process.start()
    assert entered.wait(5), "holder never acquired integration semaphore"
    return process, release, reports


def _stop(process, release) -> None:
    release.set()
    process.join(5)
    if process.is_alive():
        process.kill()
        process.join(5)


def test_same_target_integration_semaphore_serializes_processes(tmp_path):
    repo = tmp_path / "repo"
    init_repo(repo)
    first, first_release, _first_reports = _start_holder(repo)

    # Start second holder without waiting, so first holder controls entry order.
    context = multiprocessing.get_context("spawn")
    second_entered = context.Event()
    second_release = context.Event()
    second_reports = context.Queue()
    second = context.Process(
        target=_lock_worker,
        args=(str(BIN), str(repo), second_entered, second_release, second_reports),
    )
    second.start()
    try:
        assert not second_entered.wait(0.2)
        first_release.set()
        first.join(5)
        assert first.exitcode == 0
        assert second_entered.wait(5)
    finally:
        _stop(first, first_release)
        _stop(second, second_release)


def test_killed_holder_recovers_stale_metadata_without_private_identity(tmp_path):
    repo = tmp_path / "private" / "repo"
    init_repo(repo)
    holder, _release, reports = _start_holder(repo)
    prior = reports.get(timeout=2)
    holder.kill()
    holder.join(5)
    assert holder.exitcode is not None

    module = integration_module()
    with module.integration_semaphore(repo, target_branch="main", timeout_seconds=1) as recovered:
        assert recovered["recoveredStaleHolder"] is True
        assert recovered["recoveredOwnerId"] == prior["ownerId"]
        evidence_text = json.dumps(recovered, sort_keys=True)
        assert str(repo) not in evidence_text
        assert "main" not in evidence_text

        common_dir = Path(git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir").stdout.strip())
        metadata = json.loads(next((common_dir / "agnt" / "integration-locks").glob("*.lock")).read_text())
        assert set(metadata) == {"acquiredAt", "lockId", "ownerId", "state"}
        assert str(repo) not in json.dumps(metadata, sort_keys=True)


def test_waiting_integration_can_timeout_or_cancel(tmp_path):
    repo = tmp_path / "repo"
    init_repo(repo)
    holder, release, _reports = _start_holder(repo)
    module = integration_module()
    try:
        with pytest.raises(module.IntegrationLockTimeout) as timed_out:
            with module.integration_semaphore(repo, target_branch="main", timeout_seconds=0.05):
                pass
        assert timed_out.value.evidence["status"] == "lock-timeout"
        assert str(repo) not in json.dumps(timed_out.value.evidence)

        with pytest.raises(module.IntegrationLockCancelled) as cancelled:
            with module.integration_semaphore(
                repo,
                target_branch="main",
                timeout_seconds=1,
                cancel_check=lambda: True,
            ):
                pass
        assert cancelled.value.evidence["status"] == "cancelled"
    finally:
        _stop(holder, release)


def test_cancellation_wins_before_new_lock_acquisition(tmp_path):
    repo = tmp_path / "repo"
    init_repo(repo)
    holder, release, _reports = _start_holder(repo)
    module = integration_module()
    checks = 0

    def cancel_after_releasing_holder():
        nonlocal checks
        checks += 1
        if checks == 1:
            release.set()
            holder.join(5)
            return False
        return True

    with pytest.raises(module.IntegrationLockCancelled):
        with module.integration_semaphore(
            repo,
            target_branch="main",
            timeout_seconds=1,
            cancel_check=cancel_after_releasing_holder,
        ):
            pass


def test_lock_setup_errors_return_path_free_evidence(tmp_path):
    repo = tmp_path / "private" / "repo"
    init_repo(repo)
    common_dir = Path(git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir").stdout.strip())
    (common_dir / "agnt").write_text("not a directory\n", encoding="utf-8")
    module = integration_module()

    with pytest.raises(module.IntegrationLockError) as failed:
        with module.integration_semaphore(repo, target_branch="main", timeout_seconds=0):
            pass

    assert failed.value.evidence["status"] == "integration-unavailable"
    assert str(failed.value) == "integration-unavailable"
    assert failed.value.__cause__ is None
    assert str(repo) not in json.dumps(failed.value.evidence)


def test_concurrent_integration_attempts_recheck_target_under_lock(tmp_path):
    repo = tmp_path / "repo"
    base = init_repo(repo)
    source_one = tmp_path / "source-one"
    source_two = tmp_path / "source-two"
    add_worktree(repo, source_one, "source-one", base)
    add_worktree(repo, source_two, "source-two", base)
    sha_one = commit_file(source_one, "one.txt", "one\n", "source one")
    sha_two = commit_file(source_two, "two.txt", "two\n", "source two")

    first = subprocess.Popen(
        [str(AGNT), "work", "integrate", "--target-branch", "main", "--expected-head", base, "--source-sha", sha_one, "--timeout-seconds", "5"],
        cwd=repo,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    second = subprocess.Popen(
        [str(AGNT), "work", "integrate", "--target-branch", "main", "--expected-head", base, "--source-sha", sha_two, "--timeout-seconds", "5"],
        cwd=repo,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    outputs = [first.communicate(timeout=10), second.communicate(timeout=10)]
    results = [json.loads(stdout) for stdout, _stderr in outputs]

    assert sorted(result["status"] for result in results) == ["integrated", "target-diverged"]
    assert sorted(process.returncode for process in (first, second)) == [0, 3]
    winner = next(result for result in results if result["status"] == "integrated")
    loser = sha_two if winner["sourceSha"] == sha_one else sha_one
    assert git(repo, "merge-base", "--is-ancestor", winner["sourceSha"], "HEAD", check=False).returncode == 0
    assert git(repo, "merge-base", "--is-ancestor", loser, "HEAD", check=False).returncode == 1
    assert git(repo, "status", "--porcelain=v1", "--untracked-files=all").stdout == ""


def test_conflicting_merge_aborts_to_exact_clean_baseline(tmp_path):
    repo = tmp_path / "repo"
    base = init_repo(repo)
    source = tmp_path / "source"
    add_worktree(repo, source, "source", base)
    source_sha = commit_file(source, "shared.txt", "source\n", "source change")
    target_sha = commit_file(repo, "shared.txt", "target\n", "target change")

    result = run_integrate(repo, branch="main", expected_head=target_sha, source_sha=source_sha)

    assert result.returncode == 3
    evidence = json.loads(result.stdout)
    assert evidence["status"] == "conflict"
    assert evidence["rollbackVerified"] is True
    assert evidence["targetHeadBefore"] == target_sha
    assert evidence["targetHeadAfter"] == target_sha
    assert git(repo, "status", "--porcelain=v1", "--untracked-files=all").stdout == ""
    assert git(repo, "rev-parse", "-q", "--verify", "MERGE_HEAD", check=False).returncode != 0
    assert (repo / "shared.txt").read_text(encoding="utf-8") == "target\n"


def test_integration_ignores_git_environment_and_repository_hooks(tmp_path):
    repo = tmp_path / "repo"
    base = init_repo(repo)
    source = tmp_path / "source"
    add_worktree(repo, source, "source", base)
    source_sha = commit_file(source, "source.txt", "source\n", "source")
    marker = tmp_path / "hook-ran"
    hook = repo / ".git" / "hooks" / "post-merge"
    hook.write_text(f"#!/bin/sh\nprintf ran > '{marker}'\n", encoding="utf-8")
    hook.chmod(0o755)
    decoy = tmp_path / "decoy"
    init_repo(decoy)
    decoy_head = commit_file(decoy, "decoy.txt", "decoy\n", "decoy")
    git(repo, "config", "core.worktree", str(decoy))

    result = run_integrate(
        repo,
        branch="main",
        expected_head=base,
        source_sha=source_sha,
        env={"GIT_DIR": str(decoy / ".git"), "GIT_WORK_TREE": str(decoy)},
    )

    subprocess.run(
        ["git", f"--git-dir={repo / '.git'}", "config", "--unset", "core.worktree"],
        check=True,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout)["status"] == "integrated"
    assert not marker.exists()
    assert git(repo, "rev-parse", "HEAD").stdout.strip() == source_sha
    assert git(decoy, "rev-parse", "HEAD").stdout.strip() == decoy_head


def test_integration_disables_signature_verification_config(tmp_path):
    repo = tmp_path / "repo"
    base = init_repo(repo)
    source = tmp_path / "source"
    add_worktree(repo, source, "source", base)
    source_sha = commit_file(source, "source.txt", "source\n", "unsigned source")
    git(repo, "config", "merge.verifySignatures", "true")

    result = run_integrate(repo, branch="main", expected_head=base, source_sha=source_sha)

    assert result.returncode == 0
    assert json.loads(result.stdout)["status"] == "integrated"


def test_integration_rejects_branch_merge_options(tmp_path):
    repo = tmp_path / "repo"
    base = init_repo(repo)
    source = tmp_path / "source"
    add_worktree(repo, source, "source", base)
    source_sha = commit_file(source, "source.txt", "source\n", "source")
    git(repo, "config", "branch.main.mergeOptions", "--strategy=external")

    result = run_integrate(repo, branch="main", expected_head=base, source_sha=source_sha)

    assert result.returncode == 3
    assert json.loads(result.stdout)["status"] == "unsafe-git-config"
    assert git(repo, "rev-parse", "HEAD").stdout.strip() == base


def test_integration_rejects_command_bearing_merge_configuration(tmp_path):
    repo = tmp_path / "repo"
    init_repo(repo)
    (repo / ".gitattributes").write_text("shared.txt merge=external\n", encoding="utf-8")
    git(repo, "add", ".gitattributes")
    git(repo, "commit", "-q", "-m", "attributes")
    base = git(repo, "rev-parse", "HEAD").stdout.strip()
    source = tmp_path / "source"
    add_worktree(repo, source, "source", base)
    source_sha = commit_file(source, "shared.txt", "source\n", "source change")
    target_sha = commit_file(repo, "shared.txt", "target\n", "target change")
    marker = tmp_path / "driver-ran"
    driver = tmp_path / "merge-driver.sh"
    driver.write_text(f"#!/bin/sh\nprintf ran > '{marker}'\nexit 1\n", encoding="utf-8")
    driver.chmod(0o755)
    git(repo, "config", "merge.external.driver", str(driver))

    result = run_integrate(repo, branch="main", expected_head=target_sha, source_sha=source_sha)

    assert result.returncode == 3
    assert json.loads(result.stdout)["status"] == "unsafe-git-config"
    assert not marker.exists()
    assert git(repo, "rev-parse", "HEAD").stdout.strip() == target_sha
    assert git(repo, "status", "--porcelain=v1", "--untracked-files=all").stdout == ""


def test_integration_preserves_unrelated_linked_worktree(tmp_path):
    repo = tmp_path / "repo"
    base = init_repo(repo)
    source = tmp_path / "source"
    unrelated = tmp_path / "unrelated"
    add_worktree(repo, source, "source", base)
    source_sha = commit_file(source, "source.txt", "source\n", "source")
    add_worktree(repo, unrelated, "unrelated", base)
    (unrelated / "local-note.txt").write_text("keep me\n", encoding="utf-8")
    unrelated_head = git(unrelated, "rev-parse", "HEAD").stdout.strip()
    unrelated_status = git(unrelated, "status", "--porcelain=v1", "--untracked-files=all").stdout

    result = run_integrate(repo, branch="main", expected_head=base, source_sha=source_sha)

    assert result.returncode == 0
    evidence = json.loads(result.stdout)
    assert evidence["status"] == "integrated"
    assert evidence["targetHeadBefore"] == base
    assert evidence["targetHeadAfter"] == source_sha
    assert git(unrelated, "rev-parse", "HEAD").stdout.strip() == unrelated_head
    assert git(unrelated, "status", "--porcelain=v1", "--untracked-files=all").stdout == unrelated_status
    assert (unrelated / "local-note.txt").read_text(encoding="utf-8") == "keep me\n"
