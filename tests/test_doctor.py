from __future__ import annotations

import json
from unittest.mock import patch

import pytest


class FakeProc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_doctor_report_schema_and_strict_failure(agnt, monkeypatch):
    monkeypatch.setattr(agnt.shutil, "which", lambda name: None if name == "pi" else f"/bin/{name}")
    report = agnt.doctor_report(check_names=["command.pi"])

    assert report["schemaVersion"] == 1
    assert report["status"] == "failed"
    assert report["passed"] is False
    assert report["summary"]["failureCount"] == 1
    assert report["checks"][0]["id"] == "command.pi"
    assert report["checks"][0]["status"] == "fail"

    with patch.object(agnt, "doctor_report", return_value=report):
        assert agnt.cmd_doctor(["--strict", "--check", "command.pi"]) == 1


def test_doctor_catalog_parse_does_not_require_removed_models_json(agnt, tmp_path):
    (tmp_path / "catalog.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "settings.json").write_text("{}\n", encoding="utf-8")

    with patch.dict(agnt.check_catalog_parse.__globals__, {"ROOT": tmp_path}):
        report = agnt.doctor_report(check_names=["catalog.parse"])

    assert report["passed"] is True
    assert report["checks"][0]["evidence"]["parsed"] == ["catalog.json", "settings.json"]


def test_doctor_redacts_provider_env_vars(agnt, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "secret-openrouter-key")
    report = agnt.doctor_report(check_names=["provider.env"])
    encoded = json.dumps(report)

    assert "secret-openrouter-key" not in encoded
    check = report["checks"][0]
    assert check["id"] == "provider.env"
    assert check["evidence"]["OPENROUTER_API_KEY"] == "present:redacted"


def test_doctor_accepts_pi_login_provider_auth(agnt, monkeypatch, tmp_path):
    (tmp_path / "settings.json").write_text(
        json.dumps({"enabledModels": ["openrouter/minimax/minimax-m3"]}),
        encoding="utf-8",
    )
    (tmp_path / "auth.json").write_text(
        json.dumps({"openrouter": {"type": "api_key", "key": "secret"}}),
        encoding="utf-8",
    )
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    with patch.dict(agnt.check_provider_env.__globals__, {"ROOT": tmp_path}):
        report = agnt.doctor_report(check_names=["provider.env"])

    check = report["checks"][0]
    assert check["status"] == "pass"
    assert check["evidence"]["openrouter.auth"] == "present:redacted"
    assert "secret" not in json.dumps(report)


def test_doctor_rejects_unusable_pi_login_provider_auth(agnt, monkeypatch, tmp_path):
    (tmp_path / "settings.json").write_text(
        json.dumps({"enabledModels": ["openrouter/minimax/minimax-m3"]}),
        encoding="utf-8",
    )
    (tmp_path / "auth.json").write_text(
        json.dumps({"openrouter": {"type": "api_key", "key": "  "}}),
        encoding="utf-8",
    )
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    with patch.dict(agnt.check_provider_env.__globals__, {"ROOT": tmp_path}):
        report = agnt.doctor_report(check_names=["provider.env"])

    check = report["checks"][0]
    assert check["status"] == "warning"
    assert check["evidence"]["OPENROUTER_API_KEY"] == "missing"


def test_doctor_provider_env_ignores_unused_api_key_providers(agnt, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    report = agnt.doctor_report(check_names=["provider.env"])

    check = report["checks"][0]
    assert "ANTHROPIC_API_KEY" not in check["evidence"]
    assert "OPENAI_API_KEY" not in check["evidence"]


def test_verification_commands_use_current_git_root(agnt, monkeypatch, tmp_path):
    repo = tmp_path / "project"
    scripts = repo / "scripts"
    scripts.mkdir(parents=True)
    check_script = scripts / "check-pi-config.sh"
    check_script.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (repo / ".venv" / "bin").mkdir(parents=True)
    (repo / ".venv" / "bin" / "python").write_text("", encoding="utf-8")
    monkeypatch.chdir(repo)
    monkeypatch.setattr(agnt.shutil, "which", lambda name: f"/bin/{name}")

    def fake_run(argv, **kwargs):
        if argv[:3] == ["git", "-C", str(repo)] and argv[3:] == ["rev-parse", "--show-toplevel"]:
            return FakeProc(returncode=0, stdout=f"{repo}\n")
        return FakeProc(returncode=1)

    monkeypatch.setattr(agnt.subprocess, "run", fake_run)
    report = agnt.doctor_report(check_names=["verification.commands"])
    check = report["checks"][0]

    assert check["status"] == "pass"
    assert check["evidence"]["checkPiConfig"] == str(check_script)


def test_node_non_lts_with_nvm_suggests_lts_without_mutation(agnt, monkeypatch, tmp_path):
    home = tmp_path / "home"
    nvm = home / ".nvm"
    profile_d = home / ".local" / "etc" / "profile.d"
    nvm.mkdir(parents=True)
    profile_d.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("IN_NIX_SHELL", raising=False)
    monkeypatch.delenv("NIX_PROFILES", raising=False)
    monkeypatch.setattr(agnt.shutil, "which", lambda name: "/usr/local/bin/node" if name == "node" else None)

    def fake_run(argv, **kwargs):
        if argv == ["node", "--version"]:
            return FakeProc(returncode=0, stdout="v23.1.0\n")
        return FakeProc(returncode=1)

    monkeypatch.setattr(agnt.subprocess, "run", fake_run)
    report = agnt.doctor_report(check_names=["node.version"])
    check = report["checks"][0]

    assert check["status"] == "warning"
    assert check["evidence"]["version"] == "v23.1.0"
    assert check["evidence"]["manager"] == "nvm"
    assert any("nvm install --lts" in action for action in check["suggestedActions"])
    assert any(".local/etc/profile.d/pi-node-lts.sh" in action for action in check["suggestedActions"])
    assert not (profile_d / "pi-node-lts.sh").exists()


def test_node_lts_passes(agnt, monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("IN_NIX_SHELL", raising=False)
    monkeypatch.delenv("NIX_PROFILES", raising=False)
    monkeypatch.setattr(agnt.shutil, "which", lambda name: "/usr/local/bin/node" if name == "node" else None)

    def fake_run(argv, **kwargs):
        if argv == ["node", "--version"]:
            return FakeProc(returncode=0, stdout="v22.13.1\n")
        return FakeProc(returncode=1)

    monkeypatch.setattr(agnt.subprocess, "run", fake_run)
    report = agnt.doctor_report(check_names=["node.version"])

    assert report["checks"][0]["status"] == "pass"


def test_doctor_rejects_retired_profile_option(agnt):
    with pytest.raises(SystemExit):
        agnt.cmd_doctor(["--profile", "orchestrator-startup"])


@pytest.mark.parametrize("payload", [
    {"unsupported": True, "code": "embedded_unsupported", "checks_supported_in_embedded_mode": ["conventions"]},
    {"code": "embedded_unsupported", "overall_ok": True, "checks": [{"name": "db", "status": "ok"}], "checks_supported_in_embedded_mode": 1},
    {"error": "unavailable"},
    {"overall_ok": False, "checks": [{"name": "db", "status": "error"}]},
    {"overall_ok": True, "checks": [{"name": "db", "status": "warning"}]},
    {"overall_ok": True, "checks": []},
    [], "bad json",
])
@pytest.mark.parametrize("stream", ["stdout", "stderr"])
def test_beads_doctor_zero_exit_is_not_health_proof(agnt, monkeypatch, tmp_path, payload, stream):
    (tmp_path / ".beads").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(agnt.shutil, "which", lambda _name: "/bin/bd")
    calls = []
    def run(argv, **_kwargs):
        calls.append(argv)
        if argv[1] == "version":
            return FakeProc(stdout=json.dumps({"version": "1.3.1"}))
        if "--check=conventions" in argv:
            return FakeProc(stdout=json.dumps({"overall_ok": True, "checks": [{"name": "lint", "status": "ok"}]}))
        if argv[1] == "list":
            return FakeProc(stdout="[]")
        return FakeProc(**{stream: payload if isinstance(payload, str) else json.dumps(payload)})
    monkeypatch.setattr(agnt.subprocess, "run", run)
    report = agnt.doctor_report(check_names=["command.bd"])
    assert report["status"] == "degraded"
    assert report["passed"] is False
    assert report["checks"][0]["evidence"]["healthVerified"] is False
    assert ["/bin/bd", "doctor", "--json"] in calls
    if isinstance(payload, dict) and payload.get("unsupported"):
        assert report["checks"][0]["evidence"]["conventionsVerified"] is True
        assert report["checks"][0]["evidence"]["queryVerified"] is True
    assert all("--fix" not in command for command in calls)


@pytest.mark.parametrize("version,expected", [("1.3.1", "passed"), ("1.2.2", "degraded")])
def test_beads_doctor_checks_supported_version_and_json_health(agnt, monkeypatch, tmp_path, version, expected):
    (tmp_path / ".beads").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(agnt.shutil, "which", lambda _name: "/bin/bd")
    def run(argv, **_kwargs):
        payload = {"version": version} if argv[1] == "version" else {
            "overall_ok": True, "checks": [{"name": "db", "status": "ok"}],
        }
        return FakeProc(stdout=json.dumps(payload))
    monkeypatch.setattr(agnt.subprocess, "run", run)
    report = agnt.doctor_report(check_names=["command.bd"])
    assert report["status"] == expected
    assert report["checks"][0]["evidence"]["version"] == version
