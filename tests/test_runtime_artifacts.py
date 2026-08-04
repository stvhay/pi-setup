from __future__ import annotations

import hashlib
import stat
import subprocess
from pathlib import Path

import pytest


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def init_repo(path: Path, ignore: str | None = None) -> Path:
    path.mkdir()
    git(path, "init", "-q")
    git(path, "config", "user.email", "test@example.invalid")
    git(path, "config", "user.name", "Test User")
    if ignore is not None:
        (path / ".gitignore").write_text(ignore, encoding="utf-8")
    return path


def resolve(agnt, kind: str, cwd: Path, global_root: Path) -> Path:
    resolver = getattr(agnt, "resolve_runtime_directory", None)
    assert callable(resolver), "runtime directory policy is missing"
    return resolver(kind, cwd=cwd, global_root=global_root)


def test_runtime_directory_uses_ignored_untracked_project_path(agnt, tmp_path):
    repo = init_repo(tmp_path / "repo", ".pi/runs/\n")

    path = resolve(agnt, "runs", repo, tmp_path / "global")

    assert path == repo / ".pi" / "runs"
    assert stat.S_IMODE(path.stat().st_mode) == 0o700


def test_runtime_directory_rejects_unignored_project_path(agnt, tmp_path):
    repo = init_repo(tmp_path / "repo")
    global_root = tmp_path / "global"

    path = resolve(agnt, "runs", repo, global_root)

    assert global_root in path.parents
    assert path != repo / ".pi" / "runs"


def test_runtime_directory_rejects_unrelated_probe_ignore_rule(agnt, tmp_path):
    repo = init_repo(tmp_path / "repo", "*.agnt-runtime-probe\n")
    global_root = tmp_path / "global"

    path = resolve(agnt, "runs", repo, global_root)

    assert global_root in path.parents
    assert path != repo / ".pi" / "runs"


def test_runtime_directory_rejects_tracked_project_path(agnt, tmp_path):
    repo = init_repo(tmp_path / "repo", ".pi/runs/\n")
    tracked = repo / ".pi" / "runs" / "owned.txt"
    tracked.parent.mkdir(parents=True)
    tracked.write_text("tracked\n", encoding="utf-8")
    git(repo, "add", "-f", ".pi/runs/owned.txt")
    global_root = tmp_path / "global"

    path = resolve(agnt, "runs", repo, global_root)

    assert global_root in path.parents
    assert path != tracked.parent


def test_runtime_directory_supports_worktree_git_file(agnt, tmp_path):
    repo = init_repo(tmp_path / "repo", ".pi/runs/\n")
    git(repo, "add", ".gitignore")
    git(repo, "commit", "-qm", "init")
    worktree = tmp_path / "worktree"
    git(repo, "worktree", "add", "-q", "-b", "test-worktree", str(worktree))
    assert (worktree / ".git").is_file()

    path = resolve(agnt, "runs", worktree, tmp_path / "global")

    assert path == worktree / ".pi" / "runs"


def test_runtime_directory_non_git_fallback_has_deterministic_full_hash(agnt, tmp_path):
    cwd = tmp_path / "plain"
    cwd.mkdir()
    global_root = tmp_path / "global"
    expected_key = hashlib.sha256(f"path:{cwd.resolve()}".encode()).hexdigest()

    first = resolve(agnt, "metrics/invocations", cwd, global_root)
    second = resolve(agnt, "metrics/invocations", cwd, global_root)

    assert first == second == global_root / expected_key / "metrics" / "invocations"
    assert len(first.relative_to(global_root).parts[0]) == 64


def test_runtime_directory_hashes_distinct_non_git_locations(agnt, tmp_path):
    first_cwd = tmp_path / "first"
    second_cwd = tmp_path / "second"
    first_cwd.mkdir()
    second_cwd.mkdir()
    global_root = tmp_path / "global"

    first = resolve(agnt, "runs", first_cwd, global_root)
    second = resolve(agnt, "runs", second_cwd, global_root)

    assert first.parent != second.parent


def test_runtime_directory_global_fallback_is_private(agnt, tmp_path):
    cwd = tmp_path / "plain"
    cwd.mkdir()
    global_root = tmp_path / "global"
    global_root.mkdir(mode=0o777)
    global_root.chmod(0o777)

    path = resolve(agnt, "runs", cwd, global_root)

    assert stat.S_IMODE(global_root.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.stat().st_mode) == 0o700


def test_runtime_directory_missing_git_uses_non_git_identity(agnt, monkeypatch, tmp_path):
    repo = init_repo(tmp_path / "repo", ".pi/runs/\n")
    global_root = tmp_path / "global"
    expected_key = hashlib.sha256(f"path:{repo.resolve()}".encode()).hexdigest()
    resolver = getattr(agnt, "resolve_runtime_directory", None)
    assert callable(resolver), "runtime directory policy is missing"
    module = __import__(resolver.__module__, fromlist=["shutil"])
    monkeypatch.setattr(module.shutil, "which", lambda _name: None)

    path = resolve(agnt, "runs", repo, global_root)

    assert path == global_root / expected_key / "runs"


def test_runtime_directory_rejects_symlinked_project_candidate(agnt, tmp_path):
    repo = init_repo(tmp_path / "repo", ".pi/runs/\n")
    external = tmp_path / "external"
    external.mkdir()
    (repo / ".pi").mkdir()
    (repo / ".pi" / "runs").symlink_to(external, target_is_directory=True)
    global_root = tmp_path / "global"

    path = resolve(agnt, "runs", repo, global_root)

    assert global_root in path.parents
    assert path != external


def test_runtime_directory_rejects_unsafe_kind(agnt, tmp_path):
    with pytest.raises(ValueError, match="runtime kind"):
        resolve(agnt, "../private", tmp_path, tmp_path / "global")
