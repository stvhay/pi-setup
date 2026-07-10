from __future__ import annotations

import json
from typing import Any, Dict, List, Mapping

VALID_ACTIONS = {"implement", "review", "verify", "plan", "research", "finish", "maintenance"}
READ_ONLY_ACTIONS = {"review", "verify", "plan", "research", "maintenance"}
VALID_RISKS = {"low", "medium", "high"}
VALID_BUDGETS = {"cheap", "balanced", "quality"}
VALID_MODEL_POLICY_MODES = {"auto", "constraints"}
VALID_DIVERSITY = {"none", "normal", "high"}
VALID_THINKING_POLICIES = {"auto"}
VALID_WORKTREE_POLICIES = {"epic-worktree", "existing-worktree", "none"}
VALID_SESSION_POLICIES = {"recorded", "no-session"}
VALID_MEMORY_POLICIES = {"auto", "active", "passive", "disabled"}
VALID_ALLOWED_EFFECTS = {
    "read_workspace",
    "write_artifacts",
    "edit_files",
    "write_workspace",
    "update_beads",
    "external_read",
    "external_write",
    "push",
    "deploy",
    "delete_files",
}
MODEL_OVERRIDE_KEYS = {"model", "selectedModel", "modelOverride", "target", "provider", "id", "override"}


def _is_dict(value: Any) -> bool:
    return isinstance(value, dict)


def _string_list(value: Any) -> List[str] | None:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        return None
    return list(value)


def _bool_field(value: Any) -> bool:
    return isinstance(value, bool) and value is True


def _metadata_pi(metadata: Any) -> Dict[str, Any] | None:
    if not isinstance(metadata, dict):
        return None
    candidate = metadata.get("pi")
    if candidate is None:
        return None
    return dict(candidate) if isinstance(candidate, dict) else None


def _acceptance_items(bead: Mapping[str, Any] | None, pi_meta: Mapping[str, Any]) -> List[str]:
    raw = None
    if bead:
        raw = bead.get("acceptance_criteria") or bead.get("acceptanceCriteria")
    if raw is None:
        raw = pi_meta.get("acceptanceCriteria")
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    if raw is None:
        return []
    return [item.strip() for item in str(raw).replace(";", "\n").splitlines() if item.strip()]


def _validate_model_policy(pi_meta: Mapping[str, Any], failures: List[str]) -> Dict[str, Any]:
    for key in MODEL_OVERRIDE_KEYS:
        if key in pi_meta:
            failures.append(f"model override is not allowed in metadata.pi.{key}; use modelPolicy constraints")

    raw = pi_meta.get("modelPolicy", {"mode": "auto"})
    if not isinstance(raw, dict):
        failures.append("metadata.pi.modelPolicy must be an object")
        return {"mode": "auto", "diversity": "normal", "avoidFamilies": []}

    for key in MODEL_OVERRIDE_KEYS:
        if key in raw:
            failures.append(f"model override is not allowed in metadata.pi.modelPolicy.{key}; use routing policy constraints")

    mode = raw.get("mode", "auto")
    if mode not in VALID_MODEL_POLICY_MODES:
        failures.append(f"metadata.pi.modelPolicy.mode must be one of {sorted(VALID_MODEL_POLICY_MODES)}")
        mode = "auto"

    diversity = raw.get("diversity", "normal")
    if diversity not in VALID_DIVERSITY:
        failures.append(f"metadata.pi.modelPolicy.diversity must be one of {sorted(VALID_DIVERSITY)}")
        diversity = "normal"

    avoid_families = raw.get("avoidFamilies", [])
    if _string_list(avoid_families) is None:
        failures.append("metadata.pi.modelPolicy.avoidFamilies must be a list of strings")
        avoid_families = []

    normalized = {"mode": mode, "diversity": diversity, "avoidFamilies": list(avoid_families)}
    if isinstance(raw.get("localOk"), bool):
        normalized["localOk"] = raw["localOk"]
    return normalized


def _validate_continuation(pi_meta: Mapping[str, Any], failures: List[str], *, action: str | None) -> Dict[str, str] | None:
    raw = pi_meta.get("continuation")
    if raw is None:
        return None
    if action != "implement":
        failures.append("metadata.pi.continuation is allowed only for implement actions")
        return None
    if not isinstance(raw, dict):
        failures.append("metadata.pi.continuation must be an object")
        return None
    mode = raw.get("mode")
    predecessor = raw.get("predecessor")
    approval_ref = raw.get("approvalRef")
    if mode != "checkpoint":
        failures.append("metadata.pi.continuation.mode must be 'checkpoint'")
    if not isinstance(predecessor, str) or not predecessor:
        failures.append("metadata.pi.continuation.predecessor must be a non-empty string")
    if not isinstance(approval_ref, str) or not approval_ref:
        failures.append("metadata.pi.continuation.approvalRef must be a non-empty string")
    if mode != "checkpoint" or not isinstance(predecessor, str) or not predecessor or not isinstance(approval_ref, str) or not approval_ref:
        return None
    return {"mode": mode, "predecessor": predecessor, "approvalRef": approval_ref}


