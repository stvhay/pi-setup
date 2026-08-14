from __future__ import annotations

import sys
from pathlib import Path

from conftest import run_node

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


class FakeAnnotationClient(langfuse.LangfuseClient):
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def _request(self, method, path, body=None, params=None):
        self.calls.append((method, path, dict(params or {})))
        return self.responses.pop(0)


def test_annotation_service_port_uses_current_bounded_api_fields():
    queue = {
        "id": "queue-quality",
        "scoreConfigIds": ["config-quality"],
    }
    item = {
        "id": "item-1",
        "queueId": "queue-quality",
        "objectId": "trace-private",
        "objectType": "TRACE",
        "status": "COMPLETED",
    }
    score = {
        "id": "score-1",
        "source": "ANNOTATION",
        "queueId": "queue-quality",
        "authorUserId": "reviewer-private",
        "configId": "config-quality",
        "dataType": "NUMERIC",
        "value": 1,
        "subject": {"kind": "trace", "id": "trace-private"},
    }
    config = {"id": "config-quality", "dataType": "NUMERIC"}
    client = FakeAnnotationClient([
        queue,
        {"data": [item], "meta": {"totalItems": 1}},
        {"data": [score], "meta": {"cursor": None}},
        config,
    ])

    assert client.get_annotation_queue("queue-quality") == queue
    assert client.list_annotation_queue_items("queue-quality", limit=2) == {
        "items": [item],
        "complete": True,
    }
    assert client.list_annotation_scores("queue-quality", limit=2) == {
        "scores": [score],
        "complete": True,
    }
    assert client.get_score_config("config-quality") == config
    assert client.calls == [
        ("GET", "/api/public/annotation-queues/queue-quality", {}),
        ("GET", "/api/public/annotation-queues/queue-quality/items", {
            "limit": 3,
            "page": 1,
        }),
        ("GET", "/api/public/v3/scores", {
            "fields": "details,subject,annotation",
            "queueId": "queue-quality",
            "source": "ANNOTATION",
            "limit": 3,
        }),
        ("GET", "/api/public/score-configs/config-quality", {}),
    ]


def test_annotation_item_port_rejects_total_below_returned_rows_as_incomplete():
    item = {
        "id": "item-1",
        "queueId": "queue-quality",
        "objectId": "trace-private",
        "objectType": "TRACE",
        "status": "COMPLETED",
    }
    client = FakeAnnotationClient([{
        "data": [item],
        "meta": {"totalItems": 0},
    }])

    assert client.list_annotation_queue_items("queue-quality", limit=2) == {
        "items": [item],
        "complete": False,
    }


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
    quality = next(item for item in manifest["evaluators"] if item["name"] == "Subagent output quality")["prompt"]
    for contract in ("inline", "artifact", "status-only", "pass-no-findings", "unknown"):
        assert contract in quality
    assert "status-only" in quality and "must not be penalized" in quality
    assert "PASS/no-findings" in quality
    assert "required output is unavailable" in quality
    assert "artifactContentStatus" in quality


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


def test_langfuse_wrapper_loads_without_optional_package(tmp_path):
    agent_dir = tmp_path / "agent"
    npm_dir = agent_dir / "npm"
    npm_dir.mkdir(parents=True)
    (npm_dir / "package.json").write_text('{"private":true}\n', encoding="utf-8")
    script = f"""
      import assert from "node:assert/strict";
      import install from {STARTUP_EXTENSION.as_uri()!r};

      const handlers = {{}};
      const errors = [];
      const originalError = console.error;
      console.error = (...args) => errors.push(args.join(" "));
      try {{
        await install({{
          on(name, candidate) {{ handlers[name] = candidate; }},
          events: {{ on() {{}} }},
        }});
        assert.equal(typeof handlers.message_end, "function");
        assert.deepEqual(errors, ["[langfuse-projection] pi-langfuse package is unavailable"]);
      }} finally {{
        console.error = originalError;
      }}
    """
    run_node(script, {"PI_CODING_AGENT_DIR": str(agent_dir)})


def test_setup_applies_and_startup_checks_evaluators():
    setup = UPDATE_SCRIPT.read_text(encoding="utf-8")
    extension = STARTUP_EXTENSION.read_text(encoding="utf-8")

    assert '"$DEST/agent/bin/agnt" langfuse apply' in setup
    assert 'pi?.on("session_start"' in extension
    assert 'resolve(agentDir, "bin", "agnt")' in extension
    assert 'langfuse", "check", "--quiet"' in extension
    assert 'pi.exec("agnt"' not in extension
    assert "Langfuse evaluator configuration is outdated" in extension
