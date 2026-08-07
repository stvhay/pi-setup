from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "apply-pi-package-patches.sh"
PATCHES = ROOT / "patches" / "pi-packages"
ARCHIMEDES_VENDOR = ROOT / "forks" / "pi-archimedes"
ARCHIMEDES_VENDOR_HEAD = "eb78e66b13d85a09b18254213a6553218a9c81d5"


def _package(root: Path, relative: str, name: str, version: str, source: str) -> Path:
    package = root / relative
    package.mkdir(parents=True)
    (package / "package.json").write_text(json.dumps({"name": name, "version": version}), encoding="utf-8")
    target = package / ("index.ts" if name == "pi-langfuse" else "src/stream.ts")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source, encoding="utf-8")
    if name == "pi-langfuse":
        score_source = package / "src/langfuse.ts"
        score_source.parent.mkdir(parents=True, exist_ok=True)
        score_source.write_text(
            'import { randomUUID } from "node:crypto";\n'
            "export const filler1 = true;\n"
            "export const filler2 = true;\n"
            "export const filler3 = true;\n"
            "export const filler4 = true;\n"
            "export const scores = [];\n"
            "export const flush = true;\n",
            encoding="utf-8",
        )
    return target


def _archimedes_meta(root: Path) -> Path:
    package = root / "pi-archimedes"
    target = package / "src/settings.ts"
    target.parent.mkdir(parents=True)
    (package / "package.json").write_text(
        json.dumps({"name": "pi-archimedes", "version": "1.8.3"}),
        encoding="utf-8",
    )
    target.write_text("export const settings = {};\n", encoding="utf-8")
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
diff --git a/src/langfuse.ts b/src/langfuse.ts
--- a/src/langfuse.ts
+++ b/src/langfuse.ts
@@ -6,2 +6,3 @@
 export const scores = [];
+export const scoreEntityId = randomUUID();
 export const flush = true;
""",
        encoding="utf-8",
    )
    (root / "pi-archimedes-subagent-1.8.3.patch").write_text(
        """diff --git a/src/stream.ts b/src/stream.ts