def _validate_closeout(pi_meta: Mapping[str, Any], blockers: List[str], *, required: bool) -> Dict[str, Any]:
    raw = pi_meta.get("closeout")
    if raw is None and not required:
        return {
            "requiresEvidence": False,
            "requiresResolvedApprovals": False,
            "requiresFollowUpsReconciled": False,
        }
    if not isinstance(raw, dict):
        blockers.append("metadata.pi.closeout is required and must be an object")
        raw = {}
    normalized = {
        "requiresEvidence": _bool_field(raw.get("requiresEvidence")),
        "requiresResolvedApprovals": _bool_field(raw.get("requiresResolvedApprovals")),
        "requiresFollowUpsReconciled": _bool_field(raw.get("requiresFollowUpsReconciled")),
    }
    if required:
        for key, value in normalized.items():
            if value is not True:
                blockers.append(f"metadata.pi.closeout.{key} must be true")
    return normalized


def _status(failures: List[str], human_actions: List[str], blockers: List[str]) -> str:
    if failures:
        return "invalid"
    if human_actions:
        return "needs-human"
    if blockers:
        return "blocked"
    return "dispatchable"


def _result(
    *,
    status: str,
    normalized: Dict[str, Any] | None = None,
    failures: List[str] | None = None,
    blockers: List[str] | None = None,
    human_actions: List[str] | None = None,
    warnings: List[str] | None = None,
    bead_id: str | None = None,
) -> Dict[str, Any]:
    result = {
        "schemaVersion": 1,
        "status": status,
        "dispatchable": status == "dispatchable",
        "normalized": normalized or {},
        "failures": failures or [],
        "blockers": blockers or [],
        "humanActions": human_actions or [],
        "warnings": warnings or [],
    }
    if bead_id is not None:
        result["bead"] = bead_id
    return result


