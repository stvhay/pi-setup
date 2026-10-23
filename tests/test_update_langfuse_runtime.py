"""Integration with the normal updater, not automatic legacy migration."""
import json
import os

from test_langfuse_runtime_delivery import bundle as bundle, installed_copy
from test_update_pi_config import ROOT, config_source, run_update


def source_with_release(tmp_path, proof):
    source = config_source(tmp_path / "source")
    (source / "agent/settings.json").write_text(json.dumps({"packages": [{
        "source": f"../runtime/pi-langfuse/releases/{proof['id']}", "extensions": [],
    }]}))
    (source / "agent/extensions/langfuse-config-env.ts").write_text("// new wrapper\n")
    library = source / "agent/extensions/lib"
    library.mkdir()
    (library / "langfuse-runtime.ts").write_bytes((ROOT / "pi/agent/extensions/lib/langfuse-runtime.ts").read_bytes())
    return source


def old_destination(tmp_path):
    dest = config_source(tmp_path / ".pi")
    (dest / "agent/settings.json").write_text('{"packages":["npm:pi-langfuse@custom"],"lastChangelogVersion":"preserved"}')
    (dest / "agent/extensions/langfuse-config-env.ts").write_text("// old wrapper\n")
    legacy = dest / "agent/npm/node_modules/pi-langfuse/private-data"
    legacy.parent.mkdir(parents=True)
    legacy.write_text("unfamiliar legacy state: handle explicitly, do not touch")
    return dest, legacy


def test_reused_release_precedes_activation_and_legacy_state_is_untouched(tmp_path, bundle):
    artifact, proof, dependency = bundle
    source = source_with_release(tmp_path, proof)
    dest, legacy = old_destination(tmp_path)
    installed_copy(artifact, dest / "runtime/pi-langfuse/releases" / proof["id"], dependency)
    patch = tmp_path / "patch"
    patch.write_text('#!/bin/sh\nset -eu\ngrep -q "old wrapper" "$PI_CONFIG_DEST/agent/extensions/langfuse-config-env.ts"\ngrep -q "pi-langfuse@custom" "$PI_CONFIG_DEST/agent/settings.json"\n')
    patch.chmod(0o755)
    before = legacy.read_bytes()
    # rsync's size/mtime quick check must not miss changed, equal-length code.
    for root in (source, dest):
        os.utime(root / "agent/extensions/langfuse-config-env.ts", (1_700_000_000, 1_700_000_000))
    result = run_update(dest, env_overrides={"PI_CONFIG_SOURCE": str(source), "PI_LANGFUSE_RUNTIME_BUNDLE": str(artifact),
                                           "PI_LANGFUSE_NPM_CLI": "/does/not/exist", "PI_PACKAGE_PATCH_HELPER": str(patch)})
    assert result.returncode == 0, result.stderr
    assert "verified-existing" in result.stdout
    assert (dest / "agent/extensions/langfuse-config-env.ts").read_text() == "// new wrapper\n"
    settings = json.loads((dest / "agent/settings.json").read_text())
    assert settings["lastChangelogVersion"] == "preserved"
    assert settings["packages"][0]["source"].endswith(proof["id"])
    assert legacy.read_bytes() == before
    assert not (dest / "runtime/pi-langfuse/.install.lock").exists()


def test_preview_names_release_without_installation_or_activation(tmp_path, bundle):
    artifact, proof, _ = bundle
    source = source_with_release(tmp_path, proof)
    dest, legacy = old_destination(tmp_path)
    result = run_update(dest, "--dry-run", env_overrides={"PI_CONFIG_SOURCE": str(source), "PI_LANGFUSE_RUNTIME_BUNDLE": str(artifact)})
    assert result.returncode == 0, result.stderr
    assert "would-install" in result.stdout
    assert proof["id"] in result.stdout
    assert not (dest / "runtime").exists()
    assert "old wrapper" in (dest / "agent/extensions/langfuse-config-env.ts").read_text()
    assert legacy.is_file()
    assert "install npm:pi-langfuse" not in result.stdout


def test_bad_bundle_does_not_replace_config(tmp_path, bundle):
    artifact, proof, _ = bundle
    source = source_with_release(tmp_path, proof)
    dest, _ = old_destination(tmp_path)
    (artifact / "index.js").write_text("changed")
    result = run_update(dest, env_overrides={"PI_CONFIG_SOURCE": str(source), "PI_LANGFUSE_RUNTIME_BUNDLE": str(artifact)})
    assert result.returncode != 0
    assert "old wrapper" in (dest / "agent/extensions/langfuse-config-env.ts").read_text()
    assert not (dest / "runtime").exists()


def test_wrong_settings_release_is_rejected_before_install(tmp_path, bundle):
    artifact, _, _ = bundle
    source = source_with_release(tmp_path, {"id": "0" * 64})
    dest, _ = old_destination(tmp_path)
    result = run_update(dest, env_overrides={"PI_CONFIG_SOURCE": str(source), "PI_LANGFUSE_RUNTIME_BUNDLE": str(artifact)})
    assert result.returncode != 0
    assert "settings" in result.stderr.lower()
    assert not (dest / "runtime").exists()


def test_failed_release_install_leaves_settings_and_legacy_unchanged(tmp_path, bundle):
    artifact, proof, _ = bundle
    source = source_with_release(tmp_path, proof)
    dest, legacy = old_destination(tmp_path)
    before = (dest / "agent/settings.json").read_bytes()
    result = run_update(dest, env_overrides={"PI_CONFIG_SOURCE": str(source), "PI_LANGFUSE_RUNTIME_BUNDLE": str(artifact),
                                           "PI_LANGFUSE_NPM_CLI": str(tmp_path / "missing-npm.js")})
    assert result.returncode != 0
    assert (dest / "agent/settings.json").read_bytes() == before
    assert "old wrapper" in (dest / "agent/extensions/langfuse-config-env.ts").read_text()
    assert legacy.is_file()


def test_single_wrapper_update_requires_already_matching_runtime_and_library(tmp_path, bundle):
    artifact, proof, dependency = bundle
    source = source_with_release(tmp_path, proof)
    dest, _ = old_destination(tmp_path)
    installed_copy(artifact, dest / "runtime/pi-langfuse/releases" / proof["id"], dependency)
    result = run_update(dest, "--file", "agent/extensions/langfuse-config-env.ts", env_overrides={
        "PI_CONFIG_SOURCE": str(source), "PI_LANGFUSE_RUNTIME_BUNDLE": str(artifact),
    })
    assert result.returncode != 0
    assert "old wrapper" in (dest / "agent/extensions/langfuse-config-env.ts").read_text()
