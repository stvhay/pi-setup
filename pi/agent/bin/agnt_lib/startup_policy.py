from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List
from urllib.parse import urlparse

PASS = "pass"
WARNING = "warning"
FAIL = "fail"

ORCHESTRATOR_STARTUP_PROFILE = "orchestrator-startup"
ORCHESTRATOR_STARTUP_CHECKS = [
    "command.pi",
    "command.bd",
    "python.version",
    "git.root",
    "node.version",
    "catalog.parse",
    "verification.commands",
    "provider.env",
    "env.SEARXNG_URL",
    "beads.workspace",
]
KNOWN_PROFILES = {ORCHESTRATOR_STARTUP_PROFILE: ORCHESTRATOR_STARTUP_CHECKS}
PROJECT_INTENT_PATH = Path(".pi") / "doctor-intent.json"
GLOBAL_INTENT_PATH = Path(".pi") / "agent" / "doctor-intent.json"


def check_result(
    check_id: str,
    status: str,
    message: str,
    *,
    severity: str = "low",
    evidence: Dict[str, Any] | None = None,
    suggested_actions: List[str] | None = None,
) -> Dict[str, Any]:
    return {
        "id": check_id,
        "status": status,
        "severity": severity,
        "message": message,
        "evidence": evidence or {},
        "suggestedActions": suggested_actions or [],
    }


def profile_check_names(profile: str) -> List[str]:
    if profile not in KNOWN_PROFILES:
        raise KeyError(profile)
    return list(KNOWN_PROFILES[profile])


def check_searxng_url(environ: Dict[str, str] | None = None) -> Dict[str, Any]:
    env = environ if environ is not None else os.environ
    raw = str(env.get("SEARXNG_URL") or "").strip()
    if not raw:
        return check_result(
            "env.SEARXNG_URL",
            FAIL,
            "SEARXNG_URL is required for search/research startup readiness",
            severity="high",
            evidence={"SEARXNG_URL": "missing"},
            suggested_actions=["Set SEARXNG_URL to the SearXNG instance URL before enabling orchestrated search/research work."],
        )
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return check_result(
            "env.SEARXNG_URL",
            FAIL,
            "SEARXNG_URL must be an http(s) URL",
            severity="high",
            evidence={"SEARXNG_URL": "present:redacted", "validUrl": False},
            suggested_actions=["Set SEARXNG_URL to a valid http(s) SearXNG instance URL."],
        )
    return check_result(
        "env.SEARXNG_URL",
        PASS,
        "SEARXNG_URL is configured",
        evidence={"SEARXNG_URL": "present:redacted", "scheme": parsed.scheme},
    )


def check_beads_workspace(project_root: Path | str | None = None) -> Dict[str, Any]:
    root = Path(project_root or Path.cwd()).expanduser().resolve()
    beads_dir = root / ".beads"
    if not beads_dir.is_dir():
        return check_result(
            "beads.workspace",
            FAIL,
            "Beads workspace is required for orchestrated queue dispatch",
            severity="high",
            evidence={"root": str(root), "beadsDir": str(beads_dir), "exists": False},
            suggested_actions=["Initialize or restore the project .beads workspace before starting the orchestrator runner."],
        )
    return check_result(
        "beads.workspace",
        PASS,
        "Beads workspace is present",
        evidence={"root": str(root), "beadsDir": str(beads_dir), "exists": True},
    )


def _read_intent_file(path: Path) -> Dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_invalid": str(exc)}
    return data if isinstance(data, dict) else {"_invalid": "intent file root must be an object"}


