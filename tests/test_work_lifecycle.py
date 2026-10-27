"""Transition journal invariants with real private state and fault injection."""
from __future__ import annotations

import importlib
from pathlib import Path

import pytest


def test_lifecycle_service_available(agnt):
    assert importlib.util.find_spec("agnt_lib.work_lifecycle"), "resumable lifecycle service is missing"


@pytest.fixture
def lifecycle(agnt):
    return importlib.import_module("agnt_lib.work_lifecycle")


def setup_attempt(lifecycle, tmp_path):
    repo = tmp_path / "checkout"
    repo.mkdir()
    (repo / "unfinished.txt").write_text("preserve dirty work")
    journal = lifecycle.LifecycleStore(tmp_path / "journal")
    journal.claim("pi-a", "session-a", str(repo))
    cp = journal.checkpoint("pi-a", "session-a", {
        "objective": "deliver feature", "decisions": ["keep history"], "completed": ["tests"],
        "next": ["implementation"], "blockers": [], "verification": ["red observed"],
        "ownedPaths": ["unfinished.txt"], "artifactRefs": [], "assignmentRef": "assignment-a",
    })
    return journal, repo, cp


def prepare(journal, repo, cp, *, target="pi-a", source="session-a", checkout=None, allowed=True):
    return journal.prepare(
        source_session=source, checkpoint_ref=cp["id"], target_bead=target,
        target_checkout=str(checkout or repo), target_status="in_progress",
        blockers=[], mode="resume" if target == cp["bead"] else "switch",
        runtime_ready=True, authorize=lambda _request: allowed,
    )


def test_inv1_same_bead_resume_is_idempotent_and_preserves_work(lifecycle, tmp_path):  # Tests INV-1
    journal, repo, cp = setup_attempt(lifecycle, tmp_path)
    tx = prepare(journal, repo, cp)
    assert prepare(journal, repo, cp) == tx
    assert tx["state"] == "prepared"
    staged = journal.stage(tx["id"], child_session_file=str(tmp_path / "child.jsonl"))
    assert staged["childSession"] == tx["childSession"]
    calls = []
    attached = journal.attach(tx["id"], session_id=tx["childSession"], authorize=lambda _: True,
                              attach=lambda bead, session: calls.append((bead, session)))
    assert attached["state"] == "attached"
    assert journal.attach(tx["id"], session_id=tx["childSession"], authorize=lambda _: True,
                          attach=lambda *_: pytest.fail("duplicate attach")) == attached
    assert calls == [("pi-a", tx["childSession"])]
    assert (repo / "unfinished.txt").read_text() == "preserve dirty work"
    assert journal.status(tx["id"])["checkpointRef"] == cp["id"]
    with pytest.raises(ValueError, match="ownership"):
        journal.claim("pi-a", "session-a", str(repo))


def test_inv2_switch_and_return_preserves_source_checkpoint(lifecycle, tmp_path):  # Tests INV-2
    journal, repo, cp = setup_attempt(lifecycle, tmp_path)
    isolated = tmp_path / "isolated"
    isolated.mkdir()
    tx = prepare(journal, repo, cp, target="pi-b", checkout=isolated)
    journal.stage(tx["id"], child_session_file=str(tmp_path / "b.jsonl"))
    journal.attach(tx["id"], session_id=tx["childSession"], authorize=lambda _: True, attach=lambda *_: None)
    cp_b = journal.checkpoint("pi-b", tx["childSession"], {**cp["progress"], "next": ["return to A"]})
    back = prepare(journal, isolated, cp_b, source=tx["childSession"], target="pi-a", checkout=repo)
    journal.stage(back["id"], child_session_file=str(tmp_path / "a2.jsonl"))
    journal.attach(back["id"], session_id=back["childSession"], authorize=lambda _: True, attach=lambda *_: None)
    assert journal.latest_checkpoint("pi-a")["id"] == cp["id"]
    assert (repo / "unfinished.txt").read_text() == "preserve dirty work"


