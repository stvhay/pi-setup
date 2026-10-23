"""update-pi-config deploy safety guardrails."""

from __future__ import annotations

import json
import os
import subprocess
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from test_langfuse_runtime_delivery import bundle as bundle, installed_copy


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "update-pi-config.sh"


def run_update(
    dest: Path, *args: str, env_overrides: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    env = {
        key: value for key, value in os.environ.items()
        if not key.startswith(("LANGFUSE_", "PI_LANGFUSE_", "PI_CONFIG_", "PI_PACKAGE_PATCH_", "PI_CODING_AGENT_"))
    }
    env["PI_CONFIG_DEST"] = str(dest)
    env["PI_COMMAND"] = "/usr/bin/true"
    env["PI_PACKAGE_PATCH_HELPER"] = "/usr/bin/true"
    with TemporaryDirectory(prefix="pi-deploy-source-") as directory:
        source = config_source(Path(directory))
        env["PI_CONFIG_SOURCE"] = str(source)
        env.update(env_overrides or {})
        return subprocess.run(
            ["bash", str(SCRIPT), *args],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )


def config_source(source: Path) -> Path:
    for directory in ("agent/bin", "agent/skills", "agent/extensions"):
        (source / directory).mkdir(parents=True, exist_ok=True)
    for name in ("README.md", ".gitignore", "agent/AGENTS.md"):
        (source / name).write_text("test config\n", encoding="utf-8")
    (source / "agent/settings.json").write_text('{"packages": []}\n', encoding="utf-8")
    (source / "agent/catalog.json").write_text('{}\n', encoding="utf-8")
    agnt = source / "agent/bin/agnt"
    agnt.write_text('#!/bin/sh\nprintf "{}\\n"\n', encoding="utf-8")
    agnt.chmod(0o755)
    return source


@pytest.mark.parametrize("relative,backup_name,file_mode,old,new", [
    ("agent/extensions/fixture.ts", "before.ts", 0o640, "old extension\n", "new extension\n"),
    ("agent/bin/start-craft-mcp.sh", "before.sh", 0o750, "#!/bin/sh\nexit 98\n", "#!/bin/sh\nexit 99\n"),
])
def test_file_update_previews_backs_up_and_preserves_unrelated_state(tmp_path, relative, backup_name, file_mode, old, new):
    source = config_source(tmp_path / "source")
    dest = config_source(tmp_path / ".pi")
    (source / relative).write_text(new)
    (source / relative).chmod(0o755 if relative.endswith(".sh") else 0o644)
    (dest / relative).write_text(old)
    (dest / relative).chmod(file_mode)
    mcp = dest / "agent/mcp.json"
    mcp.write_text('{"mcpServers":{"preserved":{}}}\n')
    settings = (dest / "agent/settings.json").read_bytes()
    overrides = {"PI_CONFIG_SOURCE": str(source), "PI_COMMAND": "/usr/bin/false",
                 "PI_PACKAGE_PATCH_HELPER": "/usr/bin/false"}

    preview = run_update(dest, "--dry-run", "--file", relative, env_overrides=overrides)
    assert preview.returncode == 0, preview.stderr
    assert (dest / relative).read_text() == old
    assert (dest / relative).stat().st_mode & 0o777 == file_mode
    assert not (dest / "runtime").exists()
    assert relative in preview.stdout
    assert "*deleting" not in preview.stdout

    applied = run_update(dest, "--file", relative, env_overrides=overrides)
    assert applied.returncode == 0, applied.stderr
    assert (dest / relative).read_text() == new
    assert mcp.read_text() == '{"mcpServers":{"preserved":{}}}\n'
    assert (dest / "agent/settings.json").read_bytes() == settings
    backups = list((dest / "runtime/deployment-backups").glob(f"*/{backup_name}"))
    assert len(backups) == 1
    assert backups[0].read_text() == old
    assert backups[0].stat().st_mode & 0o777 == 0o600
    receipt = json.loads((backups[0].parent / "receipt.json").read_text())
    assert receipt["destination"] == str(dest / relative)
    assert receipt["verified"] is True
    assert receipt["beforeMode"] == f"{file_mode:04o}"
    assert (dest / relative).stat().st_mode & 0o777 == file_mode
    repeated = run_update(dest, "--file", relative, env_overrides=overrides)
    assert repeated.returncode == 0, repeated.stderr
    assert list((dest / "runtime/deployment-backups").glob(f"*/{backup_name}")) == backups


@pytest.mark.parametrize("relative", ["agent/auth.json", "../escape.ts", "/tmp/escape.ts",
                                     "agent/extensions/../escape.ts", "agent/extensions/missing.ts",
                                     "agent/bin/agnt", "agent/bin/other.sh",
                                     "agent/bin/./start-craft-mcp.sh", "agent/bin/start-craft-mcp.sh/",
                                     "agent/extensions/fixture.local.ts"])
def test_file_update_rejects_unmanaged_or_missing_paths(tmp_path, relative):
    dest = config_source(tmp_path / ".pi")
    proc = run_update(dest, "--file", relative)
    assert proc.returncode != 0
    assert not (dest / "runtime").exists()


@pytest.mark.parametrize("side", ["source", "destination"])
def test_file_update_rejects_symlink_files_and_ancestors(tmp_path, side):
    source = config_source(tmp_path / "source")
    dest = config_source(tmp_path / ".pi")
    relative = "agent/extensions/fixture.ts"
    (source / relative).write_text("new\n")
    (dest / relative).write_text("old\n")
    root = source if side == "source" else dest
    target = tmp_path / "unowned"
    target.write_text("preserve\n")
    (root / relative).unlink()
    (root / relative).symlink_to(target)
    overrides = {"PI_CONFIG_SOURCE": str(source)}
    assert run_update(dest, "--file", relative, env_overrides=overrides).returncode != 0
    (root / relative).unlink()
    (root / "agent/extensions").rmdir()
    (root / "agent/extensions").symlink_to(tmp_path, target_is_directory=True)
    assert run_update(dest, "--file", relative, env_overrides=overrides).returncode != 0
    assert target.read_text() == "preserve\n"
    assert not (dest / "runtime").exists()


@pytest.mark.parametrize("side", ["source", "destination"])
@pytest.mark.parametrize("problem", ["missing", "non-executable", "symlink", "symlink-parent"])
def test_craft_file_update_refuses_unsafe_or_nonexecutable_paths(tmp_path, side, problem):
    source = config_source(tmp_path / "source")
    dest = config_source(tmp_path / ".pi")
    relative = "agent/bin/start-craft-mcp.sh"
    for root in (source, dest):
        (root / relative).write_text("#!/bin/sh\nexit 99\n")
        (root / relative).chmod(0o755)
    root = source if side == "source" else dest
    path = root / relative
    if problem == "missing":
        path.unlink()
    elif problem == "non-executable":
        path.chmod(0o644)
    else:
        path = path.parent if problem == "symlink-parent" else path
        moved = tmp_path / "preserved"
        path.rename(moved)
        path.symlink_to(moved, target_is_directory=moved.is_dir())
    proc = run_update(dest, "--file", relative, env_overrides={"PI_CONFIG_SOURCE": str(source)})
    assert proc.returncode != 0
    if problem == "non-executable":
        assert "Craft launcher must be executable" in proc.stderr
    assert not (dest / "runtime").exists()


@pytest.mark.parametrize("relative", ["agent/bin/other.sh", "agent/bin/start-craft-mcp.sh.extra",
                                     "agent/bin/agnt", "agent/extensions/fixture.local.ts"])
def test_file_update_rejects_other_existing_files(tmp_path, relative):
    source = config_source(tmp_path / "source")
    dest = config_source(tmp_path / ".pi")
    # Keep fixture agnt functional because layout validation invokes it.
    new = '#!/bin/sh\nprintf "{}\\n"\n# new\n'
    old = '#!/bin/sh\nprintf "{}\\n"\n# old\n'
    (source / relative).write_text(new)
    (dest / relative).write_text(old)
    (source / relative).chmod(0o755)
    (dest / relative).chmod(0o755)
    proc = run_update(dest, "--file", relative, env_overrides={"PI_CONFIG_SOURCE": str(source)})
    assert proc.returncode != 0
    assert (dest / relative).read_text() == old
    assert not (dest / "runtime").exists()


def test_update_helper_isolates_ambient_credentials_and_targets(monkeypatch, tmp_path):
    inherited = {
        "LANGFUSE_PUBLIC_KEY": "ambient-public",
        "LANGFUSE_SECRET_KEY": "ambient-secret",
        "LANGFUSE_BASE_URL": "https://example.invalid",
        "LANGFUSE_HOST": "https://example.invalid",
        "PI_CONFIG_SOURCE": "/ambient/source",
        "PI_CONFIG_DEST_UNSAFE_OK": "1",
        "PI_PACKAGE_PATCH_DIR": "/ambient/patches",
        "PI_CODING_AGENT_DIR": "/ambient/agent",
    }
    for key, value in inherited.items():
        monkeypatch.setenv(key, value)
    seen = {}
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: seen.update(kwargs))

    run_update(tmp_path / ".pi")

    assert all(seen["env"].get(key) != value for key, value in inherited.items())
    assert seen["env"]["PI_CONFIG_DEST"] == str(tmp_path / ".pi")


