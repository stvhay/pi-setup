from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "apply-pi-package-patches.sh"
PATCHES = ROOT / "patches" / "pi-packages"


def _package(root: Path, relative: str, name: str, version: str, source: str) -> Path:
    package = root / relative
    package.mkdir(parents=True)
    (package / "package.json").write_text(json.dumps({"name": name, "version": version}), encoding="utf-8")
    target = package / ("index.ts" if name == "pi-langfuse" else "src/stream.ts")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source, encoding="utf-8")
    return target


def _fixture_patches(root: Path) -> Path:
    root.mkdir()
    (root / "pi-langfuse-1.5.9.patch").write_text(
        """diff --git a/index.ts b/index.ts
--- a/index.ts
+++ b/index.ts
@@ -1 +1 @@
-export const session = \"file\";
+export const session = ctx?.sessionManager?.getSessionId?.();
""",
        encoding="utf-8",
    )
    (root / "pi-archimedes-subagent-1.8.3.patch").write_text(
        """diff --git a/src/stream.ts b/src/stream.ts
--- a/src/stream.ts
+++ b/src/stream.ts
@@ -1 +1 @@
-export const result = {};
+export const result = { childSessionId: \"child\" };
""",
        encoding="utf-8",
    )
    return root


def _run(package_root: Path, patch_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(SCRIPT), *args],
        cwd=ROOT,
        env={
            **os.environ,
            "PI_PACKAGE_ROOT": str(package_root),
            "PI_PACKAGE_PATCH_DIR": str(patch_root),
        },
        text=True,
        capture_output=True,
    )


def test_package_patch_helper_is_checked_idempotent_and_version_locked(tmp_path):
    package_root = tmp_path / "node_modules"
    langfuse = _package(package_root, "pi-langfuse", "pi-langfuse", "1.5.9", 'export const session = "file";\n')
    archimedes = _package(
        package_root,
        "@pi-archimedes/subagent",
        "@pi-archimedes/subagent",
        "1.8.3",
        "export const result = {};\n",
    )
    patch_root = _fixture_patches(tmp_path / "patches")

    checked = _run(package_root, patch_root, "--check")
    assert checked.returncode == 0, checked.stderr
    assert "pending" in checked.stdout
    assert 'session = "file"' in langfuse.read_text(encoding="utf-8")

    applied = _run(package_root, patch_root)
    assert applied.returncode == 0, applied.stderr
    assert "getSessionId?.()" in langfuse.read_text(encoding="utf-8")
    assert "childSessionId" in archimedes.read_text(encoding="utf-8")

    repeated = _run(package_root, patch_root)
    assert repeated.returncode == 0, repeated.stderr
    assert repeated.stdout.count("already applied") == 2

    package_json = package_root / "pi-langfuse/package.json"
    package_json.write_text(json.dumps({"name": "pi-langfuse", "version": "1.5.8"}), encoding="utf-8")
    rejected = _run(package_root, patch_root, "--check")
    assert rejected.returncode != 0
    assert "expected pi-langfuse 1.5.9" in rejected.stderr


def test_package_patch_helper_preflights_every_package_before_mutation(tmp_path):
    package_root = tmp_path / "node_modules"
    langfuse = _package(package_root, "pi-langfuse", "pi-langfuse", "1.5.9", 'export const session = "file";\n')
    _package(
        package_root,
        "@pi-archimedes/subagent",
        "@pi-archimedes/subagent",
        "1.8.2",
        "export const result = {};\n",
    )
    patch_root = _fixture_patches(tmp_path / "patches")

    rejected = _run(package_root, patch_root)

    assert rejected.returncode != 0
    assert "expected @pi-archimedes/subagent 1.8.3" in rejected.stderr
    assert 'session = "file"' in langfuse.read_text(encoding="utf-8")


def test_runtime_patchset_contains_only_minimum_session_contract():
    langfuse = (PATCHES / "pi-langfuse-1.5.9.patch").read_text(encoding="utf-8")
    archimedes = (PATCHES / "pi-archimedes-subagent-1.8.3.patch").read_text(encoding="utf-8")

    assert "getSessionId" in langfuse
    assert "getSessionFile" in langfuse
    assert 'basename(sessionFile, ".jsonl")' in langfuse
    assert "childSessionId" in archimedes
    assert '--no-session' not in archimedes
    assert "invocationId" not in langfuse + archimedes
    assert "traceId" not in langfuse + archimedes
