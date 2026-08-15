from __future__ import annotations

import hashlib
import json
from uuid import UUID

import pytest


def _work_target_fingerprint(*, work_item, worktree, input_refs):
    return "sha256:" + hashlib.sha256(
        json.dumps(
            {
                "schemaVersion": 1,
                "workItem": work_item,
                "worktree": worktree,
                "inputRefs": input_refs,
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def _claim_context(
    *,
    action="edit",
    effects=None,
    target_fingerprint=None,
    decision_bead="pi-claim.1",
    grant_fingerprint=None,
):
    grant_fingerprint = grant_fingerprint or "sha256:" + "a" * 64
    allowance_id = "allowance-" + hashlib.sha256(
        f"{decision_bead}:{grant_fingerprint}".encode("utf-8")
    ).hexdigest()
    policy_fingerprint = "sha256:" + "b" * 64
    effects = list(effects or ["workspace.write"])
    target_fingerprint = target_fingerprint or "sha256:" + "c" * 64
    claim_id = "claim-" + hashlib.sha256(
        json.dumps(
            {
                "receiptId": "quality-receipt-1",
                "allowanceId": allowance_id,
                "policyFingerprint": policy_fingerprint,
                "action": action,
                "effects": effects,
                "targetFingerprint": target_fingerprint,
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    return {
        "schemaVersion": 1,
        "claimId": claim_id,
        "receiptId": "quality-receipt-1",
        "decisionBead": decision_bead,
        "grantFingerprint": grant_fingerprint,
        "allowanceId": allowance_id,
        "policyFingerprint": policy_fingerprint,
        "action": action,
        "effects": effects,
        "targetFingerprint": target_fingerprint,
    }


def _evidence_claim_context():
    context = _claim_context()
    context["authorizationEvidence"] = ["artifact:grant-proof"]
    context["executionEvidence"] = ["artifact:execution-proof"]
    context["requiredProof"] = ["tests"]
    identity = {
        "receiptId": context["receiptId"],
        "allowanceId": context["allowanceId"],
        "policyFingerprint": context["policyFingerprint"],
        "action": context["action"],
        "effects": context["effects"],
        "targetFingerprint": context["targetFingerprint"],
        "authorizationEvidence": context["authorizationEvidence"],
        "executionEvidence": context["executionEvidence"],
    }
    context["claimId"] = "claim-" + hashlib.sha256(
        json.dumps(identity, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).hexdigest()
    return context


def _claim_row(claim_context):
    row = {
        "schemaVersion": 1,
        "claimId": claim_context["claimId"],
        "receiptId": claim_context["receiptId"],
        "state": "claimed",
        "decisionBead": claim_context["decisionBead"],
        "grantFingerprint": claim_context["grantFingerprint"],
        "allowanceId": claim_context["allowanceId"],
        "policyFingerprint": claim_context["policyFingerprint"],
        "action": claim_context["action"],
        "effectSet": claim_context["effects"],
        "actions": 1,
        "effects": len(claim_context["effects"]),
        "errorBudget": 1,
        "targetFingerprint": claim_context["targetFingerprint"],
        "resultStatus": None,
        "evidenceRefs": [],
        "reason": None,
        "at": "2026-08-15T00:00:00Z",
    }
    if "authorizationEvidence" in claim_context:
        row.update({
            "authorizationEvidence": claim_context["authorizationEvidence"],
            "executionEvidence": claim_context["executionEvidence"],
            "requiredProof": claim_context["requiredProof"],
        })
    return row


def _claim_bound_bundle(
    agnt,
    tmp_path,
    *,
    invocation_action="implement",
    invocation_effects=None,
    invocation_input_refs=None,
    claim_action="edit",
):
    worktree_path = tmp_path / "worktree"
    worktree_path.mkdir()
    worktree = {
        "schemaVersion": 1,
        "path": str(worktree_path),
        "dispatchable": True,
        "status": "ready",
    }
    work_item = "pi-ready.claim-bound"
    claim_effects = ["read_workspace", "write_artifacts", "workspace.write"]
    canonical_input_refs = ["src/feature.py"]
    grant = {
        "schemaVersion": 1,
        "action": claim_action,
        "effects": claim_effects,
        "model": "openai/gpt-5",
        "thinking": "high",
        "toolset": ["read", "edit", "bash"],
        "contextPolicy": "task-scoped",
        "proof": {"required": ["tests"], "evidenceRefs": ["artifact:grant-proof"]},
        "rollout": {"maxActions": 1, "maxEffects": len(claim_effects)},
        "expiry": "2099-01-01T00:00:00Z",
        "revocation": {"status": "active", "reason": None, "at": None},
    }
    grant_fingerprint = agnt.capability_grant_fingerprint(grant)
    authority = {
        "schemaVersion": 1,
        "decisionBead": "pi-claim.1",
        "status": "active",
        "grant": grant,
        "grantFingerprint": grant_fingerprint,
        "resolver": {"kind": "human-ui"},
        "allowedEffects": claim_effects,
    }
    claim_context = _claim_context(
        action=claim_action,
        effects=claim_effects,
        target_fingerprint=_work_target_fingerprint(
            work_item=work_item,
            worktree=worktree,
            input_refs=canonical_input_refs,
        ),
        grant_fingerprint=grant_fingerprint,
    )
    claim_directory = tmp_path / "quality"
    claim_directory.mkdir()
    claims_path = claim_directory / "claims.jsonl"
    claims_path.write_text(json.dumps(_claim_row(claim_context)) + "\n", encoding="utf-8")
    claims_path.chmod(0o600)
    bundle = agnt.create_run_bundle(
        action=invocation_action,
        routing_task="implementation",
        input_refs=(
            canonical_input_refs
            if invocation_input_refs is None
            else invocation_input_refs
        ),
        bead=work_item,
        authority=authority,
        claim_context=claim_context,
        worktree=worktree,
        allowed_effects=(
            ["read_workspace", "write_artifacts", "edit_files"]
            if invocation_effects is None
            else invocation_effects
        ),
        output_contract="implementation-report",
        runs_dir=tmp_path / "runs",
        id_value="claim-bound",
    )
    return bundle, claim_directory, authority


def test_dispatch_plan_uses_metadata_action_before_title_heuristics(agnt):
    bead = {
        "id": "pi-ready.1",
        "title": "Execute critical harness fix",
        "issue_type": "bug",
        "status": "open",
        "acceptance_criteria": "tests pass",
        "metadata": json.dumps({
            "pi": {
                "action": "implement",
                "routingTask": "implementation",
                "approvalRefs": ["pi-approval.1"],
                "allowedEffects": ["read_workspace", "write_artifacts", "edit_files", "update_beads"],
                "epicId": "pi-epic",
                "worktreePolicy": "epic-worktree",
                "writeSet": ["src/shared.py"],
                "closeout": {
                    "requiresEvidence": True,
                    "requiresResolvedApprovals": True,
                    "requiresFollowUpsReconciled": True,
                },
            }
        }),
    }

    plan = agnt.dispatch_plan(bead, None, [])

    assert plan["action"] == "implement"
    assert plan["routingTask"] == "implementation"


def test_invoke_one_reports_timeout(agnt, monkeypatch):
    def fake_run(cmd, **kwargs):
        raise agnt.invoke_one.__globals__["subprocess"].TimeoutExpired(cmd, timeout=12, output="partial", stderr="waiting")

    monkeypatch.setattr(agnt.invoke_one.__globals__["subprocess"], "run", fake_run)

    code, out, err, record = agnt.invoke_one(
        "openrouter/minimax/minimax-m3",
        "prompt",
        metrics=False,
        timeout_seconds=12,
    )

    assert code == 124
    assert out == "partial"
    assert "timed out after 12s" in err
    assert "waiting" in err
    assert record is None


def test_invoke_one_parses_json_stream_on_timeout(agnt, monkeypatch):
    stdout = json.dumps(
        {
            "type": "message_end",
            "message": {
                "role": "assistant",
                "content": [{"type": "toolCall", "name": "read", "arguments": {"path": "README.md"}}],
                "usage": {"input": 100, "output": 20, "totalTokens": 120},
            },
        }
    )

    def fake_run(cmd, **kwargs):
        raise agnt.invoke_one.__globals__["subprocess"].TimeoutExpired(cmd, timeout=12, output=stdout)

    monkeypatch.setattr(agnt.invoke_one.__globals__["subprocess"], "run", fake_run)

    code, out, err, record = agnt.invoke_one(
        "openrouter/moonshotai/kimi-k2.7-code",
        "prompt",
        metrics=True,
        task="review",
        timeout_seconds=12,
    )

    assert code == 124
    assert out == ""
    assert "timed out after 12s" in err
    assert record["responseChars"] == 0
    assert record["status"] == "failed"
    assert record["executionOutcome"] == "unavailable"
    assert record["failureClass"] == "timeout"
    assert record["usage"]["providerRequests"] == 1


def test_invoke_one_fails_terminal_provider_error(agnt, monkeypatch):
    class Proc:
        returncode = 0
        stdout = json.dumps(
            {
                "type": "message_end",
                "message": {
                    "role": "assistant",
                    "content": [],
                    "stopReason": "error",
                    "errorMessage": "The operation was aborted",
                    "usage": {"input": 0, "output": 0, "totalTokens": 0},
                },
            }
        )
        stderr = ""

    monkeypatch.setattr(agnt.invoke_one.__globals__["subprocess"], "run", lambda cmd, **kwargs: Proc())

    code, out, err, record = agnt.invoke_one(
        "openrouter/moonshotai/kimi-k2.7-code",
        "prompt",
        metrics=True,
        task="review",
    )

    assert code == 1
    assert out == ""
    assert "The operation was aborted" in err
    assert record["exitCode"] == 1
    assert record["executionOutcome"] == "failed"
    assert record["failureClass"] == "provider"


def test_invoke_one_one_shot_disables_agent_context_and_records_request_count(agnt, monkeypatch):
    calls = []

    class Proc:
        returncode = 0
        stdout = json.dumps(
            {
                "type": "message_end",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "reviewed"}],
                    "usage": {
                        "input": 100,
                        "output": 20,
                        "cacheRead": 0,
                        "cacheWrite": 0,
                        "totalTokens": 120,
                    },
                },
            }
        )
        stderr = ""

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return Proc()

    monkeypatch.setattr(agnt.invoke_one.__globals__["subprocess"], "run", fake_run)

    code, out, err, record = agnt.invoke_one(
        "openrouter/moonshotai/kimi-k2.7-code",
        "complete review packet",
        metrics=True,
        task="review",
        thinking_level="high",
        one_shot=True,
    )

    assert code == 0
    assert out == "reviewed"
    assert err == ""
    assert record["invocationMode"] == "one-shot"
    assert record["providerRequests"] == 1
    cmd, _kwargs = calls[0]
    for flag in (
        "--no-tools",
        "--no-skills",
        "--no-context-files",
        "--no-prompt-templates",
        "--no-session",
    ):
        assert flag in cmd
    assert cmd[cmd.index("--system-prompt") + 1]
    assert cmd[cmd.index("--thinking") + 1] == "high"
    assert "complete review packet" not in cmd
    assert _kwargs["input"] == "complete review packet"


def test_invoke_one_can_record_named_session(agnt, monkeypatch, tmp_path):
    calls = []

    class Proc:
        returncode = 0
        stdout = "ok"
        stderr = ""

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return Proc()

    monkeypatch.setattr(agnt.invoke_one.__globals__["subprocess"], "run", fake_run)

    code, out, err, record = agnt.invoke_one(
        "openrouter/minimax/minimax-m3",
        "prompt",
        metrics=False,
        record_session=True,
        session_id="run-abc",
        session_name="run:abc bead:pi-1 action:review",
        cwd=tmp_path,
        pi_args=["--no-extensions", "--tools", "read"],
    )

    assert code == 0
    assert out == "ok"
    assert record is None
    cmd, kwargs = calls[0]
    assert kwargs["cwd"] == str(tmp_path)
    assert "--no-session" not in cmd
    assert "--no-extensions" in cmd
    assert "--tools" in cmd and cmd[cmd.index("--tools") + 1] == "read"
    assert "--session-id" in cmd and cmd[cmd.index("--session-id") + 1] == "run-abc"
    assert "--name" in cmd and cmd[cmd.index("--name") + 1] == "run:abc bead:pi-1 action:review"


def test_invoke_run_bundle_implementation_uses_worktree_write_tools(agnt, monkeypatch, tmp_path):
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    grant = {
        "action": "implement",
        "effects": ["edit_files"],
        "model": "openai/gpt-5",
        "thinking": "high",
        "toolset": ["read", "edit", "bash"],
        "contextPolicy": "task-scoped",
        "proof": {"required": ["tests"], "evidenceRefs": ["artifact:grant-proof"]},
        "rollout": {"maxActions": 1, "maxEffects": 1},
        "expiry": "2099-01-01T00:00:00Z",
        "revocation": {"status": "active", "reason": None, "at": None},
    }
    authority = {
        "decisionBead": "pi-approval.1",
        "status": "active",
        "grant": grant,
        "grantFingerprint": agnt.capability_grant_fingerprint(grant),
        "resolver": {"kind": "human-ui"},
        "allowedEffects": ["edit_files"],
    }
    bundle = agnt.create_run_bundle(
        action="implement",
        routing_task="implementation",
        bead="pi-ready.1",
        selected_model="openrouter/minimax/minimax-m3",
        thinking_level="high",
        authority=authority,
        worktree={"schemaVersion": 1, "path": str(worktree), "dispatchable": True, "status": "ready"},
        allowed_effects=["read_workspace", "write_artifacts", "edit_files", "write_workspace", "update_beads"],
        output_contract="implementation-report",
        runs_dir=tmp_path / "runs",
        id_value="run-implement",
    )
    calls = []

    def fake_invoke_one(target, prompt, **kwargs):
        calls.append((target, prompt, kwargs))
        return 0, "ok", "", None

    monkeypatch.setitem(agnt.invoke_run_bundle.__globals__, "invoke_one", fake_invoke_one)

    result = agnt.invoke_run_bundle(
        bundle,
        metrics=False,
        record_session=True,
        session_id="run-implement",
        grant_resolver=lambda _decision: authority,
    )

    assert result["exitCode"] == 0
    kwargs = calls[0][2]
    assert kwargs["cwd"] == str(worktree)
    assert kwargs["thinking_level"] == "high"
    assert "--no-extensions" in kwargs["pi_args"]
    assert "--tools" in kwargs["pi_args"]
    tools = kwargs["pi_args"][kwargs["pi_args"].index("--tools") + 1].split(",")
    assert {"read", "bash", "edit", "write", "grep", "find", "ls"}.issubset(set(tools))


def test_create_run_bundle_preserves_explicit_claim_provenance(agnt, tmp_path):
    claim_context = _claim_context()
    bundle = agnt.create_run_bundle(
        action="review",
        routing_task="review",
        bead="pi-ready.claim",
        claim_context=claim_context,
        runs_dir=tmp_path / "runs",
        id_value="claim-provenance",
    )

    invocation = agnt.load_yaml_json(bundle / "invocation.yaml")
    assert invocation["provenance"]["claimContext"] == claim_context
    assert agnt.validate_run_bundle(bundle) == []


def test_create_run_bundle_binds_split_evidence_contract_to_result(agnt, tmp_path):
    claim_context = _evidence_claim_context()
    bundle = agnt.create_run_bundle(
        action="review",
        routing_task="review",
        bead="pi-ready.claim-evidence",
        claim_context=claim_context,
        runs_dir=tmp_path / "runs",
        id_value="claim-evidence",
    )

    invocation = agnt.load_yaml_json(bundle / "invocation.yaml")
    result = agnt.load_yaml_json(bundle / "result.yaml")
    assert invocation["provenance"]["claimContext"] == claim_context
    assert result["claimContext"] == claim_context
    assert agnt.validate_run_bundle(bundle) == []

    missing = dict(result)
    missing.pop("claimContext")
    agnt.write_yaml_json(bundle / "result.yaml", missing)
    assert any("result claimContext" in failure for failure in agnt.validate_run_bundle(bundle))

    result["claimContext"] = {**claim_context, "targetFingerprint": "sha256:" + "f" * 64}
    agnt.write_yaml_json(bundle / "result.yaml", result)
    assert any("result claimContext" in failure for failure in agnt.validate_run_bundle(bundle))


def test_invoke_run_bundle_rejects_recomputed_claim_provenance(agnt, monkeypatch, tmp_path):
    claim_context = _claim_context()
    claim_directory = tmp_path / "quality"
    claim_directory.mkdir()
    claims_path = claim_directory / "claims.jsonl"
    claims_path.write_text(json.dumps(_claim_row(claim_context)) + "\n", encoding="utf-8")
    claims_path.chmod(0o600)
    bundle = agnt.create_run_bundle(
        action="review",
        routing_task="review",
        bead="pi-ready.claim",
        claim_context=claim_context,
        runs_dir=tmp_path / "runs",
        id_value="claim-forged",
    )
    invocation = agnt.load_yaml_json(bundle / "invocation.yaml")
    forged = dict(claim_context)
    forged["targetFingerprint"] = "sha256:" + "f" * 64
    forged["claimId"] = "claim-" + hashlib.sha256(
        json.dumps(
            {
                "receiptId": forged["receiptId"],
                "allowanceId": forged["allowanceId"],
                "policyFingerprint": forged["policyFingerprint"],
                "action": forged["action"],
                "effects": forged["effects"],
                "targetFingerprint": forged["targetFingerprint"],
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    invocation["provenance"]["claimContext"] = forged
    agnt.write_yaml_json(bundle / "invocation.yaml", invocation)
    invoked = []
    monkeypatch.setitem(
        agnt.invoke_run_bundle.__globals__,
        "invoke_one",
        lambda *args, **kwargs: invoked.append(args) or (0, "OK", "", None),
    )

    result = agnt.invoke_run_bundle(bundle, metrics=False, claim_directory=claim_directory)

    assert result["exitCode"] == 1
    assert "claim context" in result["authorityError"]
    assert invoked == []


def test_invoke_run_bundle_rejects_forged_claim_provenance(agnt, monkeypatch, tmp_path):
    bundle = agnt.create_run_bundle(
        action="review",
        routing_task="review",
        bead="pi-ready.claim",
        claim_context=_claim_context(),
        runs_dir=tmp_path / "runs",
        id_value="claim-forged",
    )
    invocation = agnt.load_yaml_json(bundle / "invocation.yaml")
    invocation["provenance"]["claimContext"]["targetFingerprint"] = "sha256:" + "f" * 64
    agnt.write_yaml_json(bundle / "invocation.yaml", invocation)
    invoked = []
    monkeypatch.setitem(
        agnt.invoke_run_bundle.__globals__,
        "invoke_one",
        lambda *args, **kwargs: invoked.append(args) or (0, "OK", "", None),
    )

    result = agnt.invoke_run_bundle(bundle, metrics=False)

    assert result["exitCode"] == 1
    assert "claim context" in result["authorityError"]
    assert invoked == []


def test_invoke_run_bundle_accepts_exact_claim_invocation_binding(agnt, monkeypatch, tmp_path):
    bundle, claim_directory, authority = _claim_bound_bundle(agnt, tmp_path)
    invoked = []
    monkeypatch.setitem(
        agnt.invoke_run_bundle.__globals__,
        "invoke_one",
        lambda *args, **kwargs: invoked.append(args) or (0, "OK: bound", "", None),
    )

    result = agnt.invoke_run_bundle(
        bundle,
        metrics=False,
        claim_directory=claim_directory,
        grant_resolver=lambda _decision: authority,
    )

    assert result["exitCode"] == 0
    assert len(invoked) == 1


@pytest.mark.parametrize(
    ("bundle_overrides", "expected_error"),
    [
        (
            {"invocation_action": "review"},
            "explicit claim action does not match invocation action",
        ),
        (
            {"invocation_effects": ["read_workspace", "edit_files"]},
            "explicit claim effects do not match invocation allowed effects",
        ),
        (
            {"invocation_input_refs": ["src/other.py"]},
            "explicit claim target does not match invocation target",
        ),
        (
            {"invocation_effects": [{"malformed": "effect"}]},
            "explicit claim effects do not match invocation allowed effects",
        ),
        (
            {"claim_action": "unsupported", "invocation_action": None},
            "explicit claim action does not match invocation action",
        ),
    ],
)
def test_invoke_run_bundle_rejects_claim_invocation_mismatch_before_worker(
    agnt, monkeypatch, tmp_path, bundle_overrides, expected_error
):
    bundle, claim_directory, authority = _claim_bound_bundle(
        agnt,
        tmp_path,
        **bundle_overrides,
    )
    invoked = []
    monkeypatch.setitem(
        agnt.invoke_run_bundle.__globals__,
        "invoke_one",
        lambda *args, **kwargs: invoked.append(args) or (0, "OK", "", None),
    )

    result = agnt.invoke_run_bundle(
        bundle,
        metrics=False,
        claim_directory=claim_directory,
        grant_resolver=lambda _decision: authority,
    )

    assert result["exitCode"] == 1
    assert result["authorityError"] == expected_error
    assert invoked == []


def test_invoke_run_bundle_revalidates_canonical_grant_before_dispatch(agnt, monkeypatch, tmp_path):
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    grant = {
        "action": "implement",
        "effects": ["edit_files"],
        "model": "openai/gpt-5",
        "thinking": "high",
        "toolset": ["read", "edit", "bash"],
        "contextPolicy": "task-scoped",
        "proof": {"required": ["tests"], "evidenceRefs": ["artifact:grant-proof"]},
        "rollout": {"maxActions": 1, "maxEffects": 1},
        "expiry": "2099-01-01T00:00:00Z",
        "revocation": {"status": "active", "reason": None, "at": None},
    }
    authority = {
        "schemaVersion": 1,
        "decisionBead": "pi-approval.1",
        "status": "active",
        "grant": grant,
        "grantFingerprint": agnt.capability_grant_fingerprint(grant),
        "resolver": {"kind": "human-ui"},
        "allowedEffects": ["edit_files"],
    }
    bundle = agnt.create_run_bundle(
        action="implement",
        routing_task="implementation",
        bead="pi-ready.1",
        authority=authority,
        worktree={"schemaVersion": 1, "path": str(worktree), "dispatchable": True, "status": "ready"},
        allowed_effects=["read_workspace", "write_artifacts", "edit_files"],
        output_contract="implementation-report",
        runs_dir=tmp_path / "runs",
        id_value="run-revocation",
    )
    invoked = []
    monkeypatch.setitem(agnt.invoke_run_bundle.__globals__, "invoke_one", lambda *args, **kwargs: invoked.append(args) or (0, "OK", "", None))

    result = agnt.invoke_run_bundle(
        bundle,
        metrics=False,
        grant_resolver=lambda _decision: {"status": "revoked", "allowedEffects": []},
    )

    assert result["exitCode"] == 1
    assert "canonical capability grant" in result["authorityError"]
    assert invoked == []


def test_invoke_run_bundle_review_stays_read_only(agnt, monkeypatch, tmp_path):
    bundle = agnt.create_run_bundle(
        action="review",
        routing_task="review",
        bead="pi-ready.1",
        selected_model="openrouter/minimax/minimax-m3",
        allowed_effects=["read_workspace", "write_artifacts"],
        output_contract="findings-with-evidence",
        runs_dir=tmp_path / "runs",
        id_value="run-review",
    )
    calls = []

    def fake_invoke_one(target, prompt, **kwargs):
        calls.append((target, prompt, kwargs))
        return 0, "ok", "", None

    monkeypatch.setitem(agnt.invoke_run_bundle.__globals__, "invoke_one", fake_invoke_one)

    result = agnt.invoke_run_bundle(bundle, metrics=False)

    assert result["exitCode"] == 0
    kwargs = calls[0][2]
    assert kwargs["cwd"] is None
    assert kwargs["timeout_seconds"] == 300
    assert "--no-extensions" in kwargs["pi_args"]
    tools = kwargs["pi_args"][kwargs["pi_args"].index("--tools") + 1].split(",")
    assert set(tools) == {"read", "grep", "find", "ls"}


def test_invoke_run_bundle_verify_with_command_evidence_gets_safe_bash(agnt, monkeypatch, tmp_path):
    bundle = agnt.create_run_bundle(
        action="verify",
        routing_task="review",
        bead="pi-ready.1",
        selected_model="openrouter/minimax/minimax-m3",
        allowed_effects=["read_workspace", "write_artifacts"],
        acceptance_criteria=["Run `/usr/bin/python -m pytest e2e-test/test_edabit_challenges.py -q` and report result."],
        output_contract="verification-review",
        runs_dir=tmp_path / "runs",
        id_value="run-verify",
    )
    calls = []

    def fake_invoke_one(target, prompt, **kwargs):
        calls.append((target, prompt, kwargs))
        return 0, "OK: verified", "", None

    monkeypatch.setitem(agnt.invoke_run_bundle.__globals__, "invoke_one", fake_invoke_one)

    result = agnt.invoke_run_bundle(bundle, metrics=False)

    assert result["exitCode"] == 0
    tools = calls[0][2]["pi_args"][calls[0][2]["pi_args"].index("--tools") + 1].split(",")
    assert "bash" in tools
    assert "edit" not in tools
    assert "write" not in tools


def test_create_run_bundle_initializes_live_logs_and_lessons_handoff(agnt, tmp_path):
    bundle = agnt.create_run_bundle(
        action="verify",
        routing_task="review",
        bead="pi-ready.1",
        selected_model="openrouter/minimax/minimax-m3",
        output_contract="verification-review",
        runs_dir=tmp_path / "runs",
        id_value="run-live-layout",
    )

    assert (bundle / "live" / "session.jsonl").exists()
    status = json.loads((bundle / "live" / "status.json").read_text(encoding="utf-8"))
    assert status["phase"] == "created"
    assert status["runId"] == "run-live-layout"
    assert (bundle / "artifacts" / "lessons.md").read_text(encoding="utf-8").startswith("# Lessons")
    assert (bundle / "artifacts" / "handoff.md").read_text(encoding="utf-8").startswith("# Handoff")
    result = agnt.load_yaml_json(bundle / "result.yaml")
    assert "live/session.jsonl" in result["artifacts"]
    assert "live/status.json" in result["artifacts"]
    assert "artifacts/lessons.md" in result["artifacts"]
    assert "artifacts/handoff.md" in result["artifacts"]


def test_canonical_invocation_id_survives_run_start_result_and_metrics(agnt, monkeypatch, tmp_path):
    bundle = agnt.create_run_bundle(
        action="verify",
        routing_task="review",
        bead="pi-test.canonical",
        selected_model="openrouter/minimax/minimax-m3",
        parent_session_id="parent-session",
        output_contract="verification-review",
        runs_dir=tmp_path / "runs",
        id_value="readable-run-id",
    )
    invocation = agnt.load_yaml_json(bundle / "invocation.yaml")
    invocation_id = invocation["invocationId"]
    UUID(invocation_id)
    assert invocation["schemaVersion"] == 2
    assert invocation_id != invocation["id"]
    assert agnt.load_yaml_json(bundle / "result.yaml")["invocationId"] == invocation_id

    def fake_invoke_one(target, prompt, **kwargs):
        assert kwargs["invocation_id"] == invocation_id
        assert kwargs["parent_session_id"] == "parent-session"
        assert kwargs["work_item"] == "pi-test.canonical"
        return 0, "OK: verified", "", {
            "schemaVersion": 2,
            "invocationId": invocation_id,
            "recordId": "legacy-selector",
            "target": target,
            "artifactRefs": [],
        }

    monkeypatch.setitem(agnt.invoke_run_bundle.__globals__, "invoke_one", fake_invoke_one)
    agnt.invoke_run_bundle(bundle, metrics_dir=tmp_path / "metrics")

    result = agnt.load_yaml_json(bundle / "result.yaml")
    metric = agnt.load_yaml_json(bundle / result["metricsRef"])
    events = [json.loads(line) for line in (bundle / "live" / "session.jsonl").read_text(encoding="utf-8").splitlines()]
    invoke_events = [event for event in events if event["event"].startswith("worker_invocation_")]

    assert result["schemaVersion"] == 2
    assert result["invocationId"] == invocation_id
    assert metric["invocationId"] == invocation_id
    assert all(event["invocationId"] == invocation_id for event in invoke_events)
    assert metric["artifactRefs"]
    assert set(metric["artifactRefs"]).issubset(result["artifacts"])
    assert agnt.validate_run_bundle(bundle) == []


def test_legacy_v1_bundle_execution_migrates_to_fresh_canonical_invocation_id(agnt, monkeypatch, tmp_path):
    bundle = tmp_path / "legacy-readable-id"
    bundle.mkdir()
    agnt.write_yaml_json(bundle / "invocation.yaml", {
        "schemaVersion": 1,
        "id": "legacy-readable-id",
        "action": "review",
        "routingTask": "review",
        "model": "openrouter/minimax/minimax-m3",
        "allowedEffects": ["read_workspace", "write_artifacts"],
        "createdAt": "2026-06-27T01:02:03Z",
    })
    agnt.write_yaml_json(bundle / "result.yaml", {
        "schemaVersion": 1,
        "invocationId": "legacy-readable-id",
        "status": "needs-human",
        "summary": "Legacy bundle",
        "evidence": [],
        "artifacts": [],
        "followUps": [],
    })
    assert agnt.validate_run_bundle(bundle) == []
    captured = {}

    def fake_invoke_one(target, prompt, **kwargs):
        captured.update(kwargs)
        return 0, "OK: legacy bundle executed", "", {
            "schemaVersion": 2,
            "invocationId": kwargs["invocation_id"],
            "recordId": "legacy-selector",
            "target": target,
            "artifactRefs": [],
        }

    monkeypatch.setitem(agnt.invoke_run_bundle.__globals__, "invoke_one", fake_invoke_one)
    agnt.invoke_run_bundle(bundle, metrics_dir=tmp_path / "metrics")

    invocation = agnt.load_yaml_json(bundle / "invocation.yaml")
    result = agnt.load_yaml_json(bundle / "result.yaml")
    metric = agnt.load_yaml_json(next((tmp_path / "metrics").glob("*.metrics.json")))
    events = [json.loads(line) for line in (bundle / "live" / "session.jsonl").read_text(encoding="utf-8").splitlines()]
    invocation_id = captured["invocation_id"]
    UUID(invocation_id)
    assert invocation_id != invocation["id"]
    assert invocation["schemaVersion"] == 2
    assert invocation["invocationId"] == invocation_id
    assert result["schemaVersion"] == 2
    assert result["invocationId"] == invocation_id
    assert metric["invocationId"] == invocation_id
    assert all(event["invocationId"] == invocation_id for event in events)
    assert agnt.validate_run_bundle(bundle) == []


def test_render_invocation_prompt_includes_ticket_description(agnt, tmp_path):
    bundle = agnt.create_run_bundle(
        action="review",
        routing_task="review",
        bead="pi-ready.1",
        selected_model="openrouter/minimax/minimax-m3",
        ticket_metadata={"title": "Review plan", "description": "Read docs/PLAN.md and report stop conditions."},
        output_contract="findings-with-evidence",
        runs_dir=tmp_path / "runs",
        id_value="run-description",
    )

    prompt = agnt.render_invocation_prompt(agnt.load_yaml_json(bundle / "invocation.yaml"))

    assert "Review plan" in prompt
    assert "Read docs/PLAN.md and report stop conditions." in prompt


def test_invoke_run_bundle_fails_unresolved_tool_call_markup(agnt, monkeypatch, tmp_path):
    bundle = agnt.create_run_bundle(
        action="review",
        routing_task="review",
        bead="pi-ready.1",
        selected_model="openrouter/minimax/minimax-m3",
        output_contract="findings-with-evidence",
        runs_dir=tmp_path / "runs",
        id_value="run-tool-call",
    )

    def fake_invoke_one(target, prompt, **kwargs):
        return 0, '<|tool_call>call:ls{path:"."}<tool_call|>', "", None

    monkeypatch.setitem(agnt.invoke_run_bundle.__globals__, "invoke_one", fake_invoke_one)

    result = agnt.invoke_run_bundle(bundle, metrics=False)

    assert result["exitCode"] != 0
    result_doc = agnt.load_yaml_json(bundle / "result.yaml")
    assert result_doc["status"] == "failed"
    assert "unresolved tool call" in result_doc["summary"]


def test_invoke_run_bundle_fails_empty_terminal_response(agnt, monkeypatch, tmp_path):
    bundle = agnt.create_run_bundle(
        action="review",
        routing_task="review",
        bead="pi-ready.empty-response",
        runs_dir=tmp_path,
        id_value="empty-response",
    )

    def fake_invoke_one(target, prompt, **kwargs):
        return 0, " \n\t ", "", None

    monkeypatch.setitem(agnt.invoke_run_bundle.__globals__, "invoke_one", fake_invoke_one)

    result = agnt.invoke_run_bundle(bundle, metrics=False)

    assert result["exitCode"] != 0
    result_doc = agnt.load_yaml_json(bundle / "result.yaml")
    assert result_doc["status"] == "failed"
    assert "empty terminal response" in result_doc["summary"]
    assert any("empty terminal response" in item for item in result_doc["evidence"])


def test_invoke_run_bundle_fails_explicit_error_terminal_response(agnt, monkeypatch, tmp_path):
    bundle = agnt.create_run_bundle(
        action="review",
        routing_task="review",
        bead="pi-ready.semantic-error",
        runs_dir=tmp_path,
        id_value="semantic-error",
    )

    def fake_invoke_one(target, prompt, **kwargs):
        return 0, "# Review — ERROR\n\nEvidence: portability defect remains.\n\n**Verdict: ERROR**\n", "", None

    monkeypatch.setitem(agnt.invoke_run_bundle.__globals__, "invoke_one", fake_invoke_one)

    result = agnt.invoke_run_bundle(bundle, metrics=False)

    assert result["exitCode"] != 0
    result_doc = agnt.load_yaml_json(bundle / "result.yaml")
    assert result_doc["status"] == "failed"
    assert "explicit ERROR terminal response" in result_doc["summary"]
    assert any("semantic outcome was ERROR" in item for item in result_doc["evidence"])
    live_status = agnt.load_yaml_json(bundle / "live" / "status.json")
    assert live_status["semanticOutcome"] == "error"


def test_invoke_run_bundle_semantic_failure_metrics_use_effective_exit(agnt, monkeypatch, tmp_path):
    bundle = agnt.create_run_bundle(
        action="review",
        routing_task="review",
        bead="pi-ready.semantic-metrics",
        runs_dir=tmp_path,
        id_value="semantic-metrics",
    )

    def fake_invoke_one(target, prompt, **kwargs):
        return 0, "ERROR: verification failed.\n", "", {
            "schemaVersion": 2,
            "invocationId": kwargs["invocation_id"],
            "recordId": "semantic-metrics",
            "target": target,
            "status": "succeeded",
            "exitCode": 0,
            "failureClass": None,
            "artifactRefs": [],
        }

    monkeypatch.setitem(agnt.invoke_run_bundle.__globals__, "invoke_one", fake_invoke_one)

    result = agnt.invoke_run_bundle(bundle, metrics_dir=tmp_path / "metrics")
    metric = agnt.load_yaml_json(bundle / result["metricsRef"])

    assert result["exitCode"] == metric["exitCode"] != 0
    assert metric["status"] == "failed"
    assert metric["executionOutcome"] == "failed"
    assert metric["failureClass"] == "process"


def test_invoke_run_bundle_accepts_markdown_ok_terminal_response(agnt, monkeypatch, tmp_path):
    bundle = agnt.create_run_bundle(
        action="review",
        routing_task="review",
        bead="pi-ready.semantic-ok",
        runs_dir=tmp_path,
        id_value="semantic-ok",
    )

    def fake_invoke_one(target, prompt, **kwargs):
        return 0, "# Verification Review — OK\n\nEvidence: the report discusses ERROR outcomes, but checks passed.\n", "", None

    monkeypatch.setitem(agnt.invoke_run_bundle.__globals__, "invoke_one", fake_invoke_one)

    result = agnt.invoke_run_bundle(bundle, metrics=False)

    assert result["exitCode"] == 0
    assert result["semanticOutcome"] == "ok"
    assert agnt.load_yaml_json(bundle / "result.yaml")["status"] == "succeeded"


def test_invoke_run_bundle_transport_failure_wins_over_ok_marker(agnt, monkeypatch, tmp_path):
    bundle = agnt.create_run_bundle(
        action="review",
        routing_task="review",
        bead="pi-ready.transport-error",
        runs_dir=tmp_path,
        id_value="transport-error",
    )

    def fake_invoke_one(target, prompt, **kwargs):
        return 7, "OK: report was generated before transport failure.\n", "worker crashed", None

    monkeypatch.setitem(agnt.invoke_run_bundle.__globals__, "invoke_one", fake_invoke_one)

    result = agnt.invoke_run_bundle(bundle, metrics=False)

    assert result["exitCode"] == 7
    assert result["semanticOutcome"] == "ok"
    result_doc = agnt.load_yaml_json(bundle / "result.yaml")
    assert result_doc["status"] == "failed"
    assert "exit code 7" in result_doc["summary"]


def test_invoke_run_bundle_fails_missing_terminal_marker(agnt, monkeypatch, tmp_path):
    bundle = agnt.create_run_bundle(
        action="review",
        routing_task="review",
        bead="pi-ready.semantic-missing",
        runs_dir=tmp_path,
        id_value="semantic-missing",
    )

    def fake_invoke_one(target, prompt, **kwargs):
        return 0, "Checks passed, but no terminal marker was emitted.\n", "", None

    monkeypatch.setitem(agnt.invoke_run_bundle.__globals__, "invoke_one", fake_invoke_one)

    result = agnt.invoke_run_bundle(bundle, metrics=False)

    assert result["exitCode"] != 0
    assert result["semanticOutcome"] == "missing"
    result_doc = agnt.load_yaml_json(bundle / "result.yaml")
    assert result_doc["status"] == "failed"
    assert "lacked an explicit terminal marker" in result_doc["summary"]


def test_invoke_run_bundle_fails_ambiguous_terminal_markers(agnt, monkeypatch, tmp_path):
    bundle = agnt.create_run_bundle(
        action="review",
        routing_task="review",
        bead="pi-ready.semantic-ambiguous",
        runs_dir=tmp_path,
        id_value="semantic-ambiguous",
    )

    def fake_invoke_one(target, prompt, **kwargs):
        return 0, "ERROR: first conclusion.\nOK: second conflicting conclusion.\n", "", None

    monkeypatch.setitem(agnt.invoke_run_bundle.__globals__, "invoke_one", fake_invoke_one)

    result = agnt.invoke_run_bundle(bundle, metrics=False)

    assert result["exitCode"] != 0
    assert result["semanticOutcome"] == "ambiguous"
    result_doc = agnt.load_yaml_json(bundle / "result.yaml")
    assert result_doc["status"] == "failed"
    assert "ambiguous terminal markers" in result_doc["summary"]