def test_identical_progress_continuations_are_bounded(lifecycle, tmp_path):
    journal, repo, cp = setup_attempt(lifecycle, tmp_path)
    source = "session-a"
    for index in range(3):
        tx = prepare(journal, repo, cp, source=source)
        journal.stage(tx["id"], child_session_file=str(tmp_path / f"child-{index}.jsonl"))
        journal.attach(tx["id"], session_id=tx["childSession"], authorize=lambda _: True, attach=lambda *_: None)
        source = tx["childSession"]
        cp = journal.checkpoint("pi-a", source, cp["progress"])
    with pytest.raises(ValueError, match="unchanged progress"):
        prepare(journal, repo, cp, source=source)
    assert journal.owner("pi-a")["phase"] == "active"
    (repo / "unfinished.txt").write_text("new measured progress")
    cp = journal.checkpoint("pi-a", source, cp["progress"])
    assert prepare(journal, repo, cp, source=source)["state"] == "prepared"


def test_pending_transition_blocks_completed_checkout_release(lifecycle, tmp_path):
    journal, repo, cp = setup_attempt(lifecycle, tmp_path)
    tx = prepare(journal, repo, cp)
    with pytest.raises(ValueError, match="pending transition"):
        journal.release_completed("pi-a", "session-a")
    assert journal.owner("pi-a")["phase"] == "active"
    journal.cancel(tx["id"], source_session="session-a")
    journal.release_completed("pi-a", "session-a")
    assert journal.owner("pi-a")["phase"] == "completed"


def test_fail1_foreign_session_cannot_claim_or_prepare(lifecycle, tmp_path):  # Tests FAIL-1
    journal, repo, cp = setup_attempt(lifecycle, tmp_path)
    with pytest.raises(ValueError, match="ownership"):
        journal.claim("pi-a", "same-human-other-session", str(repo))
    with pytest.raises(ValueError, match="ownership"):
        prepare(journal, repo, cp, source="foreign-session")


def test_fail2_dirty_cross_bead_switch_requires_isolation(lifecycle, tmp_path):  # Tests FAIL-2
    journal, repo, cp = setup_attempt(lifecycle, tmp_path)
    with pytest.raises(ValueError, match="isolation"):
        prepare(journal, repo, cp, target="pi-b")
    assert (repo / "unfinished.txt").read_text() == "preserve dirty work"


def test_fail3_changed_snapshot_stops_staging(lifecycle, tmp_path):  # Tests FAIL-3
    journal, repo, cp = setup_attempt(lifecycle, tmp_path)
    tx = prepare(journal, repo, cp)
    (repo / "unfinished.txt").write_text("concurrent change")
    with pytest.raises(ValueError, match="changed"):
        journal.stage(tx["id"], child_session_file=str(tmp_path / "child.jsonl"))
    assert journal.status(tx["id"])["state"] == "prepared"


def test_inv3_failed_attach_recovers_exact_reservation(lifecycle, tmp_path):  # Tests INV-3
    journal, repo, cp = setup_attempt(lifecycle, tmp_path)
    tx = prepare(journal, repo, cp)
    journal.stage(tx["id"], child_session_file=str(tmp_path / "child.jsonl"))
    def fail(*_):
        raise OSError("after claim, before link")
    with pytest.raises(OSError):
        journal.attach(tx["id"], session_id=tx["childSession"], authorize=lambda _: True, attach=fail)
    reopened = lifecycle.LifecycleStore(journal.root)
    assert reopened.status(tx["id"])["state"] == "attaching"
    assert reopened.recover(tx["id"])["requiredAction"] == "reconcile-attachment"
    reconciled = reopened.attach(tx["id"], session_id=tx["childSession"], authorize=lambda _: True,
                                attached=lambda *_: True, attach=lambda *_: pytest.fail("already linked"))
    assert reconciled["state"] == "attached"


