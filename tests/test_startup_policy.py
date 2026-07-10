from __future__ import annotations

import json
import sys
from pathlib import Path

BIN = Path(__file__).resolve().parents[1] / "pi" / "agent" / "bin"
if str(BIN) not in sys.path:
    sys.path.insert(0, str(BIN))

from agnt_lib.startup_policy import (  # noqa: E402
    ORCHESTRATOR_STARTUP_CHECKS,
    build_startup_report,
    check_searxng_url,
    load_intent_config,
)


def warning_check(check_id: str, evidence: dict[str, str] | None = None) -> dict:
    return {
        "id": check_id,
        "status": "warning",
        "severity": "medium",
        "message": f"{check_id} warning",
        "evidence": evidence or {},
        "suggestedActions": ["fix warning"],
    }


def pass_check(check_id: str) -> dict:
    return {"id": check_id, "status": "pass", "severity": "low", "message": "ok", "evidence": {}, "suggestedActions": []}


def test_orchestrator_startup_profile_lists_required_checks():
    assert ORCHESTRATOR_STARTUP_CHECKS == [
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


def test_searxng_url_is_required_and_redacted(monkeypatch):
    monkeypatch.delenv("SEARXNG_URL", raising=False)
    missing = check_searxng_url()
    assert missing["id"] == "env.SEARXNG_URL"
    assert missing["status"] == "fail"
    assert missing["severity"] == "high"
    assert missing["evidence"]["SEARXNG_URL"] == "missing"

    monkeypatch.setenv("SEARXNG_URL", "https://search.example.invalid/?token=secret-value")
    present = check_searxng_url()
    assert present["status"] == "pass"
    encoded = json.dumps(present)
    assert "secret-value" not in encoded
    assert present["evidence"]["SEARXNG_URL"] == "present:redacted"


def test_load_intent_config_merges_global_then_project(tmp_path):
    home = tmp_path / "home"
    project = tmp_path / "repo"
    global_intent = home / ".pi" / "agent" / "doctor-intent.json"
    project_intent = project / ".pi" / "doctor-intent.json"
    global_intent.parent.mkdir(parents=True)
    project_intent.parent.mkdir(parents=True)
    global_intent.write_text(json.dumps({"intentionallyAbsentEnv": {"ANTHROPIC_API_KEY": "not used"}}), encoding="utf-8")
    project_intent.write_text(json.dumps({"intentionallyAbsentEnv": {"GEMINI_API_KEY": "using Olla route"}}), encoding="utf-8")

    intent = load_intent_config(project_root=project, home=home)

    assert intent["intentionallyAbsentEnv"]["ANTHROPIC_API_KEY"] == "not used"
    assert intent["intentionallyAbsentEnv"]["GEMINI_API_KEY"] == "using Olla route"
    assert str(global_intent) in intent["sources"]
    assert str(project_intent) in intent["sources"]


def test_startup_report_moves_acknowledged_provider_env_out_of_warnings():
    checks = [
        pass_check("command.pi"),
        warning_check("provider.env", {"ANTHROPIC_API_KEY": "missing"}),
    ]
    intent = {"intentionallyAbsentEnv": {"ANTHROPIC_API_KEY": "not used"}}

    report = build_startup_report(checks, intent=intent, profile="orchestrator-startup")

    assert report["status"] == "passed"
    assert report["summary"]["warningCount"] == 0
    assert report["summary"]["acknowledgedWarningCount"] == 1
    assert report["warnings"] == []
    assert report["acknowledgedWarnings"][0]["id"] == "provider.env"
    assert report["acknowledgedWarnings"][0]["evidence"]["acknowledgedEnv"] == ["ANTHROPIC_API_KEY"]
    assert report["startup"]["backgroundDispatchAllowed"] is True


def test_startup_report_blocks_on_unacknowledged_warning_or_failure():
    warning_report = build_startup_report([warning_check("node.version")], intent={}, profile="orchestrator-startup")
    assert warning_report["status"] == "degraded"
    assert warning_report["startup"]["backgroundDispatchAllowed"] is False

    failure = {"id": "env.SEARXNG_URL", "status": "fail", "severity": "high", "message": "missing", "evidence": {}, "suggestedActions": []}
    failure_report = build_startup_report([failure], intent={}, profile="orchestrator-startup")
    assert failure_report["status"] == "failed"
    assert failure_report["startup"]["backgroundDispatchAllowed"] is False