def _merge_intent(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in overlay.items():
        if key == "intentionallyAbsentEnv" and isinstance(value, dict):
            target = merged.setdefault("intentionallyAbsentEnv", {})
            if isinstance(target, dict):
                for env_name, reason in value.items():
                    if isinstance(env_name, str) and env_name:
                        target[env_name] = str(reason or "acknowledged")[:300]
        elif key.startswith("_"):
            merged[key] = value
    return merged


def load_intent_config(project_root: Path | str | None = None, home: Path | str | None = None) -> Dict[str, Any]:
    root = Path(project_root or Path.cwd()).expanduser().resolve()
    home_path = Path(home or os.environ.get("HOME") or str(Path.home())).expanduser().resolve()
    sources = [home_path / GLOBAL_INTENT_PATH, root / PROJECT_INTENT_PATH]
    intent: Dict[str, Any] = {"intentionallyAbsentEnv": {}, "sources": []}
    invalid_sources: Dict[str, str] = {}
    for source in sources:
        data = _read_intent_file(source)
        if data is None:
            continue
        intent["sources"].append(str(source))
        if "_invalid" in data:
            invalid_sources[str(source)] = str(data["_invalid"])
            continue
        intent = _merge_intent(intent, data)
    if invalid_sources:
        intent["invalidSources"] = invalid_sources
    return intent


def acknowledged_env(intent: Dict[str, Any], name: str) -> str | None:
    absent = intent.get("intentionallyAbsentEnv") if isinstance(intent, dict) else None
    if not isinstance(absent, dict):
        return None
    reason = absent.get(name)
    if reason is None:
        return None
    text = str(reason or "acknowledged").strip() or "acknowledged"
    return text[:300]


def _acknowledged_provider_warning(check: Dict[str, Any], intent: Dict[str, Any]) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    evidence = check.get("evidence") if isinstance(check.get("evidence"), dict) else {}
    missing = sorted(name for name, state in evidence.items() if state == "missing")
    if not missing:
        return [check], []
    ack = [name for name in missing if acknowledged_env(intent, name)]
    unack = [name for name in missing if name not in ack]
    warnings: List[Dict[str, Any]] = []
    acknowledged: List[Dict[str, Any]] = []
    if unack:
        warning_check = copy.deepcopy(check)
        if ack:
            warning_check["evidence"] = dict(evidence)
            warning_check["evidence"]["acknowledgedEnv"] = ack
            warning_check["message"] = "Some provider environment variables are not set and not acknowledged"
        warnings.append(warning_check)
    if ack:
        ack_check = copy.deepcopy(check)
        ack_check["status"] = WARNING
        ack_check["acknowledged"] = True
        ack_check["message"] = "Provider environment variable absence acknowledged by intent config"
        ack_check["evidence"] = {
            "acknowledgedEnv": ack,
            "reasons": {name: acknowledged_env(intent, name) for name in ack},
        }
        ack_check["suggestedActions"] = []
        acknowledged.append(ack_check)
    return warnings, acknowledged


def build_startup_report(checks: Iterable[Dict[str, Any]], *, intent: Dict[str, Any] | None = None, profile: str = ORCHESTRATOR_STARTUP_PROFILE) -> Dict[str, Any]:
    intent = intent or {"intentionallyAbsentEnv": {}}
    normalized = [copy.deepcopy(check) for check in checks]
    failures = [check for check in normalized if check.get("status") == FAIL]
    warnings: List[Dict[str, Any]] = []
    acknowledged_warnings: List[Dict[str, Any]] = []
    for check in normalized:
        if check.get("status") != WARNING:
            continue
        if check.get("id") == "provider.env":
            unack, ack = _acknowledged_provider_warning(check, intent)
            warnings.extend(unack)
            acknowledged_warnings.extend(ack)
        else:
            warnings.append(check)
    status = "failed" if failures else ("degraded" if warnings else "passed")
    background_allowed = not failures and not warnings
    suggested: List[str] = []
    for check in [*failures, *warnings]:
        suggested.extend(check.get("suggestedActions") or [])
    report = {
        "schemaVersion": 1,
        "profile": profile,
        "status": status,
        "passed": background_allowed,
        "summary": {
            "checkCount": len(normalized),
            "failureCount": len(failures),
            "warningCount": len(warnings),
            "acknowledgedWarningCount": len(acknowledged_warnings),
        },
        "checks": normalized,
        "failures": failures,
        "warnings": warnings,
        "acknowledgedWarnings": acknowledged_warnings,
        "startup": {
            "backgroundDispatchAllowed": background_allowed,
            "requiresZeroFailures": True,
            "requiresZeroUnacknowledgedWarnings": True,
        },
        "intent": {
            "sources": list(intent.get("sources") or []),
            "invalidSources": dict(intent.get("invalidSources") or {}),
        },
        "suggestedActions": suggested,
    }
    return report


__all__ = [
    "KNOWN_PROFILES",
    "ORCHESTRATOR_STARTUP_CHECKS",
    "ORCHESTRATOR_STARTUP_PROFILE",
    "build_startup_report",
    "check_beads_workspace",
    "check_searxng_url",
    "load_intent_config",
    "profile_check_names",
]
