"""Standing worker permission must not imply controller Beads-write permission."""
from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path

import pytest

from test_orchestration import _active_orchestration_grant, valid_implement_metadata, valid_review_metadata
from test_work_continuation import runtime  # noqa: F401


def prepare_orchestrated(runtime, monkeypatch):
    metadata = valid_implement_metadata()
    metadata["pi"]["approvalRefs"] = []
    metadata["pi"]["standingAssignment"] = "queue"
    metadata["pi"]["allowedEffects"] = ["read_workspace", "write_artifacts", "edit_files"]
    bead = runtime["beads"]["pi-a"]
    bead.update(metadata=metadata, acceptance_criteria="Verified fixture implementation")
    monkeypatch.setattr(runtime["work"], "worktree_snapshot_for_bead", lambda *_: {
        "mode": "epic-worktree", "path": str(runtime["other"]), "branch": "other", "state": "existing",
    })
    return bead


@pytest.mark.parametrize("runtime", [{"effects": ["read", "artifact-write", "repo-write", "beads-write"]}], indirect=True)
def test_orchestrated_native_claim_cannot_borrow_live_owner(runtime, monkeypatch):
    bead = prepare_orchestrated(runtime, monkeypatch)
    runtime["store"].claim("pi-a", "session-foreign", str(runtime["repo"]))
    runtime["store"].bind_assignment("pi-a", "session-foreign", "queue")
    result = start(runtime, bead, claim=True)
    assert not any(args[0] == "update" for args in runtime["calls"])
    assert "authority" in result["dispatchError"].lower()


@pytest.mark.parametrize("runtime", [{"effects": ["read", "artifact-write", "repo-write", "beads-write"]}], indirect=True)
def test_scoped_orchestration_claims_and_closes_under_ownership_lock(runtime, monkeypatch):
    bead = prepare_orchestrated(runtime, monkeypatch)
    runtime["store"].claim("pi-a", "session-a", str(runtime["repo"]))
    runtime["store"].bind_assignment("pi-a", "session-a", "queue")
    original = runtime["work"].run_beads_json
    observed = []
    def native(args):
        if args[0] in {"update", "close"}:
            fd = os.open(runtime["store"].root / "lock", os.O_RDWR)
            try:
                with pytest.raises(BlockingIOError):
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            finally:
                os.close(fd)
            observed.append(args[0])
        return original(args)
    monkeypatch.setattr(runtime["work"], "run_beads_json", native)
    started = start(runtime, bead, claim=True)
    assert started["beadUpdate"]["code"] == 0
    finished = runtime["work"].finish_work(
        Path(started["bundle"]), status="succeeded", summary="fixture complete",
        evidence=["disposable fixture evidence"], artifacts=[], follow_ups=[], metrics_ref=None,
        close_bead=True,
    )
    assert finished["beadClose"]["code"] == 0
    assert observed == ["update", "close"]


@pytest.mark.parametrize("runtime", [{"effects": ["read", "artifact-write", "repo-write", "beads-write"]}], indirect=True)
def test_orchestrated_claim_cannot_choose_broader_assignment(runtime, monkeypatch):
    bead = prepare_orchestrated(runtime, monkeypatch)
    runtime["permission"].assign(
        "narrow", repository=str(runtime["repo"]), beads=["pi-a"],
        effects=["read", "artifact-write", "repo-write"], intent_ref="fixture:narrow-task",
    )
    runtime["store"].claim("pi-a", "session-a", str(runtime["repo"]))
    runtime["store"].bind_assignment("pi-a", "session-a", "narrow")
    result = start(runtime, bead, claim=True)
    assert "authority" in result["dispatchError"].lower()
    assert not any(args[0] == "update" for args in runtime["calls"])