def validate_orchestration_metadata(metadata: Any, *, bead: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    """Validate the Beads metadata.pi dispatch contract.

    The validator is intentionally dependency-free and returns plain dictionaries
    so Beads readers, runner code, and UI extensions can share one deterministic
    status contract before any live dispatch behavior exists.
    """
    failures: List[str] = []
    blockers: List[str] = []
    human_actions: List[str] = []
    warnings: List[str] = []

    pi_meta = _metadata_pi(metadata)
    if pi_meta is None:
        blockers.append("metadata.pi is required for automatic dispatch")
        status = _status(failures, human_actions, blockers)
        return _result(
            status=status,
            failures=failures,
            blockers=blockers,
            human_actions=human_actions,
            warnings=warnings,
        )

    action = pi_meta.get("action")
    if not isinstance(action, str) or not action:
        blockers.append("metadata.pi.action is required")
        action = None
    elif action not in VALID_ACTIONS:
        failures.append(f"unknown action: {action}")

    routing_task = pi_meta.get("routingTask")
    if not isinstance(routing_task, str) or not routing_task:
        blockers.append("metadata.pi.routingTask is required")
        routing_task = None

    role = pi_meta.get("role")
    if role is not None and not isinstance(role, str):
        failures.append("metadata.pi.role must be a string when present")
        role = None

    skills = pi_meta.get("skills", [])
    if _string_list(skills) is None:
        failures.append("metadata.pi.skills must be a list of strings when present")
        skills = []

    reference_lists: Dict[str, List[str]] = {}
    for key in ("inputRefs", "approvalRefs", "decisionRefs"):
        raw_refs = pi_meta.get(key, [])
        refs = _string_list(raw_refs)
        if refs is None:
            failures.append(f"metadata.pi.{key} must be a list of strings when present")
            refs = []
        reference_lists[key] = refs

    allowed_effects = _string_list(pi_meta.get("allowedEffects"))
    if allowed_effects is None:
        blockers.append("metadata.pi.allowedEffects must be a non-empty list of strings")
        allowed_effects = []
    else:
        unknown_effects = sorted(set(allowed_effects) - VALID_ALLOWED_EFFECTS)
        if unknown_effects:
            failures.append(f"unknown allowedEffects: {', '.join(unknown_effects)}")

    risk = pi_meta.get("risk", "medium")
    if risk not in VALID_RISKS:
        failures.append(f"metadata.pi.risk must be one of {sorted(VALID_RISKS)}")
        risk = "medium"

    budget = pi_meta.get("budget", "balanced")
    if budget not in VALID_BUDGETS:
        failures.append(f"metadata.pi.budget must be one of {sorted(VALID_BUDGETS)}")
        budget = "balanced"

    model_policy = _validate_model_policy(pi_meta, failures)

    thinking_policy = pi_meta.get("thinkingPolicy", "auto")
    if thinking_policy not in VALID_THINKING_POLICIES:
        failures.append("metadata.pi.thinkingPolicy must be 'auto'; direct thinking overrides are not allowed")
        thinking_policy = "auto"

    session_policy = pi_meta.get("sessionPolicy", "recorded")
    if session_policy not in VALID_SESSION_POLICIES:
        failures.append(f"metadata.pi.sessionPolicy must be one of {sorted(VALID_SESSION_POLICIES)}")
        session_policy = "recorded"

    memory_policy = pi_meta.get("memoryPolicy", "auto")
    if memory_policy not in VALID_MEMORY_POLICIES:
        failures.append(f"metadata.pi.memoryPolicy must be one of {sorted(VALID_MEMORY_POLICIES)}")
        memory_policy = "auto"

    approved = bool(pi_meta.get("approved", False))
    human_approval = pi_meta.get("humanApproval")
    human_approval_valid = (
        isinstance(human_approval, dict)
        and isinstance(human_approval.get("decisionBead"), str)
        and bool(human_approval["decisionBead"].strip())
        and isinstance(human_approval.get("resolver"), dict)
        and human_approval["resolver"].get("kind") == "human-ui"
        and isinstance(human_approval["resolver"].get("sessionId"), str)
        and bool(human_approval["resolver"]["sessionId"].strip())
    )
    epic_id = pi_meta.get("epicId")
    worktree_policy = pi_meta.get("worktreePolicy")
    write_set = _string_list(pi_meta.get("writeSet"))
    closeout = _validate_closeout(pi_meta, blockers, required=action == "implement")
    continuation = _validate_continuation(pi_meta, failures, action=action)

    if action == "implement":
        if approved is not True:
            human_actions.append("metadata.pi.approved must be true before implement dispatch")
        elif not human_approval_valid:
            human_actions.append("metadata.pi.humanApproval with human-ui resolver provenance is required before implement dispatch")
        if not isinstance(epic_id, str) or not epic_id:
            blockers.append("metadata.pi.epicId is required for implement dispatch")
            epic_id = None
        if worktree_policy not in VALID_WORKTREE_POLICIES or worktree_policy == "none":
            blockers.append("metadata.pi.worktreePolicy must select a concrete worktree policy for implement dispatch")
            worktree_policy = None if worktree_policy not in VALID_WORKTREE_POLICIES else worktree_policy
        if write_set is None or not write_set:
            blockers.append("metadata.pi.writeSet is required for implement dispatch")
            write_set = []
        if not _acceptance_items(bead, pi_meta):
            blockers.append("acceptance criteria are required for implement dispatch")
    elif action in READ_ONLY_ACTIONS:
        if write_set is None:
            write_set = []
        if worktree_policy is None:
            worktree_policy = "none"
    else:
        if write_set is None:
            write_set = []

    normalized = {
        "action": action,
        "routingTask": routing_task,
        "role": role,
        "skills": list(skills),
        "approved": approved,
        "humanApproval": human_approval if human_approval_valid else None,
        "inputRefs": reference_lists["inputRefs"],
        "approvalRefs": reference_lists["approvalRefs"],
        "decisionRefs": reference_lists["decisionRefs"],
        "allowedEffects": allowed_effects,
        "risk": risk,
        "budget": budget,
        "modelPolicy": model_policy,
        "thinkingPolicy": thinking_policy,
        "epicId": epic_id,
        "worktreePolicy": worktree_policy,
        "writeSet": write_set or [],
        "closeout": closeout,
        "continuation": continuation,
        "sessionPolicy": session_policy,
        "memoryPolicy": memory_policy,
    }
    status = _status(failures, human_actions, blockers)
    return _result(
        status=status,
        normalized=normalized,
        failures=failures,
        blockers=blockers,
        human_actions=human_actions,
        warnings=warnings,
    )


def _bead_metadata(bead: Mapping[str, Any]) -> Any:
    if "metadata" in bead:
        return bead.get("metadata")
    if "pi" in bead:
        return {"pi": bead.get("pi")}
    return {}


def validate_bead_orchestration_metadata(bead: Mapping[str, Any]) -> Dict[str, Any]:
    """Validate orchestration metadata from a Beads issue object.

    Beads JSON may expose custom metadata as an object or as a JSON-encoded
    string depending on the command/version. This adapter normalizes that input
    and preserves the bead id in the validation result for tree/status views.
    """
    bead_id = str(bead.get("id") or "") if isinstance(bead, Mapping) else ""
    raw = _bead_metadata(bead)
    if isinstance(raw, str):
        try:
            raw = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError as exc:
            return _result(
                status="invalid",
                failures=[f"metadata JSON is invalid: {exc}"],
                bead_id=bead_id or None,
            )
    result = validate_orchestration_metadata(raw, bead=bead)
    if bead_id:
        result["bead"] = bead_id
    return result


__all__ = ["validate_orchestration_metadata", "validate_bead_orchestration_metadata"]
