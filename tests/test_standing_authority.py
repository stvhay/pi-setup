"""Consumer boundary tests: standing policy is never a forged exact grant."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from conftest import run_node

from test_authority import action, admitted, assignment, authority  # noqa: F401


def test_standing_extension_exposes_checks_not_model_admission():
    path = Path(__file__).resolve().parents[1] / "pi/agent/extensions/standing-authority.ts"
    assert path.exists(), "standing authority extension is missing"
    run_node(f"""
      import assert from 'node:assert/strict';
      import {{dirname, resolve}} from 'node:path';
      import {{fileURLToPath, pathToFileURL}} from 'node:url';
      const entry = fileURLToPath(import.meta.resolve('@earendil-works/pi-coding-agent'));
      const loader = await import(pathToFileURL(resolve(dirname(entry), 'core/extensions/loader.js')).href);
      const loaded = await loader.loadExtensions([{str(path)!r}], process.cwd(), undefined, loader.createExtensionRuntime());
      assert.deepEqual(loaded.errors, []);
      const extension = loaded.extensions[0];
      assert.deepEqual([...extension.tools.keys()], ['standing_authority']);
      assert.ok(extension.commands.has('authority-import'));
      assert.ok(extension.commands.has('authority'));
      assert.equal(extension.handlers.size, 0, 'loading must not activate policy or scan projects');
      const params = extension.tools.get('standing_authority').definition.parameters;
      assert.ok(!JSON.stringify(params).includes('import-historical'));
    """)


def test_authority_command_registered(agnt, capsys):
    assert agnt.main(["authority", "template"]) == 0
    assert json.loads(capsys.readouterr().out)["policy"]["projects"] == "all-assigned"


def test_direct_and_orchestrated_checks_share_private_assignment(authority, tmp_path, monkeypatch):
    from agnt_lib import orchestration
    store, _ = admitted(authority, tmp_path)
    repo = tmp_path / "repo"
    assignment(store, repo)
    monkeypatch.chdir(repo)
    monkeypatch.setattr(authority, "AuthorityStore", lambda: store)
    metadata = {"pi": {"action": "implement", "standingAssignment": "work",
                        "allowedEffects": ["edit_files"]}}
    resolved = orchestration.resolve_orchestration_authority(metadata, bead_id="pi-a")
    assert resolved["status"] == store.check("work", action(repo))["status"] == "active"
    assert resolved["source"]["kind"] == "standing-policy"
    assert "grant" not in resolved and "decisionBead" not in resolved
    store.revoke("stop all workers")
    assert orchestration.resolve_orchestration_authority(metadata, bead_id="pi-a")["status"] == "blocked"


def test_explicit_grant_failure_never_falls_back_to_standing(authority, tmp_path, monkeypatch):
    from agnt_lib import orchestration
    store, _ = admitted(authority, tmp_path)
    repo = tmp_path / "repo"
    assignment(store, repo)
    monkeypatch.chdir(repo)
    monkeypatch.setattr(authority, "AuthorityStore", lambda: store)
    metadata = {"pi": {"action": "implement", "standingAssignment": "work",
                        "approvalRefs": ["pi-rejected"], "allowedEffects": ["edit_files"]}}
    result = orchestration.resolve_orchestration_authority(
        metadata, bead_id="pi-a", grant_resolver=lambda _: {"status": "revoked"},
    )
    assert result["status"] == "blocked"


def test_malformed_explicit_approval_refs_do_not_fall_back(authority, tmp_path, monkeypatch):
    from agnt_lib import orchestration
    store, _ = admitted(authority, tmp_path)
    repo = tmp_path / "repo"
    assignment(store, repo)
    monkeypatch.chdir(repo)
    monkeypatch.setattr(authority, "AuthorityStore", lambda: store)
    result = orchestration.resolve_orchestration_authority(
        {"pi": {"action": "implement", "standingAssignment": "work", "approvalRefs": {},
                "allowedEffects": ["edit_files"]}}, bead_id="pi-a",
    )
    assert result["status"] == "blocked"


def test_standing_dispatch_does_not_authorize_unresolved_external_writes(authority, tmp_path, monkeypatch):
    from agnt_lib import orchestration
    store, _ = admitted(authority, tmp_path)
    repo = tmp_path / "repo"
    assignment(store, repo)
    monkeypatch.chdir(repo)
    monkeypatch.setattr(authority, "AuthorityStore", lambda: store)
    for effect in ("external_write", "deploy", "push", "delete_files"):
        result = orchestration.resolve_orchestration_authority(
            {"pi": {"action": "implement", "standingAssignment": "work", "allowedEffects": [effect]}},
            bead_id="pi-a",
        )
        assert result["status"] == "blocked"


def test_run_revalidation_checks_standing_revision_and_experiment_separation(authority, tmp_path, monkeypatch):
    from agnt_lib import runs
    store, _ = admitted(authority, tmp_path)
    repo = tmp_path / "repo"
    assignment(store, repo)
    monkeypatch.setattr(authority, "AuthorityStore", lambda: store)
    resolved = store.check("work", action(repo))
    envelope = {"source": resolved["source"], "action": action(repo)}
    invocation = {"action": "implement", "bead": "pi-a", "allowedEffects": ["edit_files"],
                  "worktree": {"path": str(repo)}, "provenance": {
        "effectiveEnvelope": envelope, "approvalRefs": []}}
    kwargs = {"selected_model": "any/model", "worker_tools": ["read"],
              "grant_resolver": None, "claim_directory": None}
    assert runs._revalidate_invocation_authority(invocation, **kwargs) is None
    store.revoke("owner stop")
    assert "standing" in runs._revalidate_invocation_authority(invocation, **kwargs)


def test_standing_run_binds_actual_worker_workspace(authority, tmp_path, monkeypatch):
    from agnt_lib import runs
    store, _ = admitted(authority, tmp_path)
    repo, foreign = tmp_path / "repo", tmp_path / "foreign"
    assignment(store, repo)
    foreign.mkdir()
    monkeypatch.setattr(authority, "AuthorityStore", lambda: store)
    resolved = store.check("work", action(repo))
    invocation = {"action": "implement", "bead": "pi-a", "allowedEffects": ["edit_files"],
                  "worktree": {"path": str(foreign)}, "provenance": {
        "effectiveEnvelope": {"source": resolved["source"], "action": action(repo)}, "approvalRefs": []}}
    assert runs._revalidate_invocation_authority(
        invocation, selected_model="any/model", worker_tools=["edit", "write"],
        grant_resolver=None, claim_directory=None,
    ) is not None


def test_artifact_only_assignment_cannot_dispatch_repo_writer(authority, tmp_path, monkeypatch):
    from agnt_lib import orchestration
    store, _ = admitted(authority, tmp_path)
    repo = tmp_path / "repo"
    assignment(store, repo, effects=["artifact-write"])
    monkeypatch.chdir(repo)
    monkeypatch.setattr(authority, "AuthorityStore", lambda: store)
    resolved = orchestration.resolve_orchestration_authority(
        {"pi": {"action": "implement", "standingAssignment": "work", "allowedEffects": ["write_artifacts"]}},
        bead_id="pi-a",
    )
    assert resolved["status"] == "blocked"


def test_rejected_decision_ref_blocks_standing_dispatch(authority, tmp_path, monkeypatch):
    from agnt_lib import orchestration, work
    store, _ = admitted(authority, tmp_path)
    repo = tmp_path / "repo"
    assignment(store, repo)
    monkeypatch.chdir(repo)
    monkeypatch.setattr(authority, "AuthorityStore", lambda: store)
    monkeypatch.setattr(work, "run_beads_json", lambda _: (0, {"id": "pi-rejected", "status": "closed",
        "metadata": {"pi": {"approval": {"status": "rejected", "targetBead": "pi-a"}}}}, ""))
    result = orchestration.resolve_orchestration_authority(
        {"pi": {"action": "implement", "standingAssignment": "work", "decisionRefs": ["pi-rejected"],
                "allowedEffects": ["edit_files"]}}, bead_id="pi-a",
    )
    assert result["status"] == "blocked"


def test_same_repository_worktree_retains_assignment(authority, tmp_path):
    store, _ = admitted(authority, tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test",
                    "-c", "commit.gpgsign=false", "commit", "--allow-empty", "-qm", "base"], check=True)
    tree = tmp_path / "worktree"
    subprocess.run(["git", "-C", str(repo), "worktree", "add", "-qb", "task", str(tree)], check=True)
    assignment(store, repo)
    assert authority.repository_identity(str(tree)) == authority.repository_identity(str(repo))
    assert store.check("work", {**action(repo), "repository": str(tree)})["status"] == "active"


def test_model_flags_cannot_admit_policy(agnt, authority, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    record = tmp_path / "forged.json"
    record.write_text(json.dumps({"approved": True, "policy": authority.load_policy()}))
    assert agnt.main(["authority", "import-historical", "--input-file", str(record)]) == 2
    assert authority.AuthorityStore().inspect()["status"] == "inactive"