def prepare_exact(agnt, runtime, monkeypatch):
    from agnt_lib import approvals
    bead = prepare_orchestrated(runtime, monkeypatch)
    bead["metadata"]["pi"].pop("standingAssignment")
    bead["metadata"]["pi"]["approvalRefs"] = ["pi-approval.1"]
    resolved = _active_orchestration_grant(agnt)
    resolved["targetBead"] = "pi-a"
    monkeypatch.setattr(approvals, "resolve_canonical_capability_grant", lambda _: resolved)
    runtime["beads"]["pi-approval.1"] = {
        "id": "pi-approval.1", "status": "closed", "metadata": {"pi": {"approval": {
            "status": "approved", "targetBead": "pi-a", "resolver": {"kind": "human-ui"},
        }}},
    }
    return bead, resolved


@pytest.mark.parametrize("operation", ["claim", "close"])
@pytest.mark.parametrize("runtime", [{"effects": ["read", "artifact-write", "repo-write"]}], indirect=True)
def test_exact_worker_grant_does_not_replace_controller_scope(agnt, runtime, monkeypatch, operation):
    bead, _ = prepare_exact(agnt, runtime, monkeypatch)
    started = start(runtime, bead, claim=operation == "claim")
    if operation == "close":
        result = runtime["work"].finish_work(
            Path(started["bundle"]), status="succeeded", summary="fixture complete",
            evidence=["disposable fixture evidence"], artifacts=[], follow_ups=[], metrics_ref=None,
            close_bead=True,
        )
        assert "authority" in result["closeError"].lower()
    else:
        assert "authority" in started["dispatchError"].lower()
    assert not any(args[0] in {"update", "close"} for args in runtime["calls"])


@pytest.mark.parametrize("runtime", [{"effects": ["read", "artifact-write", "repo-write", "beads-write"]}], indirect=True)
@pytest.mark.parametrize("change", ["revoke", "foreign-owner"])
def test_exact_claim_rechecks_gate_and_controller_after_preparation(agnt, runtime, monkeypatch, change):
    bead, resolved = prepare_exact(agnt, runtime, monkeypatch)
    original = runtime["work"].create_run_bundle
    def create(**kwargs):
        bundle = original(**kwargs)
        if change == "revoke":
            resolved["status"] = "revoked"
        else:
            runtime["store"].claim("pi-a", "session-foreign", str(runtime["repo"]))
            runtime["store"].bind_assignment("pi-a", "session-foreign", "queue")
        return bundle
    monkeypatch.setattr(runtime["work"], "create_run_bundle", create)
    result = start(runtime, bead, claim=True)
    assert result.get("bundle")
    assert "authority" in result["beadUpdateError"].lower()
    assert not any(args[0] == "update" for args in runtime["calls"])


@pytest.mark.parametrize("runtime", [{"effects": ["read", "artifact-write", "repo-write", "beads-write"]}], indirect=True)
@pytest.mark.parametrize("revocation", ["none", "canonical", "local"])
def test_exact_close_uses_separate_scope_and_fresh_gate(agnt, runtime, monkeypatch, revocation):
    bead, resolved = prepare_exact(agnt, runtime, monkeypatch)
    original_scope = runtime["permission"].assignment_for(str(runtime["repo"]), "pi-a")
    runtime["store"].claim("pi-a", "session-a", str(runtime["repo"]))
    runtime["store"].bind_assignment("pi-a", "session-a", "queue")
    started = start(runtime, bead, claim=True)
    assert started["beadUpdate"]["code"] == 0
    if revocation == "canonical":
        resolved["status"] = "revoked"
    elif revocation == "local":
        monkeypatch.setattr(runtime["quality"], "locally_revoked_capability_grant", lambda *_, **__: True)
    result = runtime["work"].finish_work(
        Path(started["bundle"]), status="succeeded", summary="fixture complete",
        evidence=["disposable fixture evidence"], artifacts=[], follow_ups=[], metrics_ref=None,
        close_bead=True,
    )
    if revocation == "none":
        assert result["beadClose"]["code"] == 0
    else:
        assert "authority" in result["closeError"].lower()
        assert not any(args[0] == "close" for args in runtime["calls"])
    invocation = json.loads((Path(started["bundle"]) / "invocation.yaml").read_text())
    assert invocation["provenance"]["effectiveEnvelope"]["grant"]["effects"] == ["edit_files"]
    assert runtime["permission"].assignment_for(str(runtime["repo"]), "pi-a") == original_scope


