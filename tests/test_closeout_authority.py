"""Direct closeout must not widen the current assignment's effect ceiling."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

from test_work_continuation import runtime  # noqa: F401


def prepare_closeout(runtime, monkeypatch):
    repo = runtime["repo"]
    portable = repo / ".beads" / "issues.jsonl"
    portable.parent.mkdir()
    portable.write_text(json.dumps({"id": "pi-a", "status": "open"}) + "\n")
    subprocess.run(["git", "add", ".beads/issues.jsonl"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                    "commit", "-qm", "fixture portable state"], cwd=repo, check=True, capture_output=True)
    for key, value in (("user.name", "Fixture"), ("user.email", "fixture@example.invalid")):
        subprocess.run(["git", "config", key, value], cwd=repo, check=True, capture_output=True)
    assert runtime["work"].direct_start("pi-a", claim=False)["status"] == "started"
    # Baseline must not invoke a real exporter after its unauthorized close.
    monkeypatch.setattr(runtime["work"], "beads_bin", lambda: None)
    return portable


@pytest.mark.parametrize("runtime", [
    {"effects": ["repo-write", "git-commit"]},
    {"effects": ["beads-write", "repo-write"]},
    {"effects": ["beads-write", "git-commit"]},
], indirect=True)
def test_closeout_denies_missing_effect_before_outcome_or_native_write(runtime, monkeypatch):
    portable = prepare_closeout(runtime, monkeypatch)
    before = portable.read_bytes()
    result = runtime["work"].direct_closeout("pi-a", outcome="success", reason="fixture complete")
    assert runtime["quality"].session_attempt_state("session-a")["outcome"] is None
    assert not any(args[0] == "close" for args in runtime["calls"])
    assert portable.read_bytes() == before
    assert result["stages"]["authority"]["status"] == "failed"
    assert result["repair"]["safeToRetry"] is False


@pytest.mark.parametrize("runtime", [{"effects": ["beads-write", "repo-write", "git-commit"]}], indirect=True)
def test_closeout_rechecks_scope_before_native_close(runtime, monkeypatch):
    portable = prepare_closeout(runtime, monkeypatch)
    original = runtime["work"].record_current_session_outcome
    def record(*args):
        result = original(*args)
        runtime["permission"].revoke("stop before native close")
        return result
    monkeypatch.setattr(runtime["work"], "record_current_session_outcome", record)
    before = portable.read_bytes()
    result = runtime["work"].direct_closeout("pi-a", outcome="success", reason="fixture complete")
    assert not any(args[0] == "close" for args in runtime["calls"])
    assert portable.read_bytes() == before
    assert result["stages"]["authority"]["status"] == "failed"
    assert result["stages"]["outcome"]["status"] == "succeeded"
    assert result["repair"]["safeToRetry"] is False


@pytest.mark.parametrize("runtime", [{"effects": ["beads-write", "repo-write", "git-commit"]}], indirect=True)
def test_closeout_stops_export_after_revocation(runtime, monkeypatch):
    portable = prepare_closeout(runtime, monkeypatch)
    monkeypatch.setattr(runtime["work"], "beads_bin", lambda: str(runtime["root"] / "must-not-run"))
    original = runtime["work"].run_beads_json
    def close(args):
        result = original(args)
        if args[0] == "close":
            runtime["permission"].revoke("stop after close")
        return result
    monkeypatch.setattr(runtime["work"], "run_beads_json", close)
    before = portable.read_bytes()
    result = runtime["work"].direct_closeout("pi-a", outcome="success", reason="fixture complete")
    assert result["status"] == "partial"
    assert result["stages"]["close"]["status"] == "succeeded"
    assert result["stages"]["authority"]["status"] == "failed"
    assert portable.read_bytes() == before
    assert result["repair"]["safeToRetry"] is False


@pytest.mark.parametrize("runtime", [{"effects": ["beads-write", "repo-write", "git-commit"]}], indirect=True)
def test_closeout_rejects_redirected_portable_directory_before_success(runtime, monkeypatch):
    portable = prepare_closeout(runtime, monkeypatch)
    foreign = runtime["root"] / "foreign-portable"
    portable.parent.rename(foreign)
    portable.parent.symlink_to(foreign, target_is_directory=True)
    runtime["work"].direct_closeout("pi-a", outcome="success", reason="fixture complete")
    assert runtime["quality"].session_attempt_state("session-a")["outcome"] is None
    assert not any(args[0] == "close" for args in runtime["calls"])


@pytest.mark.parametrize("change", ["pending-dependency", "closed-elsewhere"])
@pytest.mark.parametrize("runtime", [{"effects": ["beads-write", "repo-write", "git-commit"]}], indirect=True)
def test_changed_canonical_work_cannot_be_finalized(runtime, monkeypatch, change):
    prepare_closeout(runtime, monkeypatch)
    if change == "pending-dependency":
        runtime["beads"]["pi-a"]["dependencies"] = [{"depends_on_id": "pi-b", "dependency_type": "blocks"}]
    else:
        runtime["beads"]["pi-a"].update(status="closed", close_reason="cancelled externally")
    result = runtime["work"].direct_closeout("pi-a", outcome="success", reason="fixture complete")
    assert runtime["quality"].session_attempt_state("session-a")["outcome"] is None
    assert not any(args[0] == "close" for args in runtime["calls"])
    assert result["stages"]["authority"]["status"] == "failed"


@pytest.mark.parametrize("runtime", [{"effects": ["beads-write", "repo-write", "git-commit"]}], indirect=True)
def test_portable_replace_cannot_follow_foreign_namespace_after_guard(runtime, monkeypatch):
    portable = prepare_closeout(runtime, monkeypatch)
    closeout_backend(runtime, monkeypatch)
    foreign = runtime["root"] / "foreign-portable"
    foreign.mkdir()
    sentinel = b"unrelated foreign state\n"
    (foreign / "issues.jsonl").write_bytes(sentinel)
    original_replace = runtime["work"].os.replace
    swapped = False
    def replace(source, destination, **kwargs):
        nonlocal swapped
        if Path(destination).name == "issues.jsonl" and not swapped:
            swapped = True
            original_source = Path(source) if Path(source).is_absolute() else portable.parent / source
            shutil.copyfile(original_source, foreign / Path(source).name)
            portable.parent.rename(runtime["repo"] / "saved-beads")
            portable.parent.symlink_to(foreign, target_is_directory=True)
        return original_replace(source, destination, **kwargs)
    monkeypatch.setattr(runtime["work"].os, "replace", replace)
    result = runtime["work"].direct_closeout("pi-a", outcome="success", reason="fixture complete")
    assert swapped
    assert (foreign / "issues.jsonl").read_bytes() == sentinel
    assert result["status"] == "partial"


def closeout_backend(runtime, monkeypatch):
    row = {**runtime["beads"]["pi-a"], "status": "closed",
           "closed_at": "2026-10-20T00:00:00Z", "close_reason": "fixture complete"}
    exporter = runtime["root"] / "fixture-exporter"
    exporter.write_text(
        "#!/usr/bin/env python3\nimport sys\n"
        f"sys.stdout.write({(json.dumps(row) + chr(10))!r})\n"
    )
    exporter.chmod(0o755)
    monkeypatch.setattr(runtime["work"], "beads_bin", lambda: str(exporter))
    original = runtime["work"].run_beads_json
    def runner(args):
        if args[0] == "close":
            runtime["beads"]["pi-a"].update(row)
        return original(args)
    monkeypatch.setattr(runtime["work"], "run_beads_json", runner)
    return exporter


@pytest.mark.parametrize("runtime", [{"effects": ["beads-write", "repo-write", "git-commit"]}], indirect=True)
def test_captured_local_scope_completes_closeout(runtime, monkeypatch):
    portable = prepare_closeout(runtime, monkeypatch)
    closeout_backend(runtime, monkeypatch)
    result = runtime["work"].direct_closeout("pi-a", outcome="success", reason="fixture complete")
    assert result["status"] == "closed"
    assert result["commit"]
    assert json.loads(portable.read_text())["status"] == "closed"
    assert runtime["store"].owner("pi-a")["phase"] == "completed"


@pytest.mark.parametrize("phase", ["export", "stage"])
@pytest.mark.parametrize("runtime", [{"effects": ["beads-write", "repo-write", "git-commit"]}], indirect=True)
def test_revocation_preserves_partial_export_or_index_without_commit(runtime, monkeypatch, phase):
    portable = prepare_closeout(runtime, monkeypatch)
    exporter = closeout_backend(runtime, monkeypatch)
    before = portable.read_bytes()
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=runtime["repo"], check=True,
                          capture_output=True, text=True).stdout
    if phase == "export":
        original_run = subprocess.run
        def run(args, *positional, **kwargs):
            result = original_run(args, *positional, **kwargs)
            if args[0] == str(exporter):
                runtime["permission"].revoke("stop before portable replacement")
            return result
        monkeypatch.setattr(subprocess, "run", run)
    else:
        original_git = runtime["work"]._git
        def git(root, args):
            result = original_git(root, args)
            if args[0] == "add":
                runtime["permission"].revoke("stop before commit")
            return result
        monkeypatch.setattr(runtime["work"], "_git", git)
    result = runtime["work"].direct_closeout("pi-a", outcome="success", reason="fixture complete")
    assert result["status"] == "partial"
    assert result["stages"]["authority"]["status"] == "failed"
    assert result["repair"]["safeToRetry"] is False
    assert subprocess.run(["git", "rev-parse", "HEAD"], cwd=runtime["repo"], check=True,
                          capture_output=True, text=True).stdout == head
    staged = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=runtime["repo"], check=True,
                            capture_output=True, text=True).stdout
    if phase == "export":
        assert portable.read_bytes() == before
        assert not staged
    else:
        assert json.loads(portable.read_text())["status"] == "closed"
        assert staged.strip() == ".beads/issues.jsonl"


@pytest.mark.parametrize("phase", ["export", "cleanup"])
@pytest.mark.parametrize("runtime", [{"effects": ["beads-write", "repo-write", "git-commit"]}], indirect=True)
def test_export_and_cleanup_keep_pinned_objects_when_parent_moves(runtime, monkeypatch, phase):
    portable = prepare_closeout(runtime, monkeypatch)
    exporter = closeout_backend(runtime, monkeypatch)
    foreign = runtime["root"] / "foreign-portable"
    foreign.mkdir()
    sentinel = b"unrelated foreign state\n"
    (foreign / "issues.jsonl").write_bytes(sentinel)
    moved_name = None
    def redirect(name):
        nonlocal moved_name
        moved_name = Path(name).name
        (foreign / moved_name).write_bytes(sentinel)
        portable.parent.rename(runtime["repo"] / "saved-beads")
        portable.parent.symlink_to(foreign, target_is_directory=True)
    if phase == "export":
        original_run = subprocess.run
        def run(args, *positional, **kwargs):
            if args[0] == str(exporter):
                assert "-o" not in args
                assert hasattr(kwargs["stdout"], "fileno")
                redirect(next(portable.parent.glob("issues-*.jsonl")))
            return original_run(args, *positional, **kwargs)
        monkeypatch.setattr(subprocess, "run", run)
    else:
        exporter.write_text(exporter.read_text() + "\nsys.exit(1)\n")
        original_unlink = runtime["work"].os.unlink
        def unlink(name, **kwargs):
            if Path(name).name.startswith("issues-"):
                redirect(name)
            return original_unlink(name, **kwargs)
        monkeypatch.setattr(runtime["work"].os, "unlink", unlink)
    result = runtime["work"].direct_closeout("pi-a", outcome="success", reason="fixture complete")
    assert result["status"] == "partial"
    assert moved_name is not None
    assert (foreign / moved_name).read_bytes() == sentinel
    assert (foreign / "issues.jsonl").read_bytes() == sentinel
    assert not (runtime["repo"] / "saved-beads" / moved_name).exists()
