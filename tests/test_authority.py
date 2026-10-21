"""Owner-global authority, independent of quality experiment grants."""
from __future__ import annotations

import importlib
import json
import subprocess
from pathlib import Path

import pytest


def test_authority_service_available(agnt):
    assert importlib.util.find_spec("agnt_lib.authority"), "standing authority service is missing"


@pytest.fixture
def authority(agnt):
    return importlib.import_module("agnt_lib.authority")


def historical_record(policy):
    return {
        "kind": "historical-consent",
        "owner": "fixture-owner",
        "policy": policy,
        "consent": "Delegate full delivery for all assigned projects.",
        "evidenceRefs": ["fixture:original-consent", "fixture:historical-traceability-waiver"],
        "inputOrigin": "not-retained",
    }


def admitted(authority, tmp_path):
    store = authority.AuthorityStore(tmp_path / "owner")
    policy = authority.load_policy()
    store.admit_historical(historical_record(policy))
    return store, policy


def assignment(store, repo, *, name="work", effects=None, denied=()):
    repo.mkdir(exist_ok=True)
    return store.assign(
        name, repository=str(repo), beads=["pi-a", "pi-b"],
        effects=effects or ["read", "repo-write", "git-commit", "deploy-production"],
        denied_effects=list(denied), intent_ref="fixture:human-task",
    )


def action(repo, effect="repo-write"):
    return {"repository": str(repo.resolve()), "bead": "pi-a", "effects": [effect],
            "target": {"identity": "fixture:target", "repository": str(repo.resolve()),
                       "verified": True},
            "preconditions": {"identity": True, "platform": True, "effectClosure": True}}


def test_inv1_global_policy_applies_without_project_enrollment(authority, tmp_path):  # Tests INV-1
    store, _ = admitted(authority, tmp_path)
    for index in range(3):
        repo = tmp_path / f"unrelated-{index}"
        assignment(store, repo, name=f"task-{index}")
        decision = store.check(f"task-{index}", action(repo))
        assert decision["status"] == "active"
        assert decision["source"]["kind"] == "standing-policy"
        assert not list(repo.iterdir())
    assert authority.AuthorityStore(store.root).inspect()["status"] == "active"


@pytest.mark.parametrize("override", ["environment", "worktree-config", "ancestor-worktree-config"])
def test_git_context_cannot_alias_foreign_repository(authority, tmp_path, monkeypatch, override):
    store, _ = admitted(authority, tmp_path)
    owned = tmp_path / "owned"
    foreign = owned / "nested" if override == "ancestor-worktree-config" else tmp_path / "foreign"
    for repo in (owned, foreign):
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
    assignment(store, owned)
    original_identity = authority.repository_identity(str(owned))
    if override == "environment":
        monkeypatch.setenv("GIT_DIR", str(owned / ".git"))
        monkeypatch.setenv("GIT_WORK_TREE", str(owned))
    else:
        subprocess.run(["git", "-C", str(foreign), "config", "core.worktree", str(owned)], check=True)
    assert authority.repository_identity(str(owned)) == original_identity
    assert store.check("work", action(foreign))["status"] == "blocked"