def test_fail4_revocation_on_attach_does_not_steal_owner(lifecycle, tmp_path):  # Tests FAIL-4
    journal, repo, cp = setup_attempt(lifecycle, tmp_path)
    tx = prepare(journal, repo, cp)
    journal.stage(tx["id"], child_session_file=str(tmp_path / "child.jsonl"))
    with pytest.raises(ValueError, match="authority"):
        journal.attach(tx["id"], session_id=tx["childSession"], authorize=lambda _: False,
                       attach=lambda *_: pytest.fail("revoked"))
    assert journal.status(tx["id"])["state"] == "staged"


def test_inv4_prelaunch_cancel_leaves_source_usable(lifecycle, tmp_path):  # Tests INV-4
    journal, repo, cp = setup_attempt(lifecycle, tmp_path)
    tx = prepare(journal, repo, cp)
    journal.cancel(tx["id"], source_session="session-a")
    journal.claim("pi-a", "session-a", str(repo))
    with pytest.raises(ValueError, match="cancelled"):
        journal.stage(tx["id"], child_session_file=str(tmp_path / "child.jsonl"))


@pytest.mark.parametrize("status", ["closed", "deferred", "blocked"])
def test_fail5_ineligible_target_is_not_reopened(lifecycle, tmp_path, status):  # Tests FAIL-5
    journal, repo, cp = setup_attempt(lifecycle, tmp_path)
    with pytest.raises(ValueError, match="target"):
        journal.prepare(source_session="session-a", checkpoint_ref=cp["id"], target_bead="pi-a",
                        target_checkout=str(repo), target_status=status, blockers=[], mode="resume",
                        runtime_ready=True, authorize=lambda _: True)


def test_fail6_unavailable_runtime_leaves_source_active(lifecycle, tmp_path):  # Tests FAIL-6
    journal, repo, cp = setup_attempt(lifecycle, tmp_path)
    with pytest.raises(ValueError, match="runtime"):
        journal.prepare(source_session="session-a", checkpoint_ref=cp["id"], target_bead="pi-a",
                        target_checkout=str(repo), target_status="open", blockers=[], mode="resume",
                        runtime_ready=False, authorize=lambda _: True)
    journal.claim("pi-a", "session-a", str(repo))


def test_fail7_target_reservation_prevents_same_actor_race(lifecycle, tmp_path):  # Tests FAIL-7
    journal, repo, cp = setup_attempt(lifecycle, tmp_path)
    target = tmp_path / "target"
    target.mkdir()
    prepare(journal, repo, cp, target="pi-b", checkout=target)
    with pytest.raises(ValueError, match="ownership"):
        journal.claim("pi-b", "competitor", str(target))


def test_latest_checkpoint_survives_sorted_serialization(lifecycle, tmp_path):
    journal, repo, cp = setup_attempt(lifecycle, tmp_path)
    latest = journal.checkpoint("pi-a", "session-a", {**cp["progress"], "next": ["new next work"]})
    assert lifecycle.LifecycleStore(journal.root).latest_checkpoint("pi-a") == latest


def test_staged_but_not_attaching_transition_can_cancel(lifecycle, tmp_path):
    journal, repo, cp = setup_attempt(lifecycle, tmp_path)
    tx = prepare(journal, repo, cp)
    journal.stage(tx["id"], child_session_file=str(tmp_path / "child.jsonl"))
    journal.cancel(tx["id"], source_session="session-a")
    journal.claim("pi-a", "session-a", str(repo))
    with pytest.raises(ValueError, match="staged"):
        journal.attach(tx["id"], session_id=tx["childSession"], authorize=lambda _: True,
                       attach=lambda *_: pytest.fail("cancelled child must not attach"))


def test_distinct_sessions_can_claim_distinct_beads_in_same_checkout(lifecycle, tmp_path):
    journal, repo, _ = setup_attempt(lifecycle, tmp_path)
    owner = journal.owner("pi-a")
    journal.claim("pi-b", "session-b", str(repo))
    assert journal.owner("pi-a") == owner
    assert journal.owner("pi-b") == {"session": "session-b", "checkout": str(repo), "phase": "active"}
    assert (repo / "unfinished.txt").read_text() == "preserve dirty work"


