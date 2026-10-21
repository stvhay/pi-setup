"""Pending decisions move UI bindings, never request identity or consent."""
from __future__ import annotations

from contextlib import contextmanager
import copy
import importlib
import json

import pytest

from test_approvals import FakeBeads, approval_preview, approval_record, capability_grant, human_ui_resolver


def test_decision_rebinding_service_exists(agnt):
    assert importlib.util.find_spec("agnt_lib.decision_rebinding"), "pending-decision rebinding is missing"


@pytest.fixture
def recovery(agnt, tmp_path, monkeypatch):
    from agnt_lib import approvals, decision_rebinding, quality, work_lifecycle

    monkeypatch.setattr(decision_rebinding, "binding_root", lambda: tmp_path / "bindings")
    monkeypatch.setattr(quality, "resolve_runtime_directory", lambda _: tmp_path / "quality")
    canonical = approval_record()
    beads = FakeBeads(show_metadata={"pi": {"approval": canonical}})
    quality.capture_session_link("child-session", "pi-work.1", beads_runner=beads)
    monkeypatch.setattr(work_lifecycle, "runtime_store", lambda *_: work_lifecycle.LifecycleStore(tmp_path / "lifecycle"))
    return decision_rebinding, approvals, quality, beads, canonical


def test_rebind_keeps_request_and_blocker_then_requires_human_answer(recovery):
    service, approvals, _, beads, canonical = recovery
    before = copy.deepcopy(canonical)
    proof = human_ui_resolver("child-session", "new-fixture-secret")
    result = service.rebind_pending_decision("pi-decision.1", resolver=proof, beads_runner=beads)
    assert result["status"] == "pending"
    assert result["decisionBead"] == "pi-decision.1"
    assert canonical == before
    assert not any(call[0] in {"create", "update", "close", "dep"} for call in beads.calls)
    with pytest.raises(ValueError, match="binding"):
        approvals.resolve_beads_approval_request(decision_bead="pi-decision.1", outcome="approved",
                                                resolver=human_ui_resolver(), beads_runner=beads)
    resolved = approvals.resolve_beads_approval_request(decision_bead="pi-decision.1", outcome="approved",
                                                       resolver=proof, beads_runner=beads)
    assert resolved["outcome"] == "approved"
    assert resolved["metadata"]["pi"]["approval"]["requestFingerprint"] == before["requestFingerprint"]


@pytest.mark.parametrize("status", ["rejected", "cancelled", "timed-out", "approved", "answered"])
def test_rebind_does_not_erase_a_prior_decision(recovery, status):
    service, _, _, beads, canonical = recovery
    canonical["status"] = status
    with pytest.raises(ValueError, match="pending"):
        service.rebind_pending_decision("pi-decision.1", resolver=human_ui_resolver("child-session"), beads_runner=beads)
    assert canonical["status"] == status


def test_rebind_denies_unassigned_or_foreign_session(recovery):
    service, _, _, beads, _ = recovery
    with pytest.raises(ValueError, match="ownership"):
        service.rebind_pending_decision("pi-decision.1", resolver=human_ui_resolver("foreign-session"), beads_runner=beads)


def test_rebind_rechecks_pending_state_inside_binding_lock(recovery, monkeypatch):
    service, _, _, beads, canonical = recovery
    original = service._locked
    @contextmanager
    def decision_changed_before_lock(decision):
        canonical["status"] = "rejected"
        with original(decision) as locked:
            yield locked
    monkeypatch.setattr(service, "_locked", decision_changed_before_lock)
    with pytest.raises(ValueError, match="pending"):
        service.rebind_pending_decision("pi-decision.1", resolver=human_ui_resolver("child-session"), beads_runner=beads)
    assert not list(service.binding_root().glob("*.json"))


def test_rebind_rejects_changed_scope(recovery):
    service, _, _, beads, canonical = recovery
    canonical["preview"]["scope"] = "a wider action"
    with pytest.raises(ValueError, match="preview changed"):
        service.rebind_pending_decision("pi-decision.1", resolver=human_ui_resolver("child-session"), beads_runner=beads)