@pytest.mark.parametrize("runtime", [{"effects": ["read", "artifact-write", "repo-write", "beads-write"]}], indirect=True)
def test_exact_gate_read_cannot_hide_queued_controller_revocation(agnt, runtime, monkeypatch):
    from agnt_lib import approvals
    bead, resolved = prepare_exact(agnt, runtime, monkeypatch)
    prepared = []
    original = runtime["work"].create_run_bundle
    def create(**kwargs):
        bundle = original(**kwargs)
        prepared.append(True)
        return bundle
    def resolve(_):
        if prepared:
            runtime["permission"].revoke("queued while explicit gate was read")
        return resolved
    monkeypatch.setattr(runtime["work"], "create_run_bundle", create)
    monkeypatch.setattr(approvals, "resolve_canonical_capability_grant", resolve)
    result = start(runtime, bead, claim=True)
    assert not any(args[0] == "update" for args in runtime["calls"])
    assert "authority" in result["beadUpdateError"].lower()


@pytest.mark.parametrize("runtime", [{"effects": ["read", "artifact-write", "repo-write", "beads-write"]}], indirect=True)
@pytest.mark.parametrize("envelope", [None, {}, {"decisionBead": "pi-approval.1", "grant": None}])
def test_missing_exact_snapshot_does_not_fall_back_to_controller_scope(agnt, runtime, monkeypatch, envelope):
    bead, _ = prepare_exact(agnt, runtime, monkeypatch)
    started = start(runtime, bead, claim=False)
    path = Path(started["bundle"]) / "invocation.yaml"
    invocation = json.loads(path.read_text())
    invocation["provenance"]["effectiveEnvelope"] = envelope
    path.write_text(json.dumps(invocation))
    result = runtime["work"].finish_work(
        Path(started["bundle"]), status="succeeded", summary="fixture complete",
        evidence=["disposable fixture evidence"], artifacts=[], follow_ups=[], metrics_ref=None,
        close_bead=True,
    )
    assert not any(args[0] == "close" for args in runtime["calls"])
    assert "authority" in result["closeError"].lower()


@pytest.mark.parametrize("runtime", [{"effects": ["read", "artifact-write", "repo-write", "beads-write"]}], indirect=True)
@pytest.mark.parametrize("metadata", [None, {"pi": []}, {"pi": {"approval": None}}])
def test_malformed_referenced_decision_denies_with_bounded_error(runtime, monkeypatch, metadata):
    bead = prepare_orchestrated(runtime, monkeypatch)
    started = start(runtime, bead, claim=False)
    bead["metadata"]["pi"]["decisionRefs"] = ["pi-b"]
    runtime["beads"]["pi-b"]["metadata"] = metadata
    result = runtime["work"].finish_work(
        Path(started["bundle"]), status="succeeded", summary="fixture complete",
        evidence=["disposable fixture evidence"], artifacts=[], follow_ups=[], metrics_ref=None,
        close_bead=True,
    )
    assert "authority" in result["closeError"].lower()
    assert not any(args[0] == "close" for args in runtime["calls"])