@pytest.mark.parametrize("separate_checkout", [False, True])
def test_session_cannot_claim_second_bead(lifecycle, tmp_path, separate_checkout):  # Tests FAIL-1
    journal, repo, _ = setup_attempt(lifecycle, tmp_path)
    checkout = tmp_path / "other" if separate_checkout else repo
    checkout.mkdir(exist_ok=True)
    with pytest.raises(ValueError, match="session ownership"):
        journal.claim("pi-b", "session-a", str(checkout))
    assert journal.owner("pi-b") is None


@pytest.mark.parametrize("phase", ["active", "paused", "reserved", "yielding"])
def test_prepare_cannot_reserve_another_beads_checkout(lifecycle, tmp_path, phase):
    journal, repo, cp = setup_attempt(lifecycle, tmp_path)
    occupied = tmp_path / "occupied"
    occupied.mkdir()
    journal.claim("pi-c", "session-c", str(occupied))
    with journal.locked() as state:
        state["owners"]["pi-c"]["phase"] = phase
        journal._write(state)
    with pytest.raises(ValueError, match="target checkout ownership conflict"):
        prepare(journal, repo, cp, target="pi-b", checkout=occupied)


@pytest.mark.parametrize("target", ["pi-a", "pi-b"])
def test_prepare_ignores_completed_checkout_owners(lifecycle, tmp_path, target):
    journal, repo, cp = setup_attempt(lifecycle, tmp_path)
    checkout = repo if target == "pi-a" else tmp_path / "target"
    checkout.mkdir(exist_ok=True)
    for bead in ("pi-c", "pi-d"):
        journal.claim(bead, f"session-{bead}", str(checkout))
        journal.release_completed(bead, f"session-{bead}")
    owners = {bead: journal.owner(bead) for bead in ("pi-c", "pi-d")}

    tx = prepare(journal, repo, cp, target=target, checkout=checkout)

    assert tx["state"] == "prepared"
    assert tx["checkpointRef"] == cp["id"]
    assert {bead: journal.owner(bead) for bead in owners} == owners
    assert (repo / "unfinished.txt").read_text() == "preserve dirty work"


def test_uncertain_attach_requires_inspection_before_retry(lifecycle, tmp_path):
    journal, repo, cp = setup_attempt(lifecycle, tmp_path)
    tx = prepare(journal, repo, cp)
    journal.stage(tx["id"], child_session_file=str(tmp_path / "child.jsonl"))
    calls = []
    def uncertain(*_):
        calls.append("applied")
        raise OSError("response lost after effect")
    with pytest.raises(OSError):
        journal.attach(tx["id"], session_id=tx["childSession"], authorize=lambda _: True, attach=uncertain)
    with pytest.raises(ValueError, match="reconcil"):
        journal.attach(tx["id"], session_id=tx["childSession"], authorize=lambda _: True, attach=uncertain)
    assert calls == ["applied"]


def test_cross_bead_attach_detects_poststage_source_write(lifecycle, tmp_path):
    journal, repo, cp = setup_attempt(lifecycle, tmp_path)
    target = tmp_path / "target"
    target.mkdir()
    tx = prepare(journal, repo, cp, target="pi-b", checkout=target)
    journal.stage(tx["id"], child_session_file=str(tmp_path / "child.jsonl"))
    (repo / "unfinished.txt").write_text("unexpected source edit")
    with pytest.raises(ValueError, match="source workspace changed"):
        journal.attach(tx["id"], session_id=tx["childSession"], authorize=lambda _: True, attach=lambda *_: None)
    assert journal.status(tx["id"])["state"] == "staged"


def test_snapshot_does_not_follow_symlinks(lifecycle, tmp_path):
    outside = tmp_path / "outside"
    outside.write_text("private")
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "link").symlink_to(outside)
    before = lifecycle.workspace_snapshot(str(repo))
    outside.write_text("changed outside")
    assert lifecycle.workspace_snapshot(str(repo)) == before
    assert str(Path(repo).resolve()) == before["checkout"]