def test_competing_resolution_cannot_be_overwritten_by_rebound_ui(recovery):
    service, approvals, _, beads, canonical = recovery
    proof = human_ui_resolver("child-session", "new-fixture-secret")
    service.rebind_pending_decision("pi-decision.1", resolver=proof, beads_runner=beads)
    canonical["status"] = "rejected"
    with pytest.raises(ValueError, match="pending"):
        approvals.resolve_beads_approval_request(decision_bead="pi-decision.1", outcome="approved",
                                                resolver=proof, beads_runner=beads)
    assert canonical["status"] == "rejected"
    assert not any(call[0] in {"update", "close"} for call in beads.calls)


def test_new_question_mode_is_immutable_request_scope(recovery, agnt):
    service, _, _, _, _ = recovery
    payload = agnt.approval_request_payload(
        kind="question", selection_mode="multi", target_bead="pi-work.1", question="Choose components",
        context="Original multi-select intent", options=["A", "B"], default="A", preview=approval_preview(),
        resolver_binding=human_ui_resolver(),
    )
    beads = FakeBeads(show_metadata=payload["metadata"])
    payload["metadata"]["pi"]["approval"]["selectionMode"] = "single"
    with pytest.raises(ValueError, match="preview changed"):
        service.rebind_pending_decision("pi-decision.1", resolver=human_ui_resolver("child-session"), beads_runner=beads)


@pytest.mark.parametrize("field,value", [("selectionMode", "single"), ("customResponseAllowed", False)])
def test_direct_question_resolution_validates_versioned_scope(recovery, agnt, field, value):
    _, approvals, _, _, _ = recovery
    payload = agnt.approval_request_payload(
        kind="question", selection_mode="multi", target_bead="pi-work.1", question="Choose components",
        context="Original multi-select intent", options=["A", "B"], default="A", preview=approval_preview(),
        resolver_binding=human_ui_resolver(),
    )
    beads = FakeBeads(show_metadata=payload["metadata"])
    payload["metadata"]["pi"]["approval"][field] = value
    with pytest.raises(ValueError, match="preview changed"):
        approvals.resolve_beads_approval_request(decision_bead="pi-decision.1", outcome="answered",
                                                custom_input="Alternative", resolver=human_ui_resolver(), beads_runner=beads)
    assert not any(call[0] in {"update", "close"} for call in beads.calls)


def test_direct_legacy_question_requires_mode_recovery(recovery):
    _, approvals, _, _, _ = recovery
    beads = FakeBeads(show_metadata={"pi": {"approval": approval_record(
        kind="question", options=["A", "B"], default="A", selectionMode="multi",
    )}})
    with pytest.raises(ValueError, match="legacy question.*recovery"):
        approvals.resolve_beads_approval_request(decision_bead="pi-decision.1", outcome="answered",
                                                selected_options=["A"], resolver=human_ui_resolver(), beads_runner=beads)
    assert not any(call[0] in {"update", "close"} for call in beads.calls)


def test_rebound_exact_grant_keeps_original_ceiling(recovery, agnt):
    service, approvals, _, _, _ = recovery
    payload = agnt.approval_request_payload(
        kind="approval", target_bead="pi-work.1", question="Approve original bounded work?",
        context="Same original scope after restart", options=["approve", "reject"], default="reject",
        preview=approval_preview(), grant=capability_grant(), resolver_binding=human_ui_resolver(),
    )
    beads = FakeBeads(show_metadata=payload["metadata"])
    original = copy.deepcopy(payload["metadata"]["pi"]["approval"])
    proof = human_ui_resolver("child-session", "new-fixture-secret")
    service.rebind_pending_decision("pi-decision.1", resolver=proof, beads_runner=beads)
    resolved = approvals.resolve_beads_approval_request(decision_bead="pi-decision.1", outcome="approved",
                                                       resolver=proof, beads_runner=beads)
    current = resolved["metadata"]["pi"]["approval"]
    assert current["requestFingerprint"] == original["requestFingerprint"]
    assert current["grantFingerprint"] == original["grantFingerprint"]
    assert current["resolverBinding"] == original["resolverBinding"]
    assert current["grant"]["revocation"]["status"] == "active"
    assert {key: value for key, value in current["grant"].items() if key != "revocation"} == {
        key: value for key, value in original["grant"].items() if key != "revocation"
    }


