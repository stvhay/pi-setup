from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch


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


def test_doctor_redacts_provider_env_vars(agnt, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-secret-value")
    report = agnt.doctor_report(check_names=["provider.env"])
    encoded = json.dumps(report)

    assert "sk-or-secret-value" not in encoded
    check = report["checks"][0]
    assert check["id"] == "provider.env"
    assert check["evidence"]["OPENROUTER_API_KEY"] == "present:redacted"


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