--- a/src/stream.ts
+++ b/src/stream.ts
@@ -1 +1 @@
-export const result = {};
+export const result = { childSessionId: \"child\", maxProviderRequests: 1 };
""",
        encoding="utf-8",
    )
    (root / "pi-archimedes-meta-1.8.3.patch").write_text(
        """diff --git a/src/settings.ts b/src/settings.ts
--- a/src/settings.ts
+++ b/src/settings.ts
@@ -1 +1 @@
-export const settings = {};
+export const settings = { subagentMaxProviderRequests: 1 };
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
    meta = _archimedes_meta(package_root)
    patch_root = _fixture_patches(tmp_path / "patches")

    checked = _run(package_root, patch_root, "--check")
    assert checked.returncode == 0, checked.stderr
    assert "pending" in checked.stdout
    assert 'session = "file"' in langfuse.read_text(encoding="utf-8")

    applied = _run(package_root, patch_root)
    assert applied.returncode == 0, applied.stderr
    assert "getSessionId?.()" in langfuse.read_text(encoding="utf-8")
    assert "childSessionId" in archimedes.read_text(encoding="utf-8")
    assert "maxProviderRequests" in archimedes.read_text(encoding="utf-8")
    assert "subagentMaxProviderRequests" in meta.read_text(encoding="utf-8")

    repeated = _run(package_root, patch_root)
    assert repeated.returncode == 0, repeated.stderr
    assert repeated.stdout.count("already applied") == 3

    package_json = package_root / "pi-langfuse/package.json"
    package_json.write_text(json.dumps({"name": "pi-langfuse", "version": "1.5.8"}), encoding="utf-8")
    rejected = _run(package_root, patch_root, "--check")
    assert rejected.returncode != 0
    assert "expected pi-langfuse 1.5.9" in rejected.stderr


def test_package_patch_helper_rejects_partial_marker_state(tmp_path):
    package_root = tmp_path / "node_modules"
    langfuse = _package(
        package_root,
        "pi-langfuse",
        "pi-langfuse",
        "1.5.9",
        "export const session = ctx?.sessionManager?.getSessionId?.();\n",
    )
    score_source = langfuse.parent / "src/langfuse.ts"
    _package(
        package_root,
        "@pi-archimedes/subagent",
        "@pi-archimedes/subagent",
        "1.8.3",
        "export const result = {};\n",
    )
    _archimedes_meta(package_root)
    patch_root = _fixture_patches(tmp_path / "patches")

    rejected = _run(package_root, patch_root, "--check")

    assert rejected.returncode != 0
    assert "partially patched" in rejected.stderr
    assert "scoreEntityId" not in score_source.read_text(encoding="utf-8")


def test_package_patch_helper_rejects_missing_score_id_dependency(tmp_path):
    package_root = tmp_path / "node_modules"
    langfuse = _package(package_root, "pi-langfuse", "pi-langfuse", "1.5.9", 'export const session = "file";\n')
    score_source = langfuse.parent / "src/langfuse.ts"
    score_source.write_text(
        score_source.read_text(encoding="utf-8").replace(
            'import { randomUUID } from "node:crypto";',
            'import { randomUuid } from "node:crypto";',
        ),
        encoding="utf-8",
    )
    _package(
        package_root,
        "@pi-archimedes/subagent",
        "@pi-archimedes/subagent",
        "1.8.3",
        "export const result = {};\n",
    )
    _archimedes_meta(package_root)
    patch_root = _fixture_patches(tmp_path / "patches")

    rejected = _run(package_root, patch_root, "--check")

    assert rejected.returncode != 0
    assert "required source context is missing" in rejected.stderr


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
    meta = _archimedes_meta(package_root)
    patch_root = _fixture_patches(tmp_path / "patches")

    rejected = _run(package_root, patch_root)

    assert rejected.returncode != 0
    assert "expected @pi-archimedes/subagent 1.8.3" in rejected.stderr
    assert 'session = "file"' in langfuse.read_text(encoding="utf-8")
    assert "subagentMaxProviderRequests" not in meta.read_text(encoding="utf-8")


def test_archimedes_vendor_submodule_pins_combined_runtime_head():
    head = subprocess.run(
        ["git", "-C", str(ARCHIMEDES_VENDOR), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
    )

    assert head.returncode == 0, head.stderr
    assert head.stdout.strip() == ARCHIMEDES_VENDOR_HEAD
    assert subprocess.run(
        ["git", "-C", str(ARCHIMEDES_VENDOR), "merge-base", "--is-ancestor", "c27561d", "HEAD"],
    ).returncode == 0


def test_runtime_patchset_contains_only_minimum_vendor_contract():
    langfuse = (PATCHES / "pi-langfuse-1.5.9.patch").read_text(encoding="utf-8")
    archimedes = (PATCHES / "pi-archimedes-subagent-1.8.3.patch").read_text(encoding="utf-8")
    meta = (PATCHES / "pi-archimedes-meta-1.8.3.patch").read_text(encoding="utf-8")
    added = "\n".join(
        line[1:] for line in (langfuse + archimedes + meta).splitlines()
        if line.startswith("+") and not line.startswith("+++")
    )

    assert "ExtensionContext" in langfuse
    assert "getSessionId" in langfuse
    assert "getSessionFile" in langfuse
    assert 'basename(sessionFile, ".jsonl")' in langfuse
    assert "score.id ??= randomUUID()" in langfuse
    assert "id?: string;" in langfuse
    assert "childSessionId" in archimedes
    assert "ResolvedChildExecution" in archimedes
    assert "maxProviderRequests" in archimedes
    assert "PARALLEL_OUTPUT_MAX_CHARS" in archimedes
    assert "subagentMaxProviderRequests" in meta
    assert "DEVELOPMENT.md" not in langfuse
    assert "diff --git a/test/" not in langfuse
    assert "diff --git a/src/" in meta
    assert ".test.ts" not in archimedes + meta
    assert '"--mode", "json", "--no-session", "-p"' in archimedes
    assert "invocationId" not in added
    assert "traceId" not in added


def test_langfuse_runtime_patch_hunks_verify_source_context():
    patch = (PATCHES / "pi-langfuse-1.5.9.patch").read_text(encoding="utf-8")
    hunks: list[list[str]] = []
    current: list[str] | None = None
    for line in patch.splitlines():
        if line.startswith("@@"):
            current = []
            hunks.append(current)
        elif line.startswith("diff --git"):
            current = None
        elif current is not None:
            current.append(line)

    assert hunks
    assert all(any(line.startswith((" ", "-")) for line in hunk) for hunk in hunks)