def test_rebound_question_preserves_structured_answer(recovery):
    service, approvals, _, _, _ = recovery
    beads = FakeBeads(show_metadata={"pi": {"approval": approval_record(
        kind="question", options=["A", "B"], default="A", selectionMode="multi",
        requestVersion=2, customResponseAllowed=True,
    )}})
    proof = human_ui_resolver("child-session", "new-fixture-secret")
    service.rebind_pending_decision("pi-decision.1", resolver=proof, beads_runner=beads)
    result = approvals.resolve_beads_approval_request(decision_bead="pi-decision.1", outcome="answered",
                                                      selected_options=["A"], custom_input="bounded alternative",
                                                      resolver=proof, beads_runner=beads)
    assert result["metadata"]["pi"]["approval"]["selectedOptions"] == ["A"]
    assert result["metadata"]["pi"]["approval"]["customInput"] == "bounded alternative"


@pytest.mark.parametrize("changed", [("selectionMode", "single"), ("customResponseAllowed", False)])
def test_legacy_question_requires_explicit_mode_verification(recovery, changed):
    service, approvals, _, _, _ = recovery
    canonical = approval_record(kind="question", options=["A", "B"], default="A", selectionMode="multi")
    beads = FakeBeads(show_metadata={"pi": {"approval": canonical}})
    original = canonical["requestFingerprint"]
    proof = human_ui_resolver("child-session", "new-fixture-secret")
    with pytest.raises(ValueError, match="selection mode.*verification"):
        service.rebind_pending_decision("pi-decision.1", resolver=proof, beads_runner=beads)
    result = service.rebind_pending_decision("pi-decision.1", resolver=proof, beads_runner=beads,
                                             legacy_selection_mode="multi")
    assert result["requestFingerprint"] == original
    assert service.recovery_context("pi-decision.1", resolver=proof, beads_runner=beads)["legacySelectionModeRequired"] is False
    service.rebind_pending_decision("pi-decision.1", resolver=proof, beads_runner=beads)
    canonical[changed[0]] = changed[1]
    with pytest.raises(ValueError, match="selection mode|custom response"):
        approvals.resolve_beads_approval_request(decision_bead="pi-decision.1", outcome="answered",
                                                selected_options=["A"], resolver=proof, beads_runner=beads)


def test_rebound_secret_is_not_stored_or_returned(recovery):
    service, _, _, beads, _ = recovery
    secret = "private-fixture-only-value"
    result = service.rebind_pending_decision("pi-decision.1", resolver=human_ui_resolver("child-session", secret), beads_runner=beads)
    serialized = json.dumps(result) + "".join(path.read_text() for path in service.binding_root().glob("*.json"))
    assert secret not in serialized


def test_corrupt_binding_never_falls_back_to_original_resolver(recovery):
    service, approvals, _, beads, _ = recovery
    service.rebind_pending_decision("pi-decision.1", resolver=human_ui_resolver("child-session"), beads_runner=beads)
    record = next(service.binding_root().glob("*.json"))
    record.write_text("{}")
    with pytest.raises(ValueError, match="binding"):
        approvals.resolve_beads_approval_request(decision_bead="pi-decision.1", outcome="approved",
                                                resolver=human_ui_resolver(), beads_runner=beads)
    assert not any(call[0] in {"update", "close"} for call in beads.calls)


@pytest.mark.parametrize("extra", [[], ["--legacy-selection-mode", "multi"]])
def test_rebind_cli_requires_existing_process_bound_ui_proof(agnt, extra):
    with pytest.raises(SystemExit) as stopped:
        agnt.main(["approvals", "rebind", "pi-decision.1", "--json", *extra])
    assert stopped.value.code != 0