def langfuse_patch_dir(tmp_path: Path) -> Path:
    patches = tmp_path / "patches"
    patches.mkdir()
    (patches / "pi-archimedes-meta-2.11.1.patch").write_text(
        """diff --git a/src/config.ts b/src/config.ts
--- a/src/config.ts
+++ b/src/config.ts
@@ -1 +1 @@
-old-meta
+new-meta
""",
        encoding="utf-8",
    )
    (patches / "pi-archimedes-subagent-2.11.1.patch").write_text(
        """diff --git a/src/index.ts b/src/index.ts
--- a/src/index.ts
+++ b/src/index.ts
@@ -1 +1 @@
-old-subagent
+new-subagent
""",
        encoding="utf-8",
    )
    (patches / "pi-archimedes-footer-2.11.1.patch").write_text(
        """diff --git a/src/index.ts b/src/index.ts
--- a/src/index.ts
+++ b/src/index.ts
@@ -1 +1 @@
-old-footer
+new-footer
""",
        encoding="utf-8",
    )
    (patches / "pi-archimedes-ask-2.11.1.patch").write_text(
        """diff --git a/src/ipc-relay.ts b/src/ipc-relay.ts
--- a/src/ipc-relay.ts
+++ b/src/ipc-relay.ts
@@ -1 +1 @@
-old-ask
+new-ask
""",
        encoding="utf-8",
    )
    (patches / "pi-archimedes-core-2.11.1.patch").write_text(
        """diff --git a/src/events.ts b/src/events.ts
--- a/src/events.ts
+++ b/src/events.ts
@@ -1 +1 @@
-old-bus
+new-bus
""",
        encoding="utf-8",
    )
    (patches / "pi-langfuse-1.7.0.patch").write_text(
        """diff --git a/index.ts b/index.ts
--- a/index.ts
+++ b/index.ts
@@ -1 +1 @@
-getSessionFile?.();
+getSessionId?.();
diff --git a/src/langfuse.ts b/src/langfuse.ts
--- a/src/langfuse.ts
+++ b/src/langfuse.ts
@@ -1 +1,2 @@
-old-runtime
+score.id ??= randomUUID();
+const MAX_INGESTION_REQUEST_BYTES = 3_000_000;
diff --git a/src/types.ts b/src/types.ts
--- a/src/types.ts
+++ b/src/types.ts
@@ -1 +1 @@
-old-type
+new-type
""",
        encoding="utf-8",
    )
    return patches


def write_clean_langfuse(package: Path) -> None:
    (package / "index.ts").write_text("getSessionFile?.();\n", encoding="utf-8")
    (package / "src").mkdir()
    (package / "src/langfuse.ts").write_text("old-runtime\n", encoding="utf-8")
    (package / "src/types.ts").write_text("old-type\n", encoding="utf-8")


def write_applied_archimedes(meta: Path, subagent: Path) -> None:
    ask = subagent.parent / "ask"
    core = subagent.parent / "core"
    footer = subagent.parent / "footer"
    for package, name in (
        (ask, "@pi-archimedes/ask"),
        (core, "@pi-archimedes/core"),
        (footer, "@pi-archimedes/footer"),
    ):
        package.mkdir(exist_ok=True)
        package_json = package / "package.json"
        if not package_json.exists():
            package_json.write_text(
                json.dumps({"name": name, "version": "2.11.1"}),
                encoding="utf-8",
            )
        (package / "src").mkdir(exist_ok=True)
    (meta / "src").mkdir(exist_ok=True)
    (subagent / "src").mkdir(exist_ok=True)
    (meta / "src/config.ts").write_text("new-meta\n", encoding="utf-8")
    (ask / "src/ipc-relay.ts").write_text("new-ask\n", encoding="utf-8")
    (core / "src/events.ts").write_text("new-bus\n", encoding="utf-8")
    (subagent / "src/index.ts").write_text("new-subagent\n", encoding="utf-8")
    (footer / "src/index.ts").write_text("new-footer\n", encoding="utf-8")


def write_archimedes_footer(footer: Path, source: str = "new-footer\n") -> None:
    (footer / "src").mkdir(exist_ok=True)
    (footer / "src/index.ts").write_text(source, encoding="utf-8")


def write_package(root: Path, relative: str, name: str, version: str) -> Path:
    package = root / relative
    package.mkdir(parents=True)
    (package / "package.json").write_text(json.dumps({"name": name, "version": version}), encoding="utf-8")
    return package