def test_direct_scope_preserves_existing_assignment_identity(authority, tmp_path):  # Tests INV-3
    store, _ = admitted(authority, tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    identity = authority.repository_identity(str(repo))
    reserved_id = "direct-" + authority.fingerprint([identity, ["pi-a", "pi-b"]])[7:31]
    original = store.assign(reserved_id, repository=str(repo), beads=["pi-other"], effects=["read"], intent_ref="original")
    with pytest.raises(ValueError, match="immutable"):
        store.register_direct_assignment(str(repo), "pi-a", scope_beads=["pi-b"])
    assert store.assignment_for(str(repo), "pi-other") == original
    assert store.assignment_for(str(repo), "pi-a") is None


def test_fail1_missing_admission_is_not_authority(authority, tmp_path):  # Tests FAIL-1
    store = authority.AuthorityStore(tmp_path / "owner")
    repo = tmp_path / "repo"
    assignment(store, repo)
    assert store.check("work", action(repo))["status"] == "blocked"
    assert store.inspect()["status"] == "inactive"


def test_inv2_historical_provenance_is_honest_and_scope_bound(authority, tmp_path):  # Tests INV-2
    store, policy = admitted(authority, tmp_path)
    admission = store.inspect()
    assert admission["provenance"] == "historical-consent"
    assert admission["policyFingerprint"] == authority.fingerprint(policy)
    assert "human-ui" not in json.dumps(admission)
    bad = historical_record(policy)
    bad["approved"] = True
    with pytest.raises(ValueError):
        store.admit_historical(bad)
    wider = historical_record({**policy, "effects": [*policy["effects"], "secret-write"]})
    with pytest.raises(ValueError):
        store.admit_historical(wider)


@pytest.mark.parametrize("change,reason", [
    ({"bead": "pi-foreign"}, "assignment"),
    ({"effects": ["secret-write"]}, "effect"),
    ({"effects": ["force-push"]}, "effect"),
    ({"effects": ["new-spend"]}, "effect"),
    ({"target": {"identity": "foreign", "repository": "/foreign", "verified": True}}, "target"),
    ({"preconditions": {"identity": True, "platform": False, "effectClosure": True}}, "precondition"),
    ({"preconditions": {"identity": True, "platform": True}}, "precondition"),
])
def test_fail2_effective_intersection_denies_expansion(authority, tmp_path, change, reason):  # Tests FAIL-2
    store, _ = admitted(authority, tmp_path)
    repo = tmp_path / "repo"
    assignment(store, repo)
    result = store.check("work", {**action(repo), **change})
    assert result["status"] == "blocked"
    assert reason in result["reason"]


def test_inv3_assignment_and_rejection_survive_restart(authority, tmp_path):  # Tests INV-3
    store, _ = admitted(authority, tmp_path)
    repo = tmp_path / "repo"
    assignment(store, repo, denied=["deploy-production"])
    reopened = authority.AuthorityStore(store.root)
    assert reopened.check("work", action(repo))["status"] == "active"
    assert reopened.check("work", action(repo, "deploy-production"))["status"] == "blocked"
    with pytest.raises(ValueError, match="immutable"):
        assignment(reopened, repo, denied=[])


def test_inv4_revocation_blocks_sibling_and_cannot_be_reimported(authority, tmp_path):  # Tests INV-4
    store, policy = admitted(authority, tmp_path)
    repo = tmp_path / "repo"
    assignment(store, repo)
    sibling = authority.AuthorityStore(store.root)
    store.revoke("owner revoked")
    assert sibling.check("work", action(repo))["status"] == "blocked"
    with pytest.raises(ValueError, match="revoked"):
        store.admit_historical(historical_record(policy))


def test_fail3_corrupt_or_symlinked_state_fails_closed(authority, tmp_path):  # Tests FAIL-3
    store, _ = admitted(authority, tmp_path)
    (store.root / "state.json").write_text('{"schemaVersion": 99}')
    with pytest.raises(ValueError):
        store.inspect()
    linked = tmp_path / "linked"
    linked.symlink_to(store.root, target_is_directory=True)
    with pytest.raises(ValueError):
        authority.AuthorityStore(linked).inspect()


def test_inv5_narrowing_policy_cannot_widen_ceiling(authority, tmp_path):  # Tests INV-5
    store, policy = admitted(authority, tmp_path)
    repo = tmp_path / "repo"
    assignment(store, repo)
    narrower = {**policy, "effects": ["read"]}
    assert store.check("work", action(repo), policy=narrower)["status"] == "blocked"
    assert store.check("work", action(repo, "read"), policy=narrower)["status"] == "active"
    wider = {**policy, "effects": [*policy["effects"], "secret-write"]}
    assert store.check("work", action(repo), policy=wider)["status"] == "blocked"


def test_inv6_owner_root_does_not_depend_on_project(authority, tmp_path, monkeypatch):  # Tests INV-6
    monkeypatch.setenv("HOME", str(tmp_path))
    first = authority.AuthorityStore().root
    repo = tmp_path / "new-project"
    repo.mkdir()
    monkeypatch.chdir(repo)
    assert authority.AuthorityStore().root == first
    assert first == Path.home() / ".pi" / "authority"
