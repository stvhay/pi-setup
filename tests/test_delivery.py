"""Concrete effect receipts: no retry authority from an unknown outcome."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import copy
import importlib
import json
import os
from pathlib import Path
from threading import Event

import pytest

from test_authority import admitted, authority  # noqa: F401


class FakeAdapter:
    kind = "fixture-provider"

    def __init__(self, repo: Path):
        self.action = {
            "schemaVersion": 1, "adapter": self.kind, "repository": str(repo), "bead": "pi-a",
            "effects": ["branch-push"], "decisionRefs": [],
            "target": {"identity": "provider:repo:branch", "repository": str(repo), "verified": True,
                       "resources": ["provider:repo:refs/heads/task"]},
            "source": {"identity": "commit:one", "rule": "verified-task-owned-commit"},
            "facts": {"expectedTargetVersion": "fixture:none"},
            "preconditions": {key: True for key in ("identity", "platform", "effectClosure", "verification", "recovery")},
            "verification": ["fixture:passing-gates"], "recovery": "Observe exact provider state; never force",
        }
        self.state = "not-applied"
        self.calls = 0
        self.on_execute = None
        self.observation_target = None

    def resolve(self):
        return copy.deepcopy(self.action)

    def execute(self, action, *, lease_fds):
        assert action == self.action
        assert lease_fds and all(os.fstat(fd).st_size >= 0 for fd in lease_fds)
        self.calls += 1
        if self.on_execute:
            self.on_execute()
        else:
            self.state = "applied"

    def observe(self, action, *, attempted):
        return {"status": self.state, "targetIdentity": self.observation_target or action["target"]["identity"],
                "sourceIdentity": action["source"]["identity"], "evidenceRefs": ["fixture:provider-observation"]}


@pytest.fixture
def delivery(agnt):
    assert importlib.util.find_spec("agnt_lib.delivery"), "delivery service is missing"
    return importlib.import_module("agnt_lib.delivery")


@pytest.fixture
def setup(delivery, authority, tmp_path):
    owner, _ = admitted(authority, tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    owner.assign("queue", repository=str(repo), beads=["pi-a", "pi-b"],
                 effects=["branch-push", "release", "worktree-create"], intent_ref="fixture:user-delivery")
    store = delivery.DeliveryStore(tmp_path / "delivery", authority=owner)
    return store, FakeAdapter(repo), owner


def test_terminal_departure_requires_settled_own_effects(setup):
    store, adapter, _ = setup
    store.assert_settled("queue", "pi-a")
    ref = store.prepare("queue", adapter)["receipt"]["id"]
    with pytest.raises(ValueError, match="unresolved admitted effects"):
        store.assert_settled("queue", "pi-a")
    store.assert_settled("queue", "pi-b")
    store.execute(ref, adapter)
    store.assert_settled("queue", "pi-a")


def test_delivery_service_available(agnt):
    assert importlib.util.find_spec("agnt_lib.delivery"), "delivery service is missing"


def test_prepare_execute_and_replay_are_one_effect(setup):
    store, adapter, _ = setup
    first = store.prepare("queue", adapter)
    assert first["status"] == "prepared"
    assert store.prepare("queue", adapter)["receipt"]["id"] == first["receipt"]["id"]
    assert adapter.calls == 0
    ref = first["receipt"]["id"]
    result = store.execute(ref, adapter)
    assert result["status"] == "applied"
    assert result["receipt"]["action"] == first["receipt"]["action"]
    assert store.execute(ref, adapter)["status"] == "applied"
    assert adapter.calls == 1
    assert [event["phase"] for event in result["receipt"]["events"]] == ["prepared", "started", "applied"]


def test_fresh_observation_does_not_rewrite_terminal_history_or_replay(setup):
    store, adapter, owner = setup
    ref = store.prepare("queue", adapter)["receipt"]["id"]
    historical = store.execute(ref, adapter)
    adapter.state = "not-applied"  # External state changed after successful effect.
    owner.revoke("fixture owner revoked writes")
    fresh = store.observe_current(ref, adapter)
    assert fresh["status"] == "not-applied" and fresh["historicalStatus"] == "applied"
    assert fresh["observation"]["sourceIdentity"] == adapter.action["source"]["identity"]
    assert store.inspect(ref) == historical and adapter.calls == 1
    adapter.observation_target = "different:target"
    assert store.observe_current(ref, adapter)["status"] == "uncertain"
    assert store.inspect(ref) == historical and adapter.calls == 1


def test_already_applied_observation_does_not_mutate(setup):
    store, adapter, _ = setup
    ref = store.prepare("queue", adapter)["receipt"]["id"]
    adapter.state = "applied"
    result = store.execute(ref, adapter)
    assert result["status"] == "applied" and adapter.calls == 0
    assert not any(event["phase"] == "started" for event in result["receipt"]["events"])


def test_crash_after_effect_reconciles_without_replay(setup):
    store, adapter, _ = setup
    ref = store.prepare("queue", adapter)["receipt"]["id"]
    def crash():
        adapter.state = "applied"
        raise SystemExit("fixture host crash")
    adapter.on_execute = crash
    with pytest.raises(SystemExit):
        store.execute(ref, adapter)
    assert store.inspect(ref)["status"] == "started"
    assert store.execute(ref, adapter)["status"] == "applied"
    assert adapter.calls == 1


def test_uncertain_effect_blocks_new_intent_and_overlapping_adapter(setup):
    store, adapter, _ = setup
    ref = store.prepare("queue", adapter)["receipt"]["id"]
    adapter.on_execute = lambda: setattr(adapter, "state", "uncertain")
    assert store.execute(ref, adapter)["status"] == "uncertain"
    changed = FakeAdapter(Path(adapter.action["repository"]))
    changed.action["source"]["identity"] = "commit:two"
    changed.kind = changed.action["adapter"] = "other-provider"
    changed.action["target"]["resources"].append("provider:repo:release")
    assert store.prepare("queue", changed)["status"] == "blocked"
    assert store.cancel(ref, "try another id")["status"] == "blocked"
    assert store.execute(ref, adapter)["status"] == "uncertain"
    assert adapter.calls == 1
    adapter.state = "applied"
    assert store.reconcile(ref, adapter)["status"] == "applied"


@pytest.mark.parametrize("variation", ["new-id", "more-resources"])
def test_known_not_applied_retries_are_bounded_across_receipt_ids(setup, variation):
    store, adapter, _ = setup
    adapter.on_execute = lambda: None  # fixture provider proves terminal rejection
    for _ in range(3):
        ref = store.prepare("queue", adapter)["receipt"]["id"]
        assert store.execute(ref, adapter)["status"] == "not-applied"
        assert store.cancel(ref, "retry fresh receipt")["status"] == "cancelled"
    if variation == "more-resources":
        adapter.kind = adapter.action["adapter"] = "another-adapter"
        adapter.action["target"]["resources"] = sorted([*adapter.action["target"]["resources"], "provider:repo:audit"])
    ref = store.prepare("queue", adapter)["receipt"]["id"]
    assert store.execute(ref, adapter)["status"] == "blocked"
    assert adapter.calls == 3


def test_revocation_after_prepare_blocks_mutation_but_not_observation(setup):
    store, adapter, owner = setup
    ref = store.prepare("queue", adapter)["receipt"]["id"]
    owner.revoke("stop")
    assert store.execute(ref, adapter)["status"] == "blocked"
    assert adapter.calls == 0
    adapter.state = "applied"  # independent provider observation, not implied execution
    assert store.reconcile(ref, adapter)["status"] == "applied"
    assert adapter.calls == 0


@pytest.mark.parametrize("key", ["identity", "platform", "effectClosure", "verification", "recovery"])
def test_missing_precondition_never_reaches_effect(setup, key):
    store, adapter, _ = setup
    adapter.action["preconditions"][key] = False
    assert store.prepare("queue", adapter)["status"] == "blocked"
    assert adapter.calls == 0


@pytest.mark.parametrize("boundary", ["resolve", "observe"])
def test_provider_errors_are_bounded_without_sensitive_details(setup, boundary):
    store, adapter, _ = setup
    def unavailable(*_args, **_kwargs):
        raise RuntimeError("fixture-sensitive-provider-detail")
    if boundary == "resolve":
        adapter.resolve = unavailable
        result = store.prepare("queue", adapter)
        assert result["status"] == "blocked"
    else:
        ref = store.prepare("queue", adapter)["receipt"]["id"]
        adapter.observe = unavailable
        result = store.execute(ref, adapter)
        assert result["status"] == "uncertain"
    assert "fixture-sensitive-provider-detail" not in str(result)
    assert adapter.calls == 0


@pytest.mark.parametrize("version", [True, 2, "1"])
def test_invalid_action_version_is_not_coerced(setup, version):
    store, adapter, _ = setup
    adapter.action["schemaVersion"] = version
    assert store.prepare("queue", adapter)["status"] == "blocked"


def test_changed_native_facts_require_new_preparation(setup):
    store, adapter, _ = setup
    adapter.action["facts"] = {"expectedTargetVersion": "provider-v1"}
    prepared = store.prepare("queue", adapter)
    assert prepared["status"] == "prepared"
    adapter.action["facts"]["expectedTargetVersion"] = "provider-v2"
    assert store.execute(prepared["receipt"]["id"], adapter)["status"] == "blocked"
    assert adapter.calls == 0


def test_changed_source_requires_new_preparation(setup):
    store, adapter, _ = setup
    ref = store.prepare("queue", adapter)["receipt"]["id"]
    adapter.action["source"]["identity"] = "commit:changed"
    assert store.execute(ref, adapter)["status"] == "blocked"
    assert adapter.calls == 0
    assert store.cancel(ref, "source changed before execution")["status"] == "cancelled"
    assert store.prepare("queue", adapter)["status"] == "prepared"


def test_wrong_observation_identity_cannot_prove_success(setup):
    store, adapter, _ = setup
    ref = store.prepare("queue", adapter)["receipt"]["id"]
    adapter.state = "applied"
    adapter.observation_target = "foreign:target"
    assert store.execute(ref, adapter)["status"] == "uncertain"
    assert adapter.calls == 0


def test_overlapping_resources_reserve_once_but_independent_work_proceeds(setup):
    store, adapter, _ = setup
    assert store.prepare("queue", adapter)["status"] == "prepared"
    other = FakeAdapter(Path(adapter.action["repository"]))
    other.action["bead"] = "pi-b"
    assert store.prepare("queue", other)["status"] == "blocked"
    other.action["target"]["identity"] = "provider:other:branch"
    other.action["target"]["resources"] = ["provider:other:branch"]
    second = store.prepare("queue", other)
    assert store.execute(second["receipt"]["id"], other)["status"] == "applied"


def test_live_resource_holder_returns_bounded_busy(setup):
    store, adapter, _ = setup
    ref = store.prepare("queue", adapter)["receipt"]["id"]
    entered, release = Event(), Event()
    def effect():
        entered.set()
        assert release.wait(5)
        adapter.state = "applied"
    adapter.on_execute = effect
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(store.execute, ref, adapter)
        assert entered.wait(3)
        second = pool.submit(store.execute, ref, adapter)
        try:
            with pytest.raises(ValueError, match="busy"):
                second.result(timeout=1)
        finally:
            release.set()
        assert first.result(timeout=5)["status"] == "applied"
    assert adapter.calls == 1


def test_corrupt_receipt_state_never_restarts_effect(setup):
    store, adapter, _ = setup
    ref = store.prepare("queue", adapter)["receipt"]["id"]
    (store.root / "state.json").write_text("{}")
    with pytest.raises(ValueError, match="receipt"):
        store.execute(ref, adapter)
    assert adapter.calls == 0


def test_invalid_phase_history_cannot_reopen_started_receipt(setup, delivery):
    store, adapter, _ = setup
    ref = store.prepare("queue", adapter)["receipt"]["id"]
    path = store.root / "state.json"
    envelope = json.loads(path.read_text())
    events = envelope["state"]["receipts"][ref]["events"]
    for phase in ("started", "prepared"):
        events.append({"phase": phase, "at": events[0]["at"], "evidence": {}})
    envelope["fingerprint"] = delivery.fingerprint(envelope["state"])
    path.write_text(json.dumps(envelope))
    with pytest.raises(ValueError, match="receipt"):
        store.inspect(ref)


def test_symlink_receipt_root_is_refused(delivery, authority, tmp_path):
    owner, _ = admitted(authority, tmp_path)
    target = tmp_path / "target"
    target.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(target, target_is_directory=True)
    store = delivery.DeliveryStore(linked, authority=owner)
    repo = tmp_path / "repo"
    repo.mkdir()
    with pytest.raises(ValueError, match="symlink"):
        store.inspect("a" * 32)