def test_update_refuses_home_destination_without_mutating(tmp_path):
    home_dest = Path.home()
    marker = home_dest / ".managed-by-pi-setup"
    before = marker.exists()

    proc = run_update(home_dest)

    assert proc.returncode == 1
    assert "Refusing unsafe PI_CONFIG_DEST" in proc.stderr
    assert marker.exists() is before


def test_update_refuses_non_pi_basename_before_creating_parent(tmp_path):
    dest = tmp_path / "nested" / "not-pi"

    proc = run_update(dest)

    assert proc.returncode == 1
    assert "destination basename must be .pi" in proc.stderr
    assert not dest.exists()
    assert not dest.parent.exists()


def test_update_preserves_pi_managed_mutable_state(tmp_path, bundle):
    dest = tmp_path / ".pi"
    agent = dest / "agent"
    agent.mkdir(parents=True)
    runtime_settings = {
        "lastChangelogVersion": "99.0.0",
        "runtimeOnly": "must not survive",
    }
    (agent / "settings.json").write_text(json.dumps(runtime_settings), encoding="utf-8")
    models_store = '{"openrouter":{"models":[{"id":"cached-model"}]}}\n'
    (agent / "models-store.json").write_text(models_store, encoding="utf-8")

    # Real config/layout, with fixture release bytes; actual SDK installation is
    # exercised separately by the package delivery verifier.
    artifact, proof, dependency = bundle
    source = tmp_path / "source"
    shutil.copytree(ROOT / "pi", source)
    settings_path = source / "agent/settings.json"
    settings = json.loads(settings_path.read_text())
    for entry in settings["packages"]:
        if isinstance(entry, dict) and entry["source"].startswith("../runtime/pi-langfuse/"):
            entry["source"] = f"../runtime/pi-langfuse/releases/{proof['id']}"
    settings_path.write_text(json.dumps(settings))
    installed_copy(artifact, dest / "runtime/pi-langfuse/releases" / proof["id"], dependency)
    proc = run_update(dest, env_overrides={"PI_CONFIG_SOURCE": str(source), "PI_LANGFUSE_RUNTIME_BUNDLE": str(artifact)})

    assert proc.returncode == 0, proc.stderr
    deployed_settings = json.loads((agent / "settings.json").read_text(encoding="utf-8"))
    source_settings = json.loads((source / "agent/settings.json").read_text(encoding="utf-8"))
    assert deployed_settings["lastChangelogVersion"] == "99.0.0"
    assert deployed_settings["packages"] == source_settings["packages"]
    assert "runtimeOnly" not in deployed_settings
    assert (agent / "models-store.json").read_text(encoding="utf-8") == models_store


def test_update_preserves_mcp_runtime_without_craft_template(tmp_path):
    dest = config_source(tmp_path / ".pi")
    names = ("mcp.json", "mcp-auth.json", "mcp.log", "mcp.log.1")
    for name in names:
        (dest / "agent" / name).write_text("private unchanged\n")
    proc = run_update(dest)
    assert proc.returncode == 0, proc.stderr
    assert all((dest / "agent" / name).is_file() for name in names), "MCP runtime deleted"
    assert all((dest / "agent" / name).read_text() == "private unchanged\n" for name in names)
    backup = next((dest / "runtime/deployment-backups").glob("*/config"))
    assert all(not (backup / "agent" / name).exists() for name in names)


def craft_source(path):
    source = config_source(path)
    (source / "agent/craft").mkdir()
    (source / "agent/craft/mcp.json").write_text(json.dumps({"mcpServers": {
        "photocraft-pilot": {"command": "agent/bin/start-craft-mcp.sh", "args": ["photocraft"],
                            "enabled": False, "cwd": ".", "timeout": 30, "exposure": "codemode"}}}))
    launcher = source / "agent/bin/start-craft-mcp.sh"
    launcher.write_text("#!/bin/sh\nexit 99\n")
    launcher.chmod(0o755)
    return source


@pytest.mark.parametrize("enabled", [True, False, None])
def test_craft_deploy_preserves_runtime_and_records_private_backup(tmp_path, enabled):
    source = craft_source(tmp_path / "source")
    dest = config_source(tmp_path / ".pi")
    entry = {"command": str(Path.home() / ".artcraft/start-craft-mcp.sh"),
             "args": ["photocraft"], "cwd": "custom", "env": {"EXAMPLE": "private-value"},
             "timeout": 45, "toolExposure": {"*": "hidden"}}
    if enabled is not None:
        entry["enabled"] = enabled
    original = {"autoEnableCodemode": False, "other": [1, 2], "mcpServers": {
        "photocraft-pilot": entry, "unrelated": {"url": "https://example.invalid"},
        "vectorcraft-pilot": {"enabled": False, "command": "do-not-change"}}}
    path = dest / "agent/mcp.json"
    old = json.dumps(original).encode() + b"\n"
    path.write_bytes(old)
    path.chmod(0o640)
    overrides = {"PI_CONFIG_SOURCE": str(source)}
    preview = run_update(dest, "--dry-run", env_overrides=overrides)
    assert preview.returncode == 0, preview.stderr
    assert path.read_bytes() == old
    assert not (dest / "runtime").exists()
    assert "private-value" not in preview.stdout + preview.stderr
    assert "Craft MCP" in preview.stdout
    applied = run_update(dest, env_overrides=overrides)
    assert applied.returncode == 0, applied.stderr
    expected = json.loads(old)
    expected["mcpServers"]["photocraft-pilot"]["command"] = str(dest / "agent/bin/start-craft-mcp.sh")
    assert path.is_file(), "MCP config deleted instead of reconciled"
    assert json.loads(path.read_text()) == expected
    assert path.stat().st_mode & 0o777 == 0o640
    backups = list((dest / "runtime/deployment-backups").glob("craft-*/before.json"))
    assert len(backups) == 1
    assert backups[0].read_bytes() == old
    assert backups[0].stat().st_mode & 0o777 == 0o600
    receipt = json.loads((backups[0].parent / "receipt.json").read_text())
    assert receipt["verified"] is True
    assert receipt["beforeMode"] == "0640"
    after = path.read_bytes()
    repeated = run_update(dest, env_overrides=overrides)
    assert repeated.returncode == 0, repeated.stderr
    assert path.read_bytes() == after
    assert list((dest / "runtime/deployment-backups").glob("craft-*/before.json")) == backups


