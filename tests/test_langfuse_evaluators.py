from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pi" / "agent" / "bin"))

from agnt_lib import langfuse


MANIFEST = ROOT / "pi" / "agent" / "langfuse" / "evaluators.json"
UPDATE_SCRIPT = ROOT / "scripts" / "update-pi-config.sh"
STARTUP_EXTENSION = ROOT / "pi" / "agent" / "extensions" / "langfuse-config-env.ts"


class FakeClient:
    def __init__(self, evaluators=(), rules=()):
        self.evaluators = list(evaluators)
        self.rules = list(rules)
        self.created_evaluators = []
        self.created_rules = []
        self.updated_rules = []

    def list_evaluators(self):
        return self.evaluators

    def list_rules(self):
        return self.rules

    def create_evaluator(self, body):
        self.created_evaluators.append(body)
        return {"id": "new-evaluator", **body}

    def create_rule(self, body):
        self.created_rules.append(body)
        return {"id": "new-rule", **body}

    def update_rule(self, rule_id, body):
        self.updated_rules.append((rule_id, body))
        return {"id": rule_id, **body}


def test_manifest_contains_default_evaluators():
    manifest = langfuse.load_manifest(MANIFEST)
    assert {item["name"] for item in manifest["evaluators"]} == {
        "Apparent task outcome",
        "Subagent output quality",
    }
    rules = {rule["name"]: rule for rule in manifest["rules"]}
    outcome = rules["Apparent task outcome — root Pi agents (10%)"]
    subagent = rules["Subagent output quality — calibration (100%)"]
    assert outcome["sampling"] == 0.1
    assert subagent["sampling"] == 1
    assert next(item for item in outcome["filter"] if item["column"] == "name")["value"] == ["interactive-result"]
    assert not any(item.get("column") == "sessionId" for item in outcome["filter"])
    assert next(item for item in subagent["filter"] if item["column"] == "name")["value"] == ["subagent-result"]
    assert not any(item.get("column") in {"sessionId", "metadata"} for item in subagent["filter"])


def test_check_is_silent_when_remote_matches(capsys):
    manifest = langfuse.load_manifest(MANIFEST)
    evaluators = [{**item, "id": f"evaluator-{index}"} for index, item in enumerate(manifest["evaluators"])]
    rules = [
        {**item, "id": f"rule-{index}", "evaluator": {**item["evaluator"], "id": f"evaluator-{index}", "type": "llm_as_judge"}}
        for index, item in enumerate(manifest["rules"])
    ]
    client = FakeClient(evaluators, rules)

    assert langfuse.run_sync(manifest, client, apply=False, quiet=True) == 0
    assert capsys.readouterr().out == ""


def test_check_reports_drift_without_mutating(capsys):
    manifest = langfuse.load_manifest(MANIFEST)
    client = FakeClient()

    assert langfuse.run_sync(manifest, client, apply=False, quiet=False) == 1
    output = capsys.readouterr().out
    assert "missing evaluator: Apparent task outcome" in output
    assert "missing rule: Subagent output quality — calibration (100%)" in output
    assert not client.created_evaluators
    assert not client.created_rules


def test_apply_creates_missing_and_updates_drifted_rules():
    manifest = langfuse.load_manifest(MANIFEST)
    existing_rule = {**manifest["rules"][0], "id": "rule-1", "sampling": 1}
    client = FakeClient(rules=[existing_rule])

    assert langfuse.run_sync(manifest, client, apply=True, quiet=True) == 0
    assert len(client.created_evaluators) == len(manifest["evaluators"])
    assert len(client.created_rules) == len(manifest["rules"]) - 1
    assert client.updated_rules == [("rule-1", manifest["rules"][0])]


def test_setup_applies_and_startup_checks_evaluators():
    setup = UPDATE_SCRIPT.read_text(encoding="utf-8")
    extension = STARTUP_EXTENSION.read_text(encoding="utf-8")

    assert '"$DEST/agent/bin/agnt" langfuse apply' in setup
    assert 'pi?.on("session_start"' in extension
    assert 'resolve(agentDir, "bin", "agnt")' in extension
    assert 'langfuse", "check", "--quiet"' in extension
    assert 'pi.exec("agnt"' not in extension
    assert "Langfuse evaluator configuration is outdated" in extension
