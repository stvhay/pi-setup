from __future__ import annotations

import importlib.util
import json
import re
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / "pi/agent/evals/review-routing-calibration"
MODULE_PATH = EVAL_DIR / "evaluate.py"


def load_module():
    spec = importlib.util.spec_from_file_location("review_routing_calibration", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def manifest() -> dict:
    return json.loads((EVAL_DIR / "manifest.json").read_text(encoding="utf-8"))


def expected_ids(packet: dict) -> list[str]:
    return list(packet["expectedFindings"])


SEMANTIC_TEXT = {
    "A1": "UTF-8 byte size differs from character length for multibyte input.",
    "A2": "Retry attempts regenerate the envelope ID instead of preserving it.",
    "B1": "Backup removal before patch validation prevents rollback.",
    "B2": "Marker-only detection accepts a partial patch state.",
}


def finding(packet: dict, finding_id: str, *, semantic: bool = True) -> dict:
    text = SEMANTIC_TEXT.get(finding_id, "Unexpected anchored claim.") if semantic else "Generic invariant issue."
    return {
        "id": finding_id,
        "severity": "important",
        "category": "correctness",
        "location": f"example.py:{finding_id}",
        "claim": text,
        "failureScenario": text,
        "evidence": text,
        "status": "unverified",
    }


def output(packet: dict, finding_ids: list[str], *, semantic: bool = True) -> str:
    return json.dumps({
        "schemaVersion": 1,
        "reviewId": packet["id"],
        "scope": packet["scope"],
        "reviewer": {"target": "calibration-candidate", "family": "codex"},
        "findings": [finding(packet, finding_id, semantic=semantic) for finding_id in finding_ids],
    })


def task(packet_id: str, repetition: int) -> str:
    spec = manifest()
    packet = next(item for item in spec["packets"] if item["id"] == packet_id)
    prompt = (EVAL_DIR / packet["prompt"]).read_text(encoding="utf-8").strip()
    prefix = packet.get("taskPrefix", spec["taskPrefix"])
    return f"{prefix} packet={packet_id} repetition={repetition}\n\n{prompt}"


def session_entry(message: dict) -> str:
    return json.dumps({"type": "message", "id": "entry", "message": message})


def packet_namespace(filename: str) -> dict:
    text = (EVAL_DIR / "packets" / filename).read_text(encoding="utf-8")
    match = re.search(r"```python\n(.*?)\n```", text, flags=re.DOTALL)
    assert match
    namespace: dict = {}
    exec(compile(match.group(1), filename, "exec"), namespace)
    return namespace


def test_real_manifest_and_packets_validate():
    module = load_module()

    checked = module.validate_manifest(manifest(), EVAL_DIR)

    assert checked["id"] == "review-routing-calibration"
    assert checked["taskPrefix"] == "review-calibration:v3"
    assert len(checked["packets"]) == 4
    deployment = {packet["id"]: packet["taskPrefix"] for packet in checked["packets"] if packet["scope"] == "boundary"}
    assert deployment == {"case-02a": "review-calibration:v6", "case-02b": "review-calibration:v6"}
    assert {packet["kind"] for packet in checked["packets"]} == {"seeded", "clean"}
    assert checked["execution"]["repetitions"] == 3
    assert checked["thresholds"]["minLatencyAdjustedYieldRatio"] == 1.25
    for packet in checked["packets"]:
        for rubric in packet["expectedFindings"].values():
            assert len(rubric["semanticAlternatives"]) >= 2


@pytest.mark.parametrize(("packet_index", "finding_id", "claim"), [
    (0, "A1", "Character-counting underestimates wire length for multibyte payloads."),
    (0, "A2", "A retry after 503 can create a duplicate score; the operation is non-idempotent."),
    (2, "B1", "Failure after backup deletion cannot recover the previous package."),
    (2, "B2", "The marker can exist while a required hunk is missing."),
])
def test_semantic_rubric_accepts_specific_paraphrases(packet_index, finding_id, claim):
    module = load_module()
    packet = manifest()["packets"][packet_index]
    paraphrase = finding(packet, finding_id, semantic=False)
    paraphrase["claim"] = claim

    assert module.verify_finding(paraphrase, packet)["status"] == "confirmed"


def test_ingestion_packets_have_only_the_declared_seeded_defects():
    seeded = packet_namespace("ingestion-seeded.md")
    clean = packet_namespace("ingestion-clean.md")
    first = {"id": "1", "body": "🙂" * 400_000}
    second = {"id": "2", "body": "🙂" * 400_000}
    later = {"id": "later", "body": "ok"}
    oversized = {"id": "big", "body": "🙂" * 800_000}

    assert seeded["serialized_size"]([first, second]) < seeded["MAX_BODY_BYTES"]
    assert len(json.dumps({"batch": [first, second]}, ensure_ascii=False).encode("utf-8")) > seeded["MAX_BODY_BYTES"]
    assert [event["id"] for batch in seeded["partition"]([oversized, later]) for event in batch] == ["later"]
    assert all(clean["serialized_size"](batch) <= clean["MAX_BODY_BYTES"] for batch in clean["partition"]([first, second]))

    class Post:
        def __init__(self):
            self.bodies = []

        def __call__(self, body):
            self.bodies.append(json.loads(body))
            return SimpleNamespace(status=503 if len(self.bodies) == 1 else 200)

    seeded_post = Post()
    clean_post = Post()
    seeded["send_score"](seeded_post, {"value": 1})
    clean["send_score"](clean_post, {"value": 1})
    assert seeded_post.bodies[0]["batch"][0]["id"] != seeded_post.bodies[1]["batch"][0]["id"]
    assert clean_post.bodies[0]["batch"][0]["id"] == clean_post.bodies[1]["batch"][0]["id"]
    with pytest.raises(ValueError, match="3,000,000"):
        seeded["send_score"](Post(), {"value": "🙂" * 800_000})
    with pytest.raises(ValueError, match="3,000,000"):
        clean["send_score"](Post(), {"value": "🙂" * 800_000})


def test_deployment_packets_have_only_the_declared_seeded_defects(tmp_path, monkeypatch):
    seeded_text = (EVAL_DIR / "packets/deployment-seeded.md").read_text(encoding="utf-8")
    clean_text = (EVAL_DIR / "packets/deployment-clean.md").read_text(encoding="utf-8")
    assert seeded_text.count("runtime.find(\"CURRENT_PATCH_MARKER\")") == 1
    assert "runtime == APPLIED_RUNTIME" in clean_text
    assert "runtime == CLEAN_RUNTIME" in clean_text
    seeded = packet_namespace("deployment-seeded.md")
    clean = packet_namespace("deployment-clean.md")
    patch_file = tmp_path / "runtime.patch"
    patch_file.write_text(
        "--- a/runtime.py\n+++ b/runtime.py\n@@ -1,3 +1,3 @@\n CONTEXT\n-OLD\n+CURRENT_PATCH_MARKER\n TAIL\n",
        encoding="utf-8",
    )

    clean_package = tmp_path / "clean"
    clean_package.mkdir()
    (clean_package / "package.json").write_text("{}\n", encoding="utf-8")
    (clean_package / "runtime.py").write_text("CONTEXT\nOLD\nTAIL\n", encoding="utf-8")
    assert clean["patch_state"](clean_package, patch_file) == "pending"
    subprocess.run(["patch", "--force", "--fuzz=0", "-p1"], cwd=clean_package,
                   input=patch_file.read_bytes(), check=True, capture_output=True)
    assert clean["patch_state"](clean_package, patch_file) == "applied"
    (clean_package / "runtime.py").write_text("MIXED CURRENT_PATCH_MARKER\n", encoding="utf-8")
    assert clean["patch_state"](clean_package, patch_file) == "invalid"
    assert seeded["patch_state"](clean_package, patch_file) == "applied"
    incomplete = tmp_path / "incomplete"
    incomplete.mkdir()
    (incomplete / "package.json").write_text("{}\n", encoding="utf-8")
    assert clean["patch_state"](incomplete, patch_file) == "invalid"
    assert seeded["patch_state"](incomplete, patch_file) == "invalid"
    with pytest.raises(RuntimeError, match="incomplete package"):
        clean["validate"](incomplete)
    invalid_runtime = tmp_path / "invalid-runtime"
    invalid_runtime.mkdir()
    (invalid_runtime / "package.json").write_text("{}\n", encoding="utf-8")
    (invalid_runtime / "runtime.py").write_text(clean["CLEAN_RUNTIME"], encoding="utf-8")
    with pytest.raises(RuntimeError, match="runtime is not fully patched"):
        clean["validate"](invalid_runtime)

    cleanup_root = tmp_path / "cleanup"
    cleanup_package = cleanup_root / "package"
    cleanup_backup = cleanup_root / "backup"
    cleanup_package.mkdir(parents=True)
    (cleanup_package / "package.json").write_text("{}\n", encoding="utf-8")
    (cleanup_package / "runtime.py").write_text("OLD\n", encoding="utf-8")

    def install_new(path):
        path.mkdir()
        (path / "package.json").write_text("{}\n", encoding="utf-8")
        (path / "runtime.py").write_text("NEW\n", encoding="utf-8")

    original_rmtree = clean["shutil"].rmtree

    def partial_cleanup(path, *args, **kwargs):
        if Path(path) == cleanup_backup:
            (cleanup_backup / "runtime.py").unlink()
            raise OSError("partial backup cleanup")
        return original_rmtree(path, *args, **kwargs)

    def apply_exact(path):
        (path / "runtime.py").write_text(clean["APPLIED_RUNTIME"], encoding="utf-8")

    monkeypatch.setattr(clean["shutil"], "rmtree", partial_cleanup)
    clean["deploy"](cleanup_package, cleanup_backup, install_new, apply_exact, clean["validate"])
    assert (cleanup_package / "runtime.py").read_text(encoding="utf-8") == clean["APPLIED_RUNTIME"]
    with pytest.raises(RuntimeError, match="stale backup"):
        clean["deploy"](cleanup_package, cleanup_backup, install_new, lambda _path: None, clean["validate"])
    assert (cleanup_package / "runtime.py").read_text(encoding="utf-8") == clean["APPLIED_RUNTIME"]

    def exercise_deploy(namespace, root):
        package = root / "package"
        backup = root / "backup"
        package.mkdir(parents=True)
        (package / "package.json").write_text("{}\n", encoding="utf-8")
        (package / "runtime.py").write_text("OLD\n", encoding="utf-8")

        def install(path):
            path.mkdir()
            (path / "package.json").write_text("{}\n", encoding="utf-8")
            (path / "runtime.py").write_text("NEW\n", encoding="utf-8")

        def fail_patch(_path):
            raise RuntimeError("patch failed")

        with pytest.raises(RuntimeError, match="patch failed"):
            namespace["deploy"](package, backup, install, fail_patch, namespace["validate"])
        return package

    assert not exercise_deploy(seeded, tmp_path / "seeded").exists()
    restored = exercise_deploy(clean, tmp_path / "control")
    assert (restored / "runtime.py").read_text(encoding="utf-8") == "OLD\n"


@pytest.mark.parametrize(("stale_prefix", "packet_id"), [
    ("review-calibration:v1", "case-01a"),
    ("review-calibration:v2", "case-01a"),
    ("review-calibration:v3", "case-02a"),
    ("review-calibration:v3", "case-02b"),
    ("review-calibration:v4", "case-02b"),
    ("review-calibration:v5", "case-02b"),
])
def test_collect_ignores_stale_trial_prefixes(tmp_path, stale_prefix, packet_id):
    module = load_module()
    session = tmp_path / "session.jsonl"
    session.write_text(session_entry({
        "role": "assistant",
        "content": [{
            "type": "toolCall",
            "id": "stale-call",
            "name": "subagent",
            "arguments": {"tasks": [{"task": f"{stale_prefix} packet={packet_id} repetition=1"}]},
        }],
    }), encoding="utf-8")

    assert module.collect_records(session, manifest()) == []


def test_collect_ignores_orphan_assistant_intent_without_tool_result(tmp_path):
    module = load_module()
    spec = manifest()
    packet = spec["packets"][0]
    session = tmp_path / "session.jsonl"
    session.write_text(session_entry({
        "role": "assistant",
        "content": [{
            "type": "toolCall",
            "id": "orphan-call",
            "name": "subagent",
            "arguments": {"tasks": [{
                "task": task(packet["id"], 1),
                "model": spec["models"][0]["target"],
                "mode": "one-shot",
                "thinking": "high",
                "limits": {"maxProviderRequests": 1, "maxDurationMs": 180_000},
                "outputContract": "inline",
            }]},
        }],
    }), encoding="utf-8")

    assert module.collect_records(session, spec) == []


def test_collect_correlates_subagent_call_and_result_dimensions(tmp_path):
    module = load_module()
    spec = manifest()
    packet = spec["packets"][0]
    targets = [model["target"] for model in spec["models"]]
    call_id = "tool-call-1"
    tasks = [{
        "task": task(packet["id"], 1),
        "model": target,
        "mode": "one-shot",
        "thinking": "high",
        "limits": {"maxProviderRequests": 1, "maxDurationMs": 180_000},
        "outputContract": "inline",
    } for target in targets]
    results = [{
        "task": task(packet["id"], 1),
        "provider": target.split("/", 1)[0],
        "model": target.split("/", 1)[1],
        "execution": {
            "profile": {"mode": "one-shot", "thinking": "high"},
            "limits": {"maxProviderRequests": 1, "maxDurationMs": 180_000},
        },
        "exitCode": 0,
        "finalOutput": output(packet, expected_ids(packet)),
        "usage": {"turns": 1},
        "termination": {"reason": "completed", "usageState": "complete"},
        "progressSummary": {"durationMs": 1_000, "tokens": 100},
        "childSessionId": f"child-{index}",
    } for index, target in enumerate(targets)]
    session = tmp_path / "session.jsonl"
    session.write_text("\n".join([
        session_entry({
            "role": "assistant",
            "content": [{"type": "toolCall", "id": call_id, "name": "subagent", "arguments": {"tasks": tasks}}],
        }),
        session_entry({
            "role": "toolResult",
            "toolCallId": call_id,
            "toolName": "subagent",
            "content": [{"type": "text", "text": "done"}],
            "details": {"mode": "parallel", "results": results},
        }),
    ]) + "\n", encoding="utf-8")

    records = module.collect_records(session, spec)

    assert len(records) == 2
    assert {record["target"] for record in records} == set(targets)
    assert all(record["dimensionsValid"] for record in records)
    assert all(record["thinking"] == "high" for record in records)
    assert all(record["mode"] == "one-shot" for record in records)
    assert all(record["observedProvider"] == "openai-codex" for record in records)
    assert all(record["effectiveThinking"] == "high" for record in records)
    assert all(record["effectiveMode"] == "one-shot" for record in records)
    assert all(record["providerRequests"] == 1 for record in records)
    assert all(record["durationMs"] == 1_000 for record in records)
    assert all(record["responseChars"] <= 6_000 for record in records)

    tasks[0]["task"] = f"review-calibration:v3 packet={packet['id']} repetition=1\n\nwrong packet"
    results[0]["task"] = tasks[0]["task"]
    session.write_text("\n".join([
        session_entry({
            "role": "assistant",
            "content": [{"type": "toolCall", "id": call_id, "name": "subagent", "arguments": {"tasks": tasks}}],
        }),
        session_entry({
            "role": "toolResult",
            "toolCallId": call_id,
            "toolName": "subagent",
            "details": {"results": results},
        }),
    ]), encoding="utf-8")
    drifted = module.collect_records(session, spec)
    terra = next(record for record in drifted if record["target"].endswith("terra"))
    assert "taskPayload" in terra["dimensionErrors"]


def test_collect_correlates_reordered_results_by_task_and_model(tmp_path):
    module = load_module()
    spec = manifest()
    packet = spec["packets"][0]
    targets = [model["target"] for model in spec["models"]]
    call_id = "tool-call-reordered"
    tasks = [{
        "task": task(packet["id"], 1),
        "model": target,
        "mode": "one-shot",
        "thinking": "high",
        "limits": {"maxProviderRequests": 1, "maxDurationMs": 180_000},
        "outputContract": "inline",
    } for target in targets]
    results = [{
        "task": task(packet["id"], 1),
        "provider": target.split("/", 1)[0],
        "model": target.split("/", 1)[1],
        "execution": {"profile": {"mode": "one-shot", "thinking": "high"},
                      "limits": {"maxProviderRequests": 1, "maxDurationMs": 180_000}},
        "exitCode": 0,
        "finalOutput": output(packet, expected_ids(packet)),
        "usage": {"turns": 1},
        "termination": {"reason": "completed", "usageState": "complete"},
        "progressSummary": {"durationMs": 1_000},
    } for target in reversed(targets)]
    session = tmp_path / "session.jsonl"
    session.write_text("\n".join([
        session_entry({"role": "assistant", "content": [{"type": "toolCall", "id": call_id,
                       "name": "subagent", "arguments": {"tasks": tasks}}]}),
        session_entry({"role": "toolResult", "toolCallId": call_id, "toolName": "subagent",
                       "details": {"mode": "parallel", "results": results}}),
    ]) + "\n", encoding="utf-8")

    records = module.collect_records(session, spec)

    assert [record["observedModel"] for record in records] == [
        record["target"].split("/", 1)[1] for record in records
    ]
    assert all(record["dimensionsValid"] for record in records)


def test_collect_rejects_unmatched_or_unbounded_dimensions(tmp_path):
    module = load_module()
    spec = manifest()
    packet = spec["packets"][0]
    target = spec["models"][0]["target"]
    call_id = "tool-call-bad"
    session = tmp_path / "session.jsonl"
    session.write_text("\n".join([
        session_entry({
            "role": "assistant",
            "content": [{
                "type": "toolCall",
                "id": call_id,
                "name": "subagent",
                "arguments": {"tasks": [{
                    "task": task(packet["id"], 1),
                    "model": target,
                    "mode": "agentic",
                    "thinking": "low",
                    "limits": {"maxProviderRequests": 2, "maxDurationMs": 90_000, "maxTotalTokens": 1_000},
                    "outputContract": "artifact",
                }]},
            }],
        }),
        session_entry({
            "role": "toolResult",
            "toolCallId": call_id,
            "toolName": "subagent",
            "details": {"mode": "parallel", "results": [{
                "model": "wrong-model",
                "exitCode": 0,
                "finalOutput": output(packet, []),
                "usage": {"turns": 2},
                "termination": {"reason": "completed", "usageState": "complete"},
                "progressSummary": {"durationMs": 1_000},
            }]},
        }),
    ]) + "\n", encoding="utf-8")

    records = module.collect_records(session, spec)

    assert len(records) == 1
    assert records[0]["dimensionsValid"] is False
    assert set(records[0]["dimensionErrors"]) >= {
        "mode",
        "thinking",
        "maxProviderRequests",
        "maxDurationMs",
        "tokenOrCostLimit",
        "outputContract",
        "observedProvider",
        "observedModel",
        "effectiveMode",
        "effectiveThinking",
        "effectiveLimits",
        "providerRequests",
        "durationMs",
    }


def synthetic_records(spec: dict, *, luna_misses: set[tuple[str, int, str]] | None = None) -> list[dict]:
    misses = luna_misses or set()
    records = []
    for packet in spec["packets"]:
        for repetition in range(1, spec["execution"]["repetitions"] + 1):
            for model in spec["models"]:
                target = model["target"]
                ids = [
                    finding_id for finding_id in expected_ids(packet)
                    if (packet["id"], repetition, finding_id) not in misses or not target.endswith("luna")
                ]
                records.append({
                    "packetId": packet["id"],
                    "repetition": repetition,
                    "toolCallId": f"wave-{packet['id']}-{repetition}",
                    "taskHash": f"hash-{packet['id']}-{repetition}",
                    "target": target,
                    "requestedModel": target,
                    "observedProvider": target.split("/", 1)[0],
                    "observedModel": target.split("/", 1)[1],
                    "mode": "one-shot",
                    "thinking": "high",
                    "effectiveMode": "one-shot",
                    "effectiveThinking": "high",
                    "effectiveLimits": {"maxProviderRequests": 1, "maxDurationMs": 180_000},
                    "maxProviderRequests": 1,
                    "maxDurationMs": 180_000,
                    "hasTokenOrCostLimit": False,
                    "outputContract": "inline",
                    "providerRequests": 1,
                    "durationMs": 20_000 if target.endswith("terra") else 10_000,
                    "exitCode": 0,
                    "terminationReason": "completed",
                    "response": output(packet, ids),
                    "responseChars": len(output(packet, ids)),
                    "childSessionId": f"{packet['id']}-{repetition}-{target}",
                    "dimensionsValid": True,
                    "dimensionErrors": [],
                })
    return records


def test_score_promotes_only_when_quality_and_yield_thresholds_pass():
    module = load_module()
    spec = manifest()

    summary = module.score_records(synthetic_records(spec), spec)

    terra = summary["models"]["openai-codex/gpt-5.6-terra"]
    luna = summary["models"]["openai-codex/gpt-5.6-luna"]
    assert terra["confirmedUniqueFindings"] == 4
    assert terra["verifiedFindingOpportunities"] == 12
    assert terra["falsePositives"] == 0
    assert terra["recall"] == 1.0
    assert luna["latencyAdjustedYieldPerMinute"] == pytest.approx(2 * terra["latencyAdjustedYieldPerMinute"])
    assert summary["decision"]["promoteLunaForBoundedReview"] is True
    assert summary["decision"]["highRiskRoutingChanged"] is False


@pytest.mark.parametrize("breakage", [
    "missing", "duplicate", "separate-wave", "task-mismatch", "invalid-dimension", "missing-duration",
    "over-duration",
])
def test_score_requires_exact_dimension_valid_paired_waves(breakage):
    module = load_module()
    spec = manifest()
    records = synthetic_records(spec)
    luna_index = next(index for index, record in enumerate(records) if record["target"].endswith("luna"))
    if breakage == "missing":
        records.pop(luna_index)
    elif breakage == "duplicate":
        records.append(dict(records[luna_index]))
    elif breakage == "separate-wave":
        records[luna_index]["toolCallId"] = "different-wave"
    elif breakage == "task-mismatch":
        records[luna_index]["taskHash"] = "different-task"
    elif breakage == "invalid-dimension":
        records[luna_index]["dimensionsValid"] = False
        records[luna_index]["dimensionErrors"] = ["thinking"]
    elif breakage == "missing-duration":
        records[luna_index]["durationMs"] = None
    else:
        records[luna_index]["durationMs"] = 180_001

    summary = module.score_records(records, spec)

    assert summary["decision"]["promoteLunaForBoundedReview"] is False
    assert "pairedExecution" in summary["decision"]["failedGates"]


def test_score_keeps_terra_when_luna_recall_deficit_exceeds_gate():
    module = load_module()
    spec = manifest()
    misses = {(spec["packets"][0]["id"], 1, expected_ids(spec["packets"][0])[0])}

    summary = module.score_records(synthetic_records(spec, luna_misses=misses), spec)

    assert summary["models"]["openai-codex/gpt-5.6-luna"]["recall"] < 1.0
    assert summary["decision"]["promoteLunaForBoundedReview"] is False
    assert "recallDeficit" in summary["decision"]["failedGates"]


def test_score_counts_clean_findings_as_false_positives_and_invalid_output():
    module = load_module()
    spec = manifest()
    records = synthetic_records(spec)
    clean = next(packet for packet in spec["packets"] if packet["kind"] == "clean")
    record = next(item for item in records if item["packetId"] == clean["id"])
    record["response"] = output(clean, [clean["anchors"][0]])
    record["responseChars"] = len(record["response"])
    invalid = next(item for item in records if item["target"].endswith("luna") and item is not record)
    invalid["response"] = "not json"
    invalid["responseChars"] = len(invalid["response"])

    summary = module.score_records(records, spec)

    assert summary["models"][record["target"]]["falsePositives"] == 1
    assert summary["models"][invalid["target"]]["invalidOutputs"] == 1
    assert summary["verification"]["checks"] >= 1
    assert summary["verification"]["durationMs"] >= 0
    assert summary["verification"]["records"]


def test_score_requires_private_semantic_rubric_for_confirmed_seed():
    module = load_module()
    spec = manifest()
    records = synthetic_records(spec)
    seeded = next(packet for packet in spec["packets"] if packet["kind"] == "seeded")
    record = next(item for item in records if item["packetId"] == seeded["id"])
    finding_id = expected_ids(seeded)[0]
    record["response"] = output(seeded, [finding_id], semantic=False)
    record["responseChars"] = len(record["response"])

    summary = module.score_records(records, spec)
    verification = next(item for item in summary["verification"]["records"]
                        if item["packetId"] == seeded["id"] and item["findingId"] == finding_id
                        and item["target"] == record["target"] and item["repetition"] == record["repetition"])

    assert verification["status"] == "refuted"
    assert summary["models"][record["target"]]["falsePositives"] == 1


def test_private_outputs_use_restrictive_permissions(tmp_path):
    module = load_module()
    path = tmp_path / "private" / "runs.json"

    module.write_json(path, {"runs": []})

    assert path.stat().st_mode & 0o777 == 0o600
    assert path.parent.stat().st_mode & 0o777 == 0o700