def test_craft_deploy_creates_only_disabled_photocraft(tmp_path):
    source = craft_source(tmp_path / "source")
    dest = tmp_path / ".pi"
    proc = run_update(dest, env_overrides={"PI_CONFIG_SOURCE": str(source)})
    assert proc.returncode == 0, proc.stderr
    path = dest / "agent/mcp.json"
    assert path.is_file(), "managed disabled entry missing"
    data = json.loads(path.read_text())
    assert set(data["mcpServers"]) == {"photocraft-pilot"}
    assert data["mcpServers"]["photocraft-pilot"]["enabled"] is False
    assert path.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("content", [
    "{bad", "[]", '{"mcpServers":[]}', '{"mcpServers":{},"mcpServers":{}}',
    '{"mcpServers":{"photocraft-pilot":{"command":"unowned"}}}',
    '{"mcpServers":{"photocraft_pilot":{"command":"collision"}}}',
])
def test_craft_deploy_refuses_invalid_or_unowned_config_before_writes(tmp_path, content):
    source = craft_source(tmp_path / "source")
    dest = config_source(tmp_path / ".pi")
    path = dest / "agent/mcp.json"
    path.write_text(content)
    proc = run_update(dest, env_overrides={"PI_CONFIG_SOURCE": str(source)})
    assert proc.returncode != 0
    assert path.read_text() == content
    assert not (dest / "runtime").exists()


@pytest.mark.parametrize("name", ["agent", "agent/mcp.json"])
def test_craft_deploy_refuses_symlinks_before_writes(tmp_path, name):
    source = craft_source(tmp_path / "source")
    dest = tmp_path / ".pi"
    dest.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "mcp.json").write_text('{"mcpServers":{}}')
    link = dest / name
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(outside if name == "agent" else outside / "mcp.json")
    proc = run_update(dest, env_overrides={"PI_CONFIG_SOURCE": str(source)})
    assert proc.returncode != 0
    assert link.is_symlink()
    assert (outside / "mcp.json").read_text() == '{"mcpServers":{}}'
    assert not (dest / "runtime").exists()


def test_update_preserves_machine_local_extensions(tmp_path):
    dest = tmp_path / ".pi"
    extension = dest / "agent" / "extensions" / "ollama.local.ts"
    extension.parent.mkdir(parents=True)
    content = "// machine-local provider\n"
    extension.write_text(content, encoding="utf-8")

    proc = run_update(dest)

    assert proc.returncode == 0, proc.stderr
    assert extension.read_text(encoding="utf-8") == content


