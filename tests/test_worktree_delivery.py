"""Native local isolation effects; all Git/Beads state is disposable."""
from __future__ import annotations

import json
import os
from pathlib import Path
import select
import shlex
import signal
import subprocess
import sys

import pytest

from test_authority import admitted, authority  # noqa: F401


def run(cwd, *args):
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def native(agnt, authority, tmp_path, monkeypatch):
    from agnt_lib import delivery, worktree_policy
    for key in list(os.environ):
        if key.startswith(("BD_", "BEADS_", "GIT_")):
            monkeypatch.delenv(key)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    repo = tmp_path / "repo"
    repo.mkdir()
    run(repo, "git", "init", "-q")
    run(repo, "git", "config", "user.name", "Fixture")
    run(repo, "git", "config", "user.email", "fixture@example.invalid")
    (repo / "source.txt").write_text("committed base")
    run(repo, "git", "add", "source.txt")
    run(repo, "git", "commit", "-qm", "base")
    owner, _ = admitted(authority, tmp_path)
    owner.assign("queue", repository=str(repo), beads=["pi-a", "pi-b"],
                 effects=["worktree-create"], intent_ref="fixture:assigned-isolation")
    store = delivery.DeliveryStore(tmp_path / "receipts", authority=owner)
    return repo, store, owner, worktree_policy


def test_native_worktree_adapter_exists(agnt):
    from agnt_lib import worktree_policy
    assert hasattr(worktree_policy, "WorktreeCreationAdapter"), "native isolation adapter is missing"


def test_native_creation_preserves_dirty_source_and_replays_once(native):
    from agnt_lib.work_lifecycle import workspace_snapshot
    repo, store, _, policy = native
    (repo / "source.txt").write_text("unfinished edits")
    (repo / "unrelated.txt").write_text("preserve")
    before = workspace_snapshot(str(repo))
    adapter = policy.WorktreeCreationAdapter(repo, "pi-b")
    prepared = store.prepare("queue", adapter)
    assert prepared["status"] == "prepared"
    facts = prepared["receipt"]["action"]["facts"]
    target = Path(facts["checkout"])
    assert not target.exists() and not target.is_relative_to(repo)
    result = store.execute(prepared["receipt"]["id"], adapter)
    assert result["status"] == "applied"
    assert (target / "source.txt").read_text() == "committed base"
    assert run(target, "git", "symbolic-ref", "--short", "HEAD") == facts["branch"]
    assert workspace_snapshot(str(repo)) == before
    assert store.execute(prepared["receipt"]["id"], adapter)["status"] == "applied"
    assert len(policy.list_git_worktrees(repo_root=repo)) == 2


def test_target_collision_blocks_creation(native):
    repo, store, _, policy = native
    adapter = policy.WorktreeCreationAdapter(repo, "pi-b")
    prepared = store.prepare("queue", adapter)
    assert prepared["status"] == "prepared"
    target = Path(prepared["receipt"]["action"]["facts"]["checkout"])
    adapter.managed_root.mkdir(parents=True, mode=0o700)
    target.parent.mkdir(mode=0o700)
    target.mkdir(mode=0o700)
    (target / "foreign.txt").write_text("never replace")
    assert store.execute(prepared["receipt"]["id"], adapter)["status"] == "blocked"
    assert (target / "foreign.txt").read_text() == "never replace"
    assert len(policy.list_git_worktrees(repo_root=repo)) == 1


def test_new_source_commit_requires_fresh_preparation(native):
    repo, store, _, policy = native
    adapter = policy.WorktreeCreationAdapter(repo, "pi-b")
    prepared = store.prepare("queue", adapter)
    target = Path(prepared["receipt"]["action"]["facts"]["checkout"])
    run(repo, "git", "commit", "--allow-empty", "-qm", "moved base")
    assert store.execute(prepared["receipt"]["id"], adapter)["status"] == "blocked"
    assert not target.exists()


def test_failed_ref_lookup_cannot_prove_absence(native, monkeypatch):
    repo, store, _, policy = native
    adapter = policy.WorktreeCreationAdapter(repo, "pi-b")
    ref = store.prepare("queue", adapter)["receipt"]["id"]
    original = policy._isolation_git
    def broken(cwd, *args, **kwargs):
        if args[-1].startswith("refs/heads/work/"):
            return subprocess.CompletedProcess(args, 128, "", "fixture ref database unavailable")
        return original(cwd, *args, **kwargs)
    monkeypatch.setattr(policy, "_isolation_git", broken)
    assert store.reconcile(ref, adapter)["status"] == "uncertain"


