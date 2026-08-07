"""update-pi-config deploy safety guardrails."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "update-pi-config.sh"


def run_update(
    dest: Path, *args: str, env_overrides: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PI_CONFIG_DEST"] = str(dest)
    env["PI_COMMAND"] = "/usr/bin/true"
    env["PI_PACKAGE_PATCH_HELPER"] = "/usr/bin/true"
    env.update(env_overrides or {})
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def langfuse_patch_dir(tmp_path: Path) -> Path:
    patches = tmp_path / "patches"
    patches.mkdir()
    (patches / "pi-langfuse-1.5.9.patch").write_text(
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


def test_update_preserves_pi_managed_mutable_state(tmp_path):
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

    proc = run_update(dest)

    assert proc.returncode == 0, proc.stderr
    deployed_settings = json.loads((agent / "settings.json").read_text(encoding="utf-8"))
    source_settings = json.loads(
        (ROOT / "pi" / "agent" / "settings.json").read_text(encoding="utf-8")
    )
    assert deployed_settings["lastChangelogVersion"] == "99.0.0"
    assert deployed_settings["packages"] == source_settings["packages"]
    assert "runtimeOnly" not in deployed_settings
    assert (agent / "models-store.json").read_text(encoding="utf-8") == models_store


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
        f"pi|{dest / 'agent'}|install npm:pi-archimedes@1.8.3",
        f"pi|{dest / 'agent'}|install npm:pi-langfuse@1.5.9",
        f"patch|{dest}|",
    ]


def test_update_repairs_missing_archimedes_subagent_before_patching(tmp_path):
    dest = tmp_path / ".pi"
    log = tmp_path / "package-sync.log"
    for relative, name, version in (
        ("pi-archimedes", "pi-archimedes", "1.8.3"),
        ("pi-langfuse", "pi-langfuse", "1.5.9"),
    ):
        package = dest / "agent" / "npm" / "node_modules" / relative
        package.mkdir(parents=True)
        (package / "package.json").write_text(
            json.dumps({"name": name, "version": version}),
            encoding="utf-8",
        )
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
        "pi|install npm:pi-archimedes@1.8.3",
        f"patch|{dest}",
    ]


def test_update_skips_exact_patch_bases_before_applying_patches(tmp_path):
    dest = tmp_path / ".pi"
    log = tmp_path / "package-sync.log"
    for relative, name, version in (
        ("pi-archimedes", "pi-archimedes", "1.8.3"),
        ("@pi-archimedes/subagent", "@pi-archimedes/subagent", "1.8.3"),
        ("pi-langfuse", "pi-langfuse", "1.5.9"),
    ):
        package = dest / "agent" / "npm" / "node_modules" / relative
        package.mkdir(parents=True)
        (package / "package.json").write_text(
            json.dumps({"name": name, "version": version}),
            encoding="utf-8",
        )
    marker = dest / "agent" / "npm" / "node_modules" / "@pi-archimedes/subagent/src/index.ts"
    marker.parent.mkdir(parents=True)
    marker.write_text("const PARALLEL_OUTPUT_MAX_CHARS = 12_000;\n", encoding="utf-8")
    progress_marker = marker.parent / "types.ts"
    progress_marker.write_text(
        "interface Progress { turnTokens?: number; streamingParts?: Map<number, unknown> }\n",
        encoding="utf-8",
    )
    (marker.parent / "handlers.ts").write_text("STREAMING_OUTPUT_MAX_CHARS\n", encoding="utf-8")
    (marker.parent / "execute.ts").write_text("executionEvidence\n", encoding="utf-8")
    breaker_marker = marker.parent / "stream.ts"
    breaker_marker.write_text('const stop = { reason: "repeated-error" };\n', encoding="utf-8")
    langfuse = dest / "agent" / "npm" / "node_modules" / "pi-langfuse"
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
    assert "pi-archimedes 1.8.3: already installed" in proc.stdout
    assert "@pi-archimedes/subagent 1.8.3: already installed" in proc.stdout
    assert "pi-langfuse 1.5.9: already installed" in proc.stdout


def test_update_reinstalls_exact_archimedes_when_patch_revision_is_stale(tmp_path):
    dest = tmp_path / ".pi"
    log = tmp_path / "package-sync.log"
    for relative, name, version in (
        ("pi-archimedes", "pi-archimedes", "1.8.3"),
        ("@pi-archimedes/subagent", "@pi-archimedes/subagent", "1.8.3"),
        ("pi-langfuse", "pi-langfuse", "1.5.9"),
    ):
        package = dest / "agent" / "npm" / "node_modules" / relative
        package.mkdir(parents=True)
        (package / "package.json").write_text(
            json.dumps({"name": name, "version": version}),
            encoding="utf-8",
        )
        if name == "pi-langfuse":
            write_clean_langfuse(package)
    stale = dest / "agent" / "npm" / "node_modules" / "@pi-archimedes/subagent/src/index.ts"
    stale.parent.mkdir(parents=True)
    stale.write_text("const PARALLEL_OUTPUT_MAX_CHARS = 12_000;\n", encoding="utf-8")
    (stale.parent / "types.ts").write_text(
        "interface Progress { turnTokens?: number; streamingParts?: Map<number, unknown> }\n",
        encoding="utf-8",
    )
    (stale.parent / "handlers.ts").write_text("STREAMING_OUTPUT_MAX_CHARS\n", encoding="utf-8")
    (stale.parent / "stream.ts").write_text(
        'const stop = { reason: "repeated-error" };\n',
        encoding="utf-8",
    )
    fake_pi = tmp_path / "pi"
    fake_patch = tmp_path / "apply-patches"
    fake_pi.write_text(
        '#!/bin/sh\n'
        'root="$PI_CODING_AGENT_DIR/npm/node_modules"\n'
        'mkdir -p "$root/pi-archimedes" "$root/@pi-archimedes/subagent"\n'
        'printf \'{"name":"pi-archimedes","version":"1.8.3"}\\n\' >"$root/pi-archimedes/package.json"\n'
        'printf \'{"name":"@pi-archimedes/subagent","version":"1.8.3"}\\n\' >"$root/@pi-archimedes/subagent/package.json"\n'
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
        "pi|install npm:pi-archimedes@1.8.3",
        f"patch|{dest}",
    ]


@pytest.mark.parametrize("partial_state", ["marked", "unmarked"])
def test_update_reinstalls_exact_langfuse_when_patch_revision_is_stale(tmp_path, partial_state):
    dest = tmp_path / ".pi"
    log = tmp_path / "package-sync.log"
    for relative, name, version in (
        ("pi-archimedes", "pi-archimedes", "1.8.3"),
        ("@pi-archimedes/subagent", "@pi-archimedes/subagent", "1.8.3"),
        ("pi-langfuse", "pi-langfuse", "1.5.9"),
    ):
        package = dest / "agent" / "npm" / "node_modules" / relative
        package.mkdir(parents=True)
        (package / "package.json").write_text(
            json.dumps({"name": name, "version": version}),
            encoding="utf-8",
        )
    subagent = dest / "agent" / "npm" / "node_modules" / "@pi-archimedes/subagent/src"
    subagent.mkdir(parents=True)
    (subagent / "index.ts").write_text("PARALLEL_OUTPUT_MAX_CHARS\n", encoding="utf-8")
    (subagent / "types.ts").write_text("turnTokens\nstreamingParts\n", encoding="utf-8")
    (subagent / "handlers.ts").write_text("STREAMING_OUTPUT_MAX_CHARS\n", encoding="utf-8")
    (subagent / "execute.ts").write_text("executionEvidence\n", encoding="utf-8")
    (subagent / "stream.ts").write_text('reason: "repeated-error"\n', encoding="utf-8")
    langfuse = dest / "agent" / "npm" / "node_modules" / "pi-langfuse"
    (langfuse / "src").mkdir()
    if partial_state == "marked":
        (langfuse / "index.ts").write_text("getSessionId?.();\n", encoding="utf-8")
        (langfuse / "src/langfuse.ts").write_text(
            "score.id ??= randomUUID();\nconst MAX_INGESTION_REQUEST_BYTES = 3_000_000;\n",
            encoding="utf-8",
        )
        (langfuse / "src/types.ts").write_text("old-type\n", encoding="utf-8")
    else:
        (langfuse / "index.ts").write_text("getSessionFile?.();\n", encoding="utf-8")
        (langfuse / "src/langfuse.ts").write_text("old-runtime\n", encoding="utf-8")
        (langfuse / "src/types.ts").write_text("new-type\n", encoding="utf-8")
    fake_pi = tmp_path / "pi"
    fake_patch = tmp_path / "apply-patches"
    fake_pi.write_text(
        '#!/bin/sh\n'
        'root="$PI_CODING_AGENT_DIR/npm/node_modules/pi-langfuse"\n'
        'mkdir -p "$root"\n'
        'printf \'{"name":"pi-langfuse","version":"1.5.9"}\\n\' >"$root/package.json"\n'
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
        "pi|install npm:pi-langfuse@1.5.9",
        f"patch|{dest}",
    ]
    assert not list((dest / "agent" / "npm").glob(".langfuse-reinstall.*"))


@pytest.mark.parametrize("failure", ["install", "patch-helper", "langfuse-apply"])
def test_update_restores_stale_langfuse_after_failure(tmp_path, failure):
    dest = tmp_path / ".pi"
    modules = dest / "agent" / "npm" / "node_modules"
    for relative, name, version in (
        ("pi-archimedes", "pi-archimedes", "1.8.3"),
        ("@pi-archimedes/subagent", "@pi-archimedes/subagent", "1.8.3"),
        ("pi-langfuse", "pi-langfuse", "1.5.9"),
    ):
        package = modules / relative
        package.mkdir(parents=True)
        (package / "package.json").write_text(
            json.dumps({"name": name, "version": version}),
            encoding="utf-8",
        )
    subagent = modules / "@pi-archimedes/subagent/src"
    subagent.mkdir(parents=True)
    (subagent / "index.ts").write_text("PARALLEL_OUTPUT_MAX_CHARS\n", encoding="utf-8")
    (subagent / "types.ts").write_text("turnTokens\nstreamingParts\n", encoding="utf-8")
    (subagent / "handlers.ts").write_text("STREAMING_OUTPUT_MAX_CHARS\n", encoding="utf-8")
    (subagent / "execute.ts").write_text("executionEvidence\n", encoding="utf-8")
    (subagent / "stream.ts").write_text('reason: "repeated-error"\n', encoding="utf-8")
    langfuse = modules / "pi-langfuse"
    (langfuse / "index.ts").write_text("getSessionId?.();\n", encoding="utf-8")
    (langfuse / "src").mkdir()
    stale = langfuse / "src/langfuse.ts"
    stale.write_text(
        "score.id ??= randomUUID();\nconst MAX_INGESTION_REQUEST_BYTES = 3_000_000;\n",
        encoding="utf-8",
    )
    (langfuse / "src/types.ts").write_text("old-type\n", encoding="utf-8")
    (langfuse / "old-runtime.txt").write_text("keep me\n", encoding="utf-8")
    fake_pi = tmp_path / "pi"
    fake_patch = tmp_path / "apply-patches"
    fake_pi.write_text(
        '#!/bin/sh\n'
        + ("exit 7\n" if failure == "install" else "")
        + 'root="$PI_CODING_AGENT_DIR/npm/node_modules/pi-langfuse"\n'
        'mkdir -p "$root"\n'
        'printf \'{"name":"pi-langfuse","version":"1.5.9"}\\n\' >"$root/package.json"\n',
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
    if failure == "langfuse-apply":
        source = tmp_path / "source"
        agnt = source / "agent/bin/agnt"
        agnt.parent.mkdir(parents=True)
        (source / "agent/AGENTS.md").write_text("test config\n", encoding="utf-8")
        agnt.write_text("#!/bin/sh\nexit 7\n", encoding="utf-8")
        agnt.chmod(0o755)
        overrides.update({
            "PI_CONFIG_SOURCE": str(source),
            "LANGFUSE_PUBLIC_KEY": "test-public",
            "LANGFUSE_SECRET_KEY": "test-secret",
            "LANGFUSE_BASE_URL": "https://example.invalid",
        })

    proc = run_update(dest, env_overrides=overrides)

    assert proc.returncode != 0
    assert stale.read_text(encoding="utf-8") == (
        "score.id ??= randomUUID();\nconst MAX_INGESTION_REQUEST_BYTES = 3_000_000;\n"
    )
    assert (langfuse / "old-runtime.txt").read_text(encoding="utf-8") == "keep me\n"
    assert not list((dest / "agent" / "npm").glob(".langfuse-reinstall.*"))


@pytest.mark.parametrize("failure", ["second-move", "langfuse-install", "patch-helper", "langfuse-apply"])
def test_update_restores_stale_archimedes_after_later_failure(tmp_path, failure):
    dest = tmp_path / ".pi"
    modules = dest / "agent" / "npm" / "node_modules"
    meta = modules / "pi-archimedes"
    subagent = modules / "@pi-archimedes/subagent"
    langfuse = modules / "pi-langfuse"
    for package, name, version in (
        (meta, "pi-archimedes", "1.8.3"),
        (subagent, "@pi-archimedes/subagent", "1.8.3"),
        (langfuse, "pi-langfuse", "1.5.8" if failure == "langfuse-install" else "1.5.9"),
    ):
        package.mkdir(parents=True)
        (package / "package.json").write_text(
            json.dumps({"name": name, "version": version}),
            encoding="utf-8",
        )
        if name == "pi-langfuse" and version == "1.5.9":
            write_clean_langfuse(package)
    stale = subagent / "src/index.ts"
    stale.parent.mkdir(parents=True)
    stale.write_text("const previousPatch = true;\n", encoding="utf-8")
    (meta / "old-runtime.txt").write_text("keep me\n", encoding="utf-8")
    fake_pi = tmp_path / "pi"
    fake_patch = tmp_path / "apply-patches"
    fake_pi.write_text(
        '#!/bin/sh\n'
        'root="$PI_CODING_AGENT_DIR/npm/node_modules"\n'
        'mkdir -p "$root/pi-archimedes" "$root/@pi-archimedes/subagent"\n'
        'printf \'{"name":"pi-archimedes","version":"1.8.3"}\\n\' >"$root/pi-archimedes/package.json"\n'
        'printf \'{"name":"@pi-archimedes/subagent","version":"1.8.3"}\\n\' >"$root/@pi-archimedes/subagent/package.json"\n'
        + ('case "$*" in *pi-langfuse*) exit 7;; esac\n' if failure == "langfuse-install" else ""),
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
            f'case "$1" in *"{subagent}") exit 7;; esac\n'
            'exec /bin/mv "$@"\n',
            encoding="utf-8",
        )
        fake_mv.chmod(0o755)
        overrides["PATH"] = f"{fake_bin}:{os.environ['PATH']}"
    if failure == "langfuse-apply":
        source = tmp_path / "source"
        agnt = source / "agent/bin/agnt"
        agnt.parent.mkdir(parents=True)
        (source / "agent/AGENTS.md").write_text("test config\n", encoding="utf-8")
        agnt.write_text("#!/bin/sh\nexit 7\n", encoding="utf-8")
        agnt.chmod(0o755)
        overrides.update({
            "PI_CONFIG_SOURCE": str(source),
            "LANGFUSE_PUBLIC_KEY": "test-public",
            "LANGFUSE_SECRET_KEY": "test-secret",
            "LANGFUSE_BASE_URL": "https://example.invalid",
        })

    proc = run_update(dest, env_overrides=overrides)

    assert proc.returncode != 0
    assert stale.read_text(encoding="utf-8") == "const previousPatch = true;\n"
    assert (meta / "old-runtime.txt").read_text(encoding="utf-8") == "keep me\n"
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
    assert "install npm:pi-archimedes@1.8.3" in proc.stdout
    assert "install npm:@pi-archimedes/subagent@1.8.3" not in proc.stdout
    assert "install npm:pi-langfuse@1.5.9" in proc.stdout
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