def test_update_backs_up_retired_ollama_local_extension(tmp_path):
    dest = tmp_path / ".pi"
    extension = dest / "agent" / "extensions" / "ollama.local.ts"
    extension.parent.mkdir(parents=True)
    content = 'import { buildModels } from "./olla-provider.ts";\n'
    extension.write_text(content, encoding="utf-8")

    proc = run_update(dest)

    assert proc.returncode == 0, proc.stderr
    assert not extension.exists()
    backups = list((dest / "runtime" / "retired-config").glob("ollama.local.ts-*"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == content
    assert "Retiring incompatible machine-local Ollama extension" in proc.stdout


def test_update_dry_run_reports_retired_ollama_local_extension_without_mutating(tmp_path):
    dest = tmp_path / ".pi"
    extension = dest / "agent" / "extensions" / "ollama.local.ts"
    extension.parent.mkdir(parents=True)
    content = 'import { buildModels } from "./olla-provider.ts";\n'
    extension.write_text(content, encoding="utf-8")

    proc = run_update(dest, "--dry-run")

    assert proc.returncode == 0, proc.stderr
    assert extension.read_text(encoding="utf-8") == content
    assert "Retiring incompatible machine-local Ollama extension" in proc.stdout
    assert "runtime/retired-config/ollama.local.ts-" in proc.stdout


def test_update_does_not_overwrite_existing_retired_ollama_backup(tmp_path):
    dest = tmp_path / ".pi"
    extension = dest / "agent" / "extensions" / "ollama.local.ts"
    extension.parent.mkdir(parents=True)
    extension.write_text('./olla-provider.ts\n', encoding="utf-8")
    retired = dest / "runtime" / "retired-config"
    retired.mkdir(parents=True)
    existing = retired / "ollama.local.ts-20000101-000000"
    existing.write_text("existing backup\n", encoding="utf-8")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    date = fake_bin / "date"
    date.write_text("#!/bin/sh\necho 20000101-000000\n", encoding="utf-8")
    date.chmod(0o755)

    proc = run_update(
        dest,
        env_overrides={"PATH": f"{fake_bin}:{os.environ['PATH']}"},
    )

    assert proc.returncode == 0, proc.stderr
    assert existing.read_text(encoding="utf-8") == "existing backup\n"
    assert len(list(retired.glob("ollama.local.ts-*"))) == 2


def test_update_preserves_langfuse_credentials(tmp_path):
    dest = tmp_path / ".pi"
    config = dest / "agent" / "pi-langfuse" / "config.json"
    config.parent.mkdir(parents=True)
    credentials = '{"publicKey":"pk-test","secretKey":"sk-test"}\n'
    config.write_text(credentials, encoding="utf-8")

    proc = run_update(dest)

    assert proc.returncode == 0, proc.stderr
    assert config.read_text(encoding="utf-8") == credentials


def test_update_preserves_private_improvement_runtime(tmp_path):
    dest = tmp_path / ".pi"
    report = dest / "improvement" / "scan-private.json"
    report.parent.mkdir(parents=True)
    report.write_text('{"private": true}\n', encoding="utf-8")

    proc = run_update(dest)

    assert proc.returncode == 0, proc.stderr
    assert report.read_text(encoding="utf-8") == '{"private": true}\n'


def test_update_preserves_private_runtime_store(tmp_path):
    dest = tmp_path / ".pi"
    artifact = dest / "runtime" / "repository-hash" / "runs" / "result.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text('{"private": true}\n', encoding="utf-8")

    proc = run_update(dest)

    assert proc.returncode == 0, proc.stderr
    assert "cannot delete non-empty directory" not in proc.stdout + proc.stderr
    assert artifact.read_text(encoding="utf-8") == '{"private": true}\n'


def test_update_preserves_owner_authority_but_deploys_policy_template(tmp_path):
    dest = tmp_path / ".pi"
    state = dest / "authority/state.json"
    state.parent.mkdir(parents=True)
    state.write_text('{"private": true}\n')
    source = config_source(tmp_path / "source")
    template = source / "agent/authority/full-delivery.json"
    template.parent.mkdir()
    template.write_text('{"template": true}\n')
    proc = run_update(dest, env_overrides={"PI_CONFIG_SOURCE": str(source)})
    assert proc.returncode == 0, proc.stderr
    assert state.exists(), "deployment deleted owner authority"
    assert state.read_text() == '{"private": true}\n'
    assert (dest / "agent/authority/full-delivery.json").read_text() == template.read_text()


def test_update_deletes_unmanaged_nested_git_but_preserves_private_git_store(tmp_path):
    dest = tmp_path / ".pi"
    stale = dest / "eval-runs" / "run" / "repo" / ".git" / "config"
    private = dest / "agent" / "git" / "checkout" / ".git" / "config"
    stale.parent.mkdir(parents=True)
    private.parent.mkdir(parents=True)
    stale.write_text("stale\n", encoding="utf-8")
    private.write_text("private\n", encoding="utf-8")

    proc = run_update(dest)

    assert proc.returncode == 0, proc.stderr
    assert "cannot delete non-empty directory" not in proc.stdout + proc.stderr
    assert not (dest / "eval-runs").exists()
    assert private.read_text(encoding="utf-8") == "private\n"


def test_update_dry_run_excludes_models_store(tmp_path):
    proc = run_update(tmp_path / ".pi", "--dry-run")

    assert proc.returncode == 0, proc.stderr
    assert "--exclude=agent/models-store.json" in proc.stdout


def test_update_installs_exact_patch_bases_before_applying_patches(tmp_path):
    dest = tmp_path / ".pi"
    log = tmp_path / "package-sync.log"
    fake_pi = tmp_path / "pi"
    fake_patch = tmp_path / "apply-patches"
    fake_pi.write_text(
        '#!/bin/sh\nprintf "pi|%s|%s\\n" "$PI_CODING_AGENT_DIR" "$*" >>"$PI_DEPLOY_LOG"\n',
        encoding="utf-8",
    )
    fake_patch.write_text(
        '#!/bin/sh\nprintf "patch|%s|%s\\n" "$PI_CONFIG_DEST" "$*" >>"$PI_DEPLOY_LOG"\n',
        encoding="utf-8",
    )
    fake_pi.chmod(0o755)
    fake_patch.chmod(0o755)

    proc = run_update(
        dest,
        env_overrides={
            "PI_COMMAND": str(fake_pi),
            "PI_PACKAGE_PATCH_HELPER": str(fake_patch),
            "PI_DEPLOY_LOG": str(log),
        },
    )

    assert proc.returncode == 0, proc.stderr
    assert log.read_text(encoding="utf-8").splitlines() == [
        f"pi|{dest / 'agent'}|install npm:pi-archimedes@2.11.1",
        f"patch|{dest}|",
    ]




def test_update_repairs_missing_archimedes_subagent_before_patching(tmp_path):
    dest = tmp_path / ".pi"
    log = tmp_path / "package-sync.log"
    for relative, name, version in (
        ("pi-archimedes", "pi-archimedes", "2.11.1"),
        ("pi-langfuse", "pi-langfuse", "1.7.0"),
    ):
        package = write_package(dest / "agent" / "npm" / "node_modules", relative, name, version)
        if name == "pi-langfuse":
            write_clean_langfuse(package)
    fake_pi = tmp_path / "pi"
    fake_patch = tmp_path / "apply-patches"
    fake_pi.write_text(
        '#!/bin/sh\nprintf "pi|%s\\n" "$*" >>"$PI_DEPLOY_LOG"\n',
        encoding="utf-8",
    )
    fake_patch.write_text(
        '#!/bin/sh\nprintf "patch|%s\\n" "$PI_CONFIG_DEST" >>"$PI_DEPLOY_LOG"\n',
        encoding="utf-8",
    )
    fake_pi.chmod(0o755)
    fake_patch.chmod(0o755)

    proc = run_update(
        dest,
        env_overrides={
            "PI_COMMAND": str(fake_pi),
            "PI_PACKAGE_PATCH_HELPER": str(fake_patch),
            "PI_PACKAGE_PATCH_DIR": str(langfuse_patch_dir(tmp_path)),
            "PI_DEPLOY_LOG": str(log),
        },
    )

    assert proc.returncode == 0, proc.stderr
    assert log.read_text(encoding="utf-8").splitlines() == [
        "pi|install npm:pi-archimedes@2.11.1",
        f"patch|{dest}",
    ]


def test_update_skips_exact_patch_bases_before_applying_patches(tmp_path):
    dest = tmp_path / ".pi"
    log = tmp_path / "package-sync.log"
    for relative, name, version in (
        ("pi-archimedes", "pi-archimedes", "2.11.1"),
        ("@pi-archimedes/subagent", "@pi-archimedes/subagent", "2.11.1"),
        ("pi-langfuse", "pi-langfuse", "1.7.0"),
    ):
        package = write_package(dest / "agent" / "npm" / "node_modules", relative, name, version)
    modules = dest / "agent" / "npm" / "node_modules"
    write_applied_archimedes(
        modules / "pi-archimedes",
        modules / "@pi-archimedes/subagent",
    )
    langfuse = modules / "pi-langfuse"
    (langfuse / "index.ts").write_text("getSessionId?.();\n", encoding="utf-8")
    (langfuse / "src").mkdir()
    (langfuse / "src/langfuse.ts").write_text(
        "score.id ??= randomUUID();\nconst MAX_INGESTION_REQUEST_BYTES = 3_000_000;\n",
        encoding="utf-8",
    )
    (langfuse / "src/types.ts").write_text("new-type\n", encoding="utf-8")
    fake_pi = tmp_path / "pi"
    fake_patch = tmp_path / "apply-patches"
    fake_pi.write_text(
        '#!/bin/sh\nprintf "pi|%s\\n" "$*" >>"$PI_DEPLOY_LOG"\n',
        encoding="utf-8",
    )
    fake_patch.write_text(
        '#!/bin/sh\nprintf "patch|%s\\n" "$PI_CONFIG_DEST" >>"$PI_DEPLOY_LOG"\n',
        encoding="utf-8",
    )
    fake_pi.chmod(0o755)
    fake_patch.chmod(0o755)

    proc = run_update(
        dest,
        env_overrides={
            "PI_COMMAND": str(fake_pi),
            "PI_PACKAGE_PATCH_HELPER": str(fake_patch),
            "PI_PACKAGE_PATCH_DIR": str(langfuse_patch_dir(tmp_path)),
            "PI_DEPLOY_LOG": str(log),
        },
    )

    assert proc.returncode == 0, proc.stderr
    assert log.read_text(encoding="utf-8").splitlines() == [f"patch|{dest}"]
    assert "pi-archimedes 2.11.1: already installed" in proc.stdout
    assert "@pi-archimedes/ask 2.11.1: already installed" in proc.stdout
    assert "@pi-archimedes/core 2.11.1: already installed" in proc.stdout
    assert "@pi-archimedes/subagent 2.11.1: already installed" in proc.stdout
    assert "@pi-archimedes/footer 2.11.1: already installed" in proc.stdout
    assert "pi-langfuse 1.7.0: already installed" not in proc.stdout


@pytest.mark.parametrize("applied", [False, True])
@pytest.mark.parametrize("offset", [False, True])
def test_update_patch_base_preview_requires_exact_match(tmp_path, patch_implementation, applied, offset):
    dest = tmp_path / ".pi"
    modules = dest / "agent/npm/node_modules"
    meta = write_package(modules, "pi-archimedes", "pi-archimedes", "2.11.1")
    subagent = write_package(modules, "@pi-archimedes/subagent", "@pi-archimedes/subagent", "2.11.1")
    langfuse = write_package(modules, "pi-langfuse", "pi-langfuse", "1.7.0")
    write_applied_archimedes(meta, subagent)
    write_clean_langfuse(langfuse)
    target = subagent / "src/index.ts"
    content = ("unexpected-prefix\n" if offset else "") + ("new-subagent\n" if applied else "old-subagent\n")
    target.write_text(content, encoding="utf-8")
    before = {path: path.read_bytes() for path in modules.rglob("*") if path.is_file()}

    result = run_update(dest, "--dry-run", env_overrides={
        "PI_PACKAGE_PATCH_DIR": str(langfuse_patch_dir(tmp_path)),
    })

    assert result.returncode == 0, result.stderr
    assert ("install npm:pi-archimedes@2.11.1" in result.stdout) == offset
    assert ("@pi-archimedes/subagent 2.11.1: already installed" in result.stdout) == (not offset)
    assert {path: path.read_bytes() for path in modules.rglob("*") if path.is_file()} == before


def test_update_reinstalls_exact_archimedes_when_patch_revision_is_stale(tmp_path):
    dest = tmp_path / ".pi"
    log = tmp_path / "package-sync.log"
    for relative, name, version in (
        ("pi-archimedes", "pi-archimedes", "2.11.1"),
        ("@pi-archimedes/subagent", "@pi-archimedes/subagent", "2.11.1"),
        ("pi-langfuse", "pi-langfuse", "1.7.0"),
    ):
        package = write_package(dest / "agent" / "npm" / "node_modules", relative, name, version)
        if name == "pi-langfuse":
            write_clean_langfuse(package)
    modules = dest / "agent" / "npm" / "node_modules"
    (modules / "pi-archimedes/src").mkdir()
    (modules / "pi-archimedes/src/config.ts").write_text("new-meta\n", encoding="utf-8")
    stale = modules / "@pi-archimedes/subagent/src/index.ts"
    stale.parent.mkdir(parents=True)
    stale.write_text("unexpected-prefix\nnew-subagent\n", encoding="utf-8")
    fake_pi = tmp_path / "pi"
    fake_patch = tmp_path / "apply-patches"
    fake_pi.write_text(
        '#!/bin/sh\n'
        'root="$PI_CODING_AGENT_DIR/npm/node_modules"\n'
        'mkdir -p "$root/pi-archimedes" "$root/@pi-archimedes/ask" "$root/@pi-archimedes/core" "$root/@pi-archimedes/subagent" "$root/@pi-archimedes/footer"\n'
        'printf \'{"name":"pi-archimedes","version":"2.11.1"}\\n\' >"$root/pi-archimedes/package.json"\n'
        'printf \'{"name":"@pi-archimedes/ask","version":"2.11.1"}\\n\' >"$root/@pi-archimedes/ask/package.json"\n'
        'printf \'{"name":"@pi-archimedes/core","version":"2.11.1"}\\n\' >"$root/@pi-archimedes/core/package.json"\n'
        'printf \'{"name":"@pi-archimedes/subagent","version":"2.11.1"}\\n\' >"$root/@pi-archimedes/subagent/package.json"\n'
        'printf \'{"name":"@pi-archimedes/footer","version":"2.11.1"}\\n\' >"$root/@pi-archimedes/footer/package.json"\n'
        'printf "pi|%s\\n" "$*" >>"$PI_DEPLOY_LOG"\n',
        encoding="utf-8",
    )
    fake_patch.write_text(
        '#!/bin/sh\nprintf "patch|%s\\n" "$PI_CONFIG_DEST" >>"$PI_DEPLOY_LOG"\n',
        encoding="utf-8",
    )
    fake_pi.chmod(0o755)
    fake_patch.chmod(0o755)

    proc = run_update(
        dest,
        env_overrides={
            "PI_COMMAND": str(fake_pi),
            "PI_PACKAGE_PATCH_HELPER": str(fake_patch),
            "PI_PACKAGE_PATCH_DIR": str(langfuse_patch_dir(tmp_path)),
            "PI_DEPLOY_LOG": str(log),
        },
    )

    assert proc.returncode == 0, proc.stderr
    assert log.read_text(encoding="utf-8").splitlines() == [
        "pi|install npm:pi-archimedes@2.11.1",
        f"patch|{dest}",
    ]


def test_update_reinstalls_exact_archimedes_when_footer_patch_revision_is_stale(tmp_path):
    dest = tmp_path / ".pi"
    log = tmp_path / "package-sync.log"
    modules = dest / "agent" / "npm" / "node_modules"
    meta = write_package(modules, "pi-archimedes", "pi-archimedes", "2.11.1")
    subagent = write_package(modules, "@pi-archimedes/subagent", "@pi-archimedes/subagent", "2.11.1")
    footer = write_package(modules, "@pi-archimedes/footer", "@pi-archimedes/footer", "2.11.1")
    langfuse = write_package(modules, "pi-langfuse", "pi-langfuse", "1.7.0")
    write_applied_archimedes(meta, subagent)
    write_archimedes_footer(footer, "unexpected-footer\n")
    write_clean_langfuse(langfuse)
    fake_pi = tmp_path / "pi"
    fake_patch = tmp_path / "apply-patches"
    fake_pi.write_text(
        '#!/bin/sh\n'
        'root="$PI_CODING_AGENT_DIR/npm/node_modules"\n'
        'mkdir -p "$root/pi-archimedes" "$root/@pi-archimedes/ask" "$root/@pi-archimedes/core" "$root/@pi-archimedes/subagent" "$root/@pi-archimedes/footer"\n'
        'printf \'{"name":"pi-archimedes","version":"2.11.1"}\\n\' >"$root/pi-archimedes/package.json"\n'
        'printf \'{"name":"@pi-archimedes/ask","version":"2.11.1"}\\n\' >"$root/@pi-archimedes/ask/package.json"\n'
        'printf \'{"name":"@pi-archimedes/core","version":"2.11.1"}\\n\' >"$root/@pi-archimedes/core/package.json"\n'
        'printf \'{"name":"@pi-archimedes/subagent","version":"2.11.1"}\\n\' >"$root/@pi-archimedes/subagent/package.json"\n'
        'printf \'{"name":"@pi-archimedes/footer","version":"2.11.1"}\\n\' >"$root/@pi-archimedes/footer/package.json"\n'
        'printf "pi|%s\\n" "$*" >>"$PI_DEPLOY_LOG"\n',
        encoding="utf-8",
    )
    fake_patch.write_text(
        '#!/bin/sh\nprintf "patch|%s\\n" "$PI_CONFIG_DEST" >>"$PI_DEPLOY_LOG"\n',
        encoding="utf-8",
    )
    fake_pi.chmod(0o755)
    fake_patch.chmod(0o755)

    proc = run_update(
        dest,
        env_overrides={
            "PI_COMMAND": str(fake_pi),
            "PI_PACKAGE_PATCH_HELPER": str(fake_patch),
            "PI_PACKAGE_PATCH_DIR": str(langfuse_patch_dir(tmp_path)),
            "PI_DEPLOY_LOG": str(log),
        },
    )

    assert proc.returncode == 0, proc.stderr
    assert log.read_text(encoding="utf-8").splitlines() == [
        "pi|install npm:pi-archimedes@2.11.1",
        f"patch|{dest}",
    ]






@pytest.mark.parametrize("failure", ["second-move", "patch-helper", "live-check"])
def test_update_restores_stale_archimedes_after_later_failure(tmp_path, failure):
    dest = tmp_path / ".pi"
    modules = dest / "agent" / "npm" / "node_modules"
    meta = modules / "pi-archimedes"
    subagent = modules / "@pi-archimedes/subagent"
    langfuse = modules / "pi-langfuse"
    for package, name, version in (
        (meta, "pi-archimedes", "2.11.1"),
        (subagent, "@pi-archimedes/subagent", "2.11.1"),
        (langfuse, "pi-langfuse", "1.7.0"),
    ):
        package.mkdir(parents=True)
        (package / "package.json").write_text(
            json.dumps({"name": name, "version": version}),
            encoding="utf-8",
        )
        if name == "pi-langfuse" and version == "1.7.0":
            write_clean_langfuse(package)
    write_applied_archimedes(meta, subagent)
    archimedes_packages = {
        "meta": meta,
        "ask": modules / "@pi-archimedes/ask",
        "core": modules / "@pi-archimedes/core",
        "footer": modules / "@pi-archimedes/footer",
        "subagent": subagent,
    }
    stale = subagent / "src/index.ts"
    stale.write_text("const previousPatch = true;\n", encoding="utf-8")
    for label, package in archimedes_packages.items():
        (package / "old-runtime.txt").write_text(f"keep {label}\n", encoding="utf-8")
    fake_pi = tmp_path / "pi"
    fake_patch = tmp_path / "apply-patches"
    fake_pi.write_text(
        '#!/bin/sh\n'
        'root="$PI_CODING_AGENT_DIR/npm/node_modules"\n'
        'mkdir -p "$root/pi-archimedes" "$root/@pi-archimedes/ask" "$root/@pi-archimedes/core" "$root/@pi-archimedes/subagent" "$root/@pi-archimedes/footer"\n'
        'printf \'{"name":"pi-archimedes","version":"2.11.1"}\\n\' >"$root/pi-archimedes/package.json"\n'
        'printf \'{"name":"@pi-archimedes/ask","version":"2.11.1"}\\n\' >"$root/@pi-archimedes/ask/package.json"\n'
        'printf \'{"name":"@pi-archimedes/core","version":"2.11.1"}\\n\' >"$root/@pi-archimedes/core/package.json"\n'
        'printf \'{"name":"@pi-archimedes/subagent","version":"2.11.1"}\\n\' >"$root/@pi-archimedes/subagent/package.json"\n'
        'printf \'{"name":"@pi-archimedes/footer","version":"2.11.1"}\\n\' >"$root/@pi-archimedes/footer/package.json"\n'
,
        encoding="utf-8",
    )
    fake_patch.write_text(
        "#!/bin/sh\n" + ("exit 7\n" if failure == "patch-helper" else "exit 0\n"),
        encoding="utf-8",
    )
    fake_pi.chmod(0o755)
    fake_patch.chmod(0o755)

    overrides = {
        "PI_COMMAND": str(fake_pi),
        "PI_PACKAGE_PATCH_HELPER": str(fake_patch),
        "PI_PACKAGE_PATCH_DIR": str(langfuse_patch_dir(tmp_path)),
    }
    if failure == "second-move":
        fake_bin = tmp_path / "bin"
        fake_bin.mkdir()
        fake_mv = fake_bin / "mv"
        fake_mv.write_text(
            "#!/bin/sh\n"
            'case "$1" in */@pi-archimedes/subagent) exit 7;; esac\n'
            'exec /bin/mv "$@"\n',
            encoding="utf-8",
        )
        fake_mv.chmod(0o755)
        overrides["PATH"] = f"{fake_bin}:{os.environ['PATH']}"
    if failure == "live-check":
        source = config_source(tmp_path / "source")
        agnt = source / "agent/bin/agnt"
        agnt.write_text(
            '#!/bin/sh\n[ "$PI_CONFIG_DIR" != "$PI_CONFIG_DEST" ] || exit 7\nprintf "{}\\n"\n',
            encoding="utf-8",
        )
        agnt.chmod(0o755)
        overrides.update({
            "PI_CONFIG_SOURCE": str(source),
        })

    proc = run_update(dest, env_overrides=overrides)

    assert proc.returncode != 0
    assert stale.read_text(encoding="utf-8") == "const previousPatch = true;\n"
    for label, package in archimedes_packages.items():
        assert (package / "old-runtime.txt").read_text(encoding="utf-8") == f"keep {label}\n"
    assert not list((dest / "agent" / "npm").glob(".archimedes-reinstall.*"))


def test_update_dry_run_reports_package_sync_without_executing_it(tmp_path):
    dest = tmp_path / ".pi"
    missing = tmp_path / "must-not-run"

    proc = run_update(
        dest,
        "--dry-run",
        env_overrides={
            "PI_COMMAND": str(missing),
            "PI_PACKAGE_PATCH_HELPER": str(missing),
        },
    )

    assert proc.returncode == 0, proc.stderr
    assert f"PI_CODING_AGENT_DIR={dest / 'agent'}" in proc.stdout
    assert "install npm:pi-archimedes@2.11.1" in proc.stdout
    assert "install npm:@pi-archimedes/subagent@2.11.1" not in proc.stdout
    assert "install npm:pi-langfuse@1.7.0" not in proc.stdout
    assert f"PI_CONFIG_DEST={dest}" in proc.stdout


def test_update_rejects_apply_flag(tmp_path):
    proc = run_update(tmp_path / ".pi", "--apply")

    assert proc.returncode == 2
    assert "Unknown argument: --apply" in proc.stderr


def test_update_removes_stale_python_cache(tmp_path):
    dest = tmp_path / ".pi"
    stale = dest / "agent" / "skills" / "stale-skill" / "tools" / "__pycache__"
    stale.mkdir(parents=True)
    (stale / "tool.cpython-313.pyc").touch()

    proc = run_update(dest)

    assert proc.returncode == 0, proc.stderr
    assert "cannot delete non-empty directory" not in proc.stdout + proc.stderr
    assert not stale.parent.parent.exists()


def test_tracked_settings_omit_pi_managed_changelog_version():
    settings = json.loads(
        (ROOT / "pi" / "agent" / "settings.json").read_text(encoding="utf-8")
    )

    assert "lastChangelogVersion" not in settings


def test_update_dry_run_itemizes_changes_without_writing(tmp_path):
    dest = tmp_path / ".pi"
    dest.mkdir()
    (dest / "stale.txt").write_text("old", encoding="utf-8")
    proc = run_update(dest, "--dry-run")
    assert proc.returncode == 0, proc.stderr
    assert "*deleting" in proc.stdout and "stale.txt" in proc.stdout
    assert "agent/settings.json" in proc.stdout
    assert sorted(path.name for path in dest.iterdir()) == ["stale.txt"]


def test_update_is_local_even_with_langfuse_credentials(tmp_path):
    source = config_source(tmp_path / "source")
    (source / "agent/bin/agnt").write_text(
        '#!/bin/sh\n[ "$1" != langfuse ] || exit 91\nprintf "{}\\n"\n', encoding="utf-8"
    )
    dest = tmp_path / ".pi"
    credentials = dest / "agent/pi-langfuse/config.json"
    credentials.parent.mkdir(parents=True)
    content = '{"publicKey":"fake", "secretKey":"fake", "host":"https://example.invalid"}'
    credentials.write_text(content, encoding="utf-8")
    proc = run_update(dest, env_overrides={
        "PI_CONFIG_SOURCE": str(source),
        "LANGFUSE_PUBLIC_KEY": "fake", "LANGFUSE_SECRET_KEY": "fake",
        "LANGFUSE_BASE_URL": "https://example.invalid",
    })
    assert proc.returncode == 0, proc.stderr
    assert credentials.read_text(encoding="utf-8") == content


def test_update_backs_up_managed_config_and_retains_restore_command(tmp_path):
    dest = tmp_path / ".pi"
    (dest / "agent").mkdir(parents=True)
    settings = '{"lastChangelogVersion":"previous", "theme":"old"}\n'
    (dest / "agent/settings.json").write_text(settings, encoding="utf-8")
    (dest / "stale.txt").write_text("previous", encoding="utf-8")
    private_paths = ["agent/auth.json", "agent/npm/private.txt", "runtime/private.txt",
                     "agent/mcp.json", "agent/mcp-auth.json", "agent/mcp.log"]
    for name in private_paths:
        path = dest / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("private", encoding="utf-8")
    proc = run_update(dest)
    assert proc.returncode == 0, proc.stderr
    backups = list((dest / "runtime/deployment-backups").glob("*"))
    assert len(backups) == 1
    backup = backups[0]
    assert backup.stat().st_mode & 0o777 == 0o700
    assert (backup / "config/agent/settings.json").read_text() == settings
    assert (backup / "config/stale.txt").read_text() == "previous"
    assert all(not (backup / "config" / name).exists() for name in private_paths)
    assert "stale.txt" in (backup / "changes.txt").read_text()
    assert str(backup) in proc.stdout
    current = json.loads((dest / "agent/settings.json").read_text())
    current["lastChangelogVersion"] = "newer-runtime-marker"
    (dest / "agent/settings.json").write_text(json.dumps(current), encoding="utf-8")
    preview = subprocess.run(["bash", str(backup / "restore.sh")], capture_output=True, text=True, timeout=10)
    assert preview.returncode == 0, preview.stderr
    assert (dest / "agent/settings.json").read_text() != settings
    restored = subprocess.run(["bash", str(backup / "restore.sh"), "--apply"], capture_output=True, text=True, timeout=10)
    assert restored.returncode == 0, restored.stderr
    expected = {**json.loads(settings), "lastChangelogVersion": "newer-runtime-marker"}
    assert json.loads((dest / "agent/settings.json").read_text()) == expected
    assert (dest / "stale.txt").read_text() == "previous"
    assert not (dest / "agent/catalog.json").exists()
    assert all((dest / name).read_text() == "private" for name in private_paths)


def test_update_checks_source_before_destination_mutation(tmp_path):
    source = config_source(tmp_path / "source")
    (source / "agent/catalog.json").unlink()
    dest = tmp_path / ".pi"
    proc = run_update(dest, env_overrides={"PI_CONFIG_SOURCE": str(source)})
    assert proc.returncode != 0
    assert not dest.exists()


def test_update_retains_backup_when_live_check_fails(tmp_path):
    source = config_source(tmp_path / "source")
    (source / "agent/bin/agnt").write_text(
        '#!/bin/sh\n[ "$PI_CONFIG_DIR" != "$PI_CONFIG_DEST" ] || exit 7\nprintf "{}\\n"\n',
        encoding="utf-8",
    )
    dest = tmp_path / ".pi"
    proc = run_update(dest, env_overrides={"PI_CONFIG_SOURCE": str(source)})
    assert proc.returncode != 0
    assert not (dest / ".managed-by-pi-setup").exists()
    assert len(list((dest / "runtime/deployment-backups").glob("*/restore.sh"))) == 1


@pytest.mark.parametrize("nested", [False, True])
def test_update_refuses_overlapping_source_and_destination(tmp_path, nested):
    dest = tmp_path / ".pi"
    source = config_source(dest / "source" if nested else tmp_path / "source")
    if not nested:
        dest = source / ".pi"
    proc = run_update(dest, "--dry-run", env_overrides={"PI_CONFIG_SOURCE": str(source)})
    assert proc.returncode != 0
    assert "overlap" in proc.stderr


def test_update_refuses_symlinked_backup_root(tmp_path):
    dest = tmp_path / ".pi"
    dest.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (dest / "runtime").symlink_to(outside, target_is_directory=True)
    proc = run_update(dest)
    assert proc.returncode != 0
    assert not list(outside.iterdir())


def test_archimedes_pin_preserves_legacy_langfuse_declaration(tmp_path):
    dest = tmp_path / ".pi"
    modules = dest / "agent/npm/node_modules"
    meta = write_package(modules, "pi-archimedes", "pi-archimedes", "2.11.1")
    subagent = write_package(modules, "@pi-archimedes/subagent", "@pi-archimedes/subagent", "2.11.1")
    write_applied_archimedes(meta, subagent)
    manifest = dest / "agent/npm/package.json"
    manifest.write_text(json.dumps({"private": True, "dependencies": {
        "pi-archimedes": "^2.11.1", "pi-langfuse": "^1.5.10",
    }}))
    result = run_update(dest, env_overrides={"PI_COMMAND": "/usr/bin/false",
        "PI_PACKAGE_PATCH_DIR": str(langfuse_patch_dir(tmp_path))})
    assert result.returncode == 0, result.stderr
    assert json.loads(manifest.read_text())["dependencies"] == {
        "pi-archimedes": "2.11.1", "pi-langfuse": "^1.5.10",
    }