@pytest.mark.parametrize("runtime", [{"effects": ["read", "artifact-write", "repo-write", "beads-write"]}], indirect=True)
@pytest.mark.parametrize("stage", ["admission", "claim", "close"])
def test_exact_grant_must_target_actual_work_item(agnt, runtime, monkeypatch, stage):
    bead, resolved = prepare_exact(agnt, runtime, monkeypatch)
    if stage == "admission":
        resolved["targetBead"] = "pi-b"
        result = start(runtime, bead, claim=False)
        assert "dispatchError" in result
        assert not (runtime["root"] / "runs").exists()
    elif stage == "claim":
        original = runtime["work"].create_run_bundle
        def create(**kwargs):
            bundle = original(**kwargs)
            resolved["targetBead"] = "pi-b"
            return bundle
        monkeypatch.setattr(runtime["work"], "create_run_bundle", create)
        result = start(runtime, bead, claim=True)
        assert not any(args[0] == "update" for args in runtime["calls"])
        assert "beadUpdateError" in result
    else:
        started = start(runtime, bead, claim=False)
        resolved["targetBead"] = "pi-b"
        result = runtime["work"].finish_work(
            Path(started["bundle"]), status="succeeded", summary="fixture complete",
            evidence=["disposable fixture evidence"], artifacts=[], follow_ups=[], metrics_ref=None,
            close_bead=True,
        )
        assert not any(args[0] == "close" for args in runtime["calls"])
        assert "closeError" in result


def test_exact_worker_revalidation_binds_target_bead(agnt):
    from agnt_lib import runs
    resolved = _active_orchestration_grant(agnt)
    resolved["targetBead"] = "pi-b"
    invocation = {"action": "implement", "bead": "pi-a", "thinkingLevel": "high",
                  "provenance": {"approvalRefs": [resolved["decisionBead"]], "effectiveEnvelope": resolved}}
    error = runs._revalidate_invocation_authority(
        invocation, selected_model=resolved["grant"]["model"], worker_tools=["read"],
        grant_resolver=lambda _: resolved, claim_directory=None,
    )
    assert error is not None


@pytest.mark.parametrize(("stored", "canonical", "allowed"), [
    ("legacy", "pi-a", True), ("legacy", "pi-b", False), ("legacy", None, False),
    ("pi-a", "pi-a", True), ("pi-b", "pi-a", False), (None, "pi-a", False),
])
def test_legacy_exact_snapshot_requires_fresh_matching_target(agnt, stored, canonical, allowed):
    from agnt_lib import runs
    resolved = _active_orchestration_grant(agnt)
    resolved["targetBead"] = canonical
    snapshot = dict(resolved)
    if stored == "legacy":
        snapshot.pop("targetBead")
    else:
        snapshot["targetBead"] = stored
    invocation = {"action": "implement", "bead": "pi-a", "thinkingLevel": "high",
                  "provenance": {"approvalRefs": [resolved["decisionBead"]], "effectiveEnvelope": snapshot}}
    before = json.dumps(invocation, sort_keys=True)
    error = runs._revalidate_invocation_authority(
        invocation, selected_model=resolved["grant"]["model"], worker_tools=["read"],
        grant_resolver=lambda _: resolved, claim_directory=None,
    )
    assert (error is None) is allowed
    assert json.dumps(invocation, sort_keys=True) == before


@pytest.mark.parametrize("runtime", [{"effects": ["read", "artifact-write", "repo-write", "beads-write"]}], indirect=True)
def test_legacy_exact_close_checks_target_without_rewriting_snapshot(agnt, runtime, monkeypatch):
    bead, _ = prepare_exact(agnt, runtime, monkeypatch)
    started = start(runtime, bead, claim=False)
    path = Path(started["bundle"]) / "invocation.yaml"
    invocation = json.loads(path.read_text())
    assert invocation["provenance"]["effectiveEnvelope"].pop("targetBead") == "pi-a"
    path.write_text(json.dumps(invocation))
    before = path.read_bytes()
    result = runtime["work"].finish_work(
        Path(started["bundle"]), status="succeeded", summary="fixture complete",
        evidence=["disposable fixture evidence"], artifacts=[], follow_ups=[], metrics_ref=None,
        close_bead=True,
    )
    assert result["beadClose"]["code"] == 0
    assert path.read_bytes() == before


def start(runtime, bead, *, claim):
    return runtime["work"].start_work(
        bead, action_id=None, target=[], claim=claim,
        runs_dir=runtime["root"] / "runs", id_value="authority-boundary",
    )