def test_project_command_filter_is_refused_without_execution(native):
    repo, store, _, policy = native
    marker = repo.parent / "must-not-exist"
    run(repo, "git", "config", "filter.unsafe.clean", f"touch {marker}")
    (repo / ".gitattributes").write_text("*.txt filter=unsafe\n")
    assert store.prepare("queue", policy.WorktreeCreationAdapter(repo, "pi-b"))["status"] == "blocked"
    assert not marker.exists()


def test_explicit_core_worktree_cannot_redirect_nested_checkout(native):
    repo, store, _, policy = native
    run(repo, "git", "config", "core.worktree", str(repo))
    assert store.prepare("queue", policy.WorktreeCreationAdapter(repo, "pi-b"))["status"] == "blocked"
    assert (repo / "source.txt").read_text() == "committed base"
    assert len(policy.list_git_worktrees(repo_root=repo)) == 1


def test_native_writer_keeps_leases_after_issuing_host_aborts(native, monkeypatch):
    repo, store, _, policy = native
    (repo / ".gitattributes").write_text("*.txt filter=fixture-pause\n")
    run(repo, "git", "add", ".gitattributes")
    run(repo, "git", "commit", "-qm", "controlled native filter fixture")
    gate = repo.parent / "release-writer"
    os.mkfifo(gate)
    script = repo.parent / "pause-filter.py"
    script.write_text(
        "import sys\ndata = sys.stdin.buffer.read()\n"
        "print('fixture-native-writer-ready', file=sys.stderr, flush=True)\n"
        "with open(sys.argv[1], 'rb') as gate: gate.read(1)\n"
        "sys.stdout.buffer.write(data)\n"
    )
    # Global configuration belongs only to this fixture's isolated HOME. The
    # normal integration trust boundary permits owner-controlled global tools.
    run(repo, "git", "config", "--global", "filter.fixture-pause.smudge",
        shlex.join([sys.executable, str(script), str(gate)]))
    adapter = policy.WorktreeCreationAdapter(repo, "pi-b")
    ref = store.prepare("queue", adapter)["receipt"]["id"]
    original_run = subprocess.run
    children = []
    def abort_after_spawn(command, *args, **kwargs):
        if "worktree" in command and command[command.index("worktree") + 1] == "add":
            assert kwargs["pass_fds"]
            options = {key: value for key, value in kwargs.items() if key not in {"capture_output", "check"}}
            child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     start_new_session=True, **options)
            children.append(child)
            raise SystemExit("fixture issuing host aborted after native spawn")
        return original_run(command, *args, **kwargs)
    monkeypatch.setattr(policy.subprocess, "run", abort_after_spawn)
    try:
        with pytest.raises(SystemExit):
            store.execute(ref, adapter)
        child = children[0]
        readable, _, _ = select.select([child.stderr], [], [], 10)
        assert readable and child.stderr.readline().strip() == "fixture-native-writer-ready"
        assert store.inspect(ref)["status"] == "started"
        # Parent lease descriptors closed during exception unwinding; real Git
        # still owns inherited descriptors while its checkout/filter is live.
        with pytest.raises(ValueError, match="busy"):
            store.reconcile(ref, adapter)
        with gate.open("wb") as release:
            release.write(b"1")
        assert child.wait(timeout=10) == 0
        assert store.reconcile(ref, adapter)["status"] == "applied"
        assert store.execute(ref, adapter)["status"] == "applied"
        assert len(children) == 1
    finally:
        for child in children:
            try:
                os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            child.wait(timeout=10)
            child.stdout.close()
            child.stderr.close()


def test_native_beads_worktree_reads_shared_current_database(native):
    repo, _, _, _ = native
    run(repo, "bd", "init", "--prefix", "probe", "--skip-agents", "--skip-hooks", "--non-interactive")
    run(repo, "bd", "export", "--readonly", "-o", str(repo / ".beads/issues.jsonl"))
    run(repo, "git", "add", ".beads")
    run(repo, "git", "commit", "-qm", "portable baseline")
    issue = json.loads(run(repo, "bd", "create", "--title", "Created after commit", "--type", "task", "--json"))
    child = repo.parent / "child"
    run(repo, "git", "worktree", "add", "-qb", "fixture-child", str(child))
    found = json.loads(run(child, "bd", "show", issue["id"], "--json"))
    assert found[0]["id"] == issue["id"]