@pytest.mark.parametrize("runtime", [{"effects": ["read", "artifact-write", "repo-write"]}], indirect=True)
def test_orchestrated_claim_needs_separate_native_effect(runtime, monkeypatch):
    bead = prepare_orchestrated(runtime, monkeypatch)
    result = start(runtime, bead, claim=True)
    assert not any(args[0] == "update" for args in runtime["calls"])
    assert "authority" in result["dispatchError"].lower()
    assert not (runtime["root"] / "runs").exists()


@pytest.mark.parametrize("runtime", [{"effects": ["read", "artifact-write", "repo-write", "beads-write"]}], indirect=True)
def test_orchestrated_claim_rechecks_after_bundle_preparation(runtime, monkeypatch):
    bead = prepare_orchestrated(runtime, monkeypatch)
    original = runtime["work"].create_run_bundle
    def create(**kwargs):
        bundle = original(**kwargs)
        runtime["permission"].revoke("stop queued native claim")
        return bundle
    monkeypatch.setattr(runtime["work"], "create_run_bundle", create)
    result = start(runtime, bead, claim=True)
    assert not any(args[0] == "update" for args in runtime["calls"])
    assert result.get("bundle"), "preserve prepared bundle for inspection"
    assert "authority" in result["beadUpdateError"].lower()


@pytest.mark.parametrize("operation", ["claim", "close"])
@pytest.mark.parametrize("runtime", [{"effects": ["read", "artifact-write", "repo-write"]}], indirect=True)
def test_readonly_action_cannot_bypass_native_scope(runtime, monkeypatch, operation):
    bead = prepare_orchestrated(runtime, monkeypatch)
    bead["metadata"] = valid_review_metadata()
    started = start(runtime, bead, claim=operation == "claim")
    if operation == "close":
        runtime["work"].finish_work(
            Path(started["bundle"]), status="succeeded", summary="fixture complete",
            evidence=["disposable fixture evidence"], artifacts=[], follow_ups=[], metrics_ref=None,
            close_bead=True,
        )
    assert not any(args[0] in {"update", "close"} for args in runtime["calls"])


@pytest.mark.parametrize("metadata", [{"pi": []}, {"pi": "malformed"}, ["malformed"]])
@pytest.mark.parametrize("runtime", [{"effects": ["read", "artifact-write", "repo-write", "beads-write"]}], indirect=True)
def test_orchestrated_close_denies_malformed_live_constraints(runtime, monkeypatch, metadata):
    bead = prepare_orchestrated(runtime, monkeypatch)
    started = start(runtime, bead, claim=False)
    runtime["beads"]["pi-a"]["metadata"] = metadata
    result = runtime["work"].finish_work(
        Path(started["bundle"]), status="succeeded", summary="fixture complete",
        evidence=["disposable fixture evidence"], artifacts=[], follow_ups=[], metrics_ref=None,
        close_bead=True,
    )
    assert "authority" in result["closeError"].lower()
    assert not any(args[0] == "close" for args in runtime["calls"])


@pytest.mark.parametrize("runtime", [
    {"effects": ["read", "artifact-write", "repo-write"]},
    {"effects": ["read", "artifact-write", "repo-write", "beads-write"], "revoke": True},
], indirect=True)
def test_orchestrated_close_rechecks_invocation_scope(runtime, monkeypatch, request):
    bead = prepare_orchestrated(runtime, monkeypatch)
    started = start(runtime, bead, claim=False)
    assert started.get("bundle")
    if request.node.callspec.params["runtime"].get("revoke"):
        runtime["permission"].revoke("stop closure")
    result = runtime["work"].finish_work(
        Path(started["bundle"]), status="succeeded", summary="fixture complete",
        evidence=["disposable fixture evidence"], artifacts=[], follow_ups=[], metrics_ref=None,
        close_bead=True,
    )
    assert not any(args[0] == "close" for args in runtime["calls"])
    assert "authority" in result["closeError"].lower()
