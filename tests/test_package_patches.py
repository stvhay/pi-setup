from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "apply-pi-package-patches.sh"
PATCHES = ROOT / "patches" / "pi-packages"
GITMODULES = ROOT / ".gitmodules"
ARCHIMEDES_VENDOR = ROOT / "forks" / "pi-archimedes"
ARCHIMEDES_VENDOR_HEAD = "7e0e3474efe37c91a0471f3b65a37ad8a35ae78f"
LANGFUSE_VENDOR = ROOT / "forks" / "pi-langfuse"
LANGFUSE_VENDOR_HEAD = "c5da10a7cd0bced92ffc70e419d0198829a7a36c"


def _package(root: Path, relative: str, name: str, version: str, source: str) -> Path:
    package = root / relative
    package.mkdir(parents=True)
    (package / "package.json").write_text(json.dumps({"name": name, "version": version}), encoding="utf-8")
    target = package / ("index.ts" if name == "pi-langfuse" else "src/types.ts")
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
            "score.id ??= randomUUID();\n"
            "export const flush = true;\n",
            encoding="utf-8",
        )
        (package / "src/redaction.ts").write_text(
            "export const redaction = true;\n",
            encoding="utf-8",
        )
    return target


def _archimedes_meta(root: Path) -> Path:
    package = root / "pi-archimedes"
    target = package / "src/settings.ts"
    target.parent.mkdir(parents=True)
    (package / "package.json").write_text(
        json.dumps({"name": "pi-archimedes", "version": "2.0.1"}),
        encoding="utf-8",
    )
    target.write_text("export const settings = {};\n", encoding="utf-8")
    return target


def _archimedes_footer(root: Path) -> Path:
    package = root / "@pi-archimedes/footer"
    target = package / "src/index.ts"
    target.parent.mkdir(parents=True)
    (package / "package.json").write_text(
        json.dumps({"name": "@pi-archimedes/footer", "version": "2.0.1"}),
        encoding="utf-8",
    )
    target.write_text("ctx.ui.setFooter;\nexport const footer = {};\n", encoding="utf-8")
    return target


def _fixture_patches(root: Path) -> Path:
    root.mkdir()
    (root / "pi-langfuse-1.5.12.patch").write_text(
        """diff --git a/src/langfuse.ts b/src/langfuse.ts
--- a/src/langfuse.ts
+++ b/src/langfuse.ts
@@ -7,2 +7,3 @@
 score.id ??= randomUUID();
+const MAX_INGESTION_REQUEST_BYTES = 3_000_000;
 export const flush = true;
diff --git a/src/redaction.ts b/src/redaction.ts
--- a/src/redaction.ts
+++ b/src/redaction.ts
@@ -1 +1,2 @@
 export const redaction = true;
+export const MALFORMED_MEDIA_DATA_URI = \"[malformed media data URI]\";
""",
        encoding="utf-8",
    )
    (root / "pi-archimedes-subagent-2.0.1.patch").write_text(
        """diff --git a/src/types.ts b/src/types.ts
--- a/src/types.ts
+++ b/src/types.ts
@@ -1 +1 @@
-export const result = {};
+export const result = { maxOutputTokens: 16384, maxProviderRequests: 1 };
""",
        encoding="utf-8",
    )
    (root / "pi-archimedes-meta-2.0.1.patch").write_text(
        """diff --git a/src/settings.ts b/src/settings.ts
--- a/src/settings.ts
+++ b/src/settings.ts
@@ -1 +1 @@
-export const settings = {};
+export const settings = { subagentMaxProviderRequests: 1 };
""",
        encoding="utf-8",
    )
    (root / "pi-archimedes-footer-2.0.1.patch").write_text(
        """diff --git a/src/index.ts b/src/index.ts
--- a/src/index.ts
+++ b/src/index.ts
@@ -1,2 +1,2 @@
 ctx.ui.setFooter;
-export const footer = {};
+export const footer = { getExtensionStatuses: true };
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
    langfuse = _package(package_root, "pi-langfuse", "pi-langfuse", "1.5.12", "export const nativeSession = true;\n")
    archimedes = _package(
        package_root,
        "@pi-archimedes/subagent",
        "@pi-archimedes/subagent",
        "2.0.1",
        "export const result = {};\n",
    )
    meta = _archimedes_meta(package_root)
    footer = _archimedes_footer(package_root)
    patch_root = _fixture_patches(tmp_path / "patches")

    checked = _run(package_root, patch_root, "--check")
    assert checked.returncode == 0, checked.stderr
    assert "pending" in checked.stdout
    assert "nativeSession" in langfuse.read_text(encoding="utf-8")

    applied = _run(package_root, patch_root)
    assert applied.returncode == 0, applied.stderr
    assert "nativeSession" in langfuse.read_text(encoding="utf-8")
    assert "MAX_INGESTION_REQUEST_BYTES" in (langfuse.parent / "src/langfuse.ts").read_text(encoding="utf-8")
    assert "MALFORMED_MEDIA_DATA_URI" in (langfuse.parent / "src/redaction.ts").read_text(encoding="utf-8")
    assert "maxOutputTokens" in archimedes.read_text(encoding="utf-8")
    assert "maxProviderRequests" in archimedes.read_text(encoding="utf-8")
    assert "subagentMaxProviderRequests" in meta.read_text(encoding="utf-8")
    assert "getExtensionStatuses" in footer.read_text(encoding="utf-8")

    repeated = _run(package_root, patch_root)
    assert repeated.returncode == 0, repeated.stderr
    assert repeated.stdout.count("already applied") == 4

    package_json = package_root / "pi-langfuse/package.json"
    package_json.write_text(json.dumps({"name": "pi-langfuse", "version": "1.5.8"}), encoding="utf-8")
    rejected = _run(package_root, patch_root, "--check")
    assert rejected.returncode != 0
    assert "expected pi-langfuse 1.5.12" in rejected.stderr


def test_package_patch_helper_rejects_partial_marker_state(tmp_path):
    package_root = tmp_path / "node_modules"
    _archimedes_footer(package_root)
    langfuse = _package(
        package_root,
        "pi-langfuse",
        "pi-langfuse",
        "1.5.12",
        "export const session = ctx?.sessionManager?.getSessionId?.();\n",
    )
    score_source = langfuse.parent / "src/langfuse.ts"
    redaction_source = langfuse.parent / "src/redaction.ts"
    redaction_source.write_text(
        redaction_source.read_text(encoding="utf-8")
        + 'export const MALFORMED_MEDIA_DATA_URI = "[malformed media data URI]";\n',
        encoding="utf-8",
    )
    _package(
        package_root,
        "@pi-archimedes/subagent",
        "@pi-archimedes/subagent",
        "2.0.1",
        "export const result = {};\n",
    )
    _archimedes_meta(package_root)
    patch_root = _fixture_patches(tmp_path / "patches")

    rejected = _run(package_root, patch_root, "--check")

    assert rejected.returncode != 0
    assert "partially patched" in rejected.stderr
    assert "MAX_INGESTION_REQUEST_BYTES" not in score_source.read_text(encoding="utf-8")


def test_package_patch_helper_rejects_unmarked_partial_state(tmp_path):
    package_root = tmp_path / "node_modules"
    _archimedes_footer(package_root)
    langfuse = _package(
        package_root,
        "pi-langfuse",
        "pi-langfuse",
        "1.5.12",
        'export const session = "file";\n',
    )
    score_source = langfuse.parent / "src/langfuse.ts"
    score_source.write_text(
        score_source.read_text(encoding="utf-8").replace(
            "export const flush = true;",
            "const MAX_INGESTION_REQUEST_BYTES = 3_000_000;\nexport const flush = true;",
        ),
        encoding="utf-8",
    )
    _package(
        package_root,
        "@pi-archimedes/subagent",
        "@pi-archimedes/subagent",
        "2.0.1",
        "export const result = {};\n",
    )
    _archimedes_meta(package_root)
    patch_root = _fixture_patches(tmp_path / "patches")

    rejected = _run(package_root, patch_root, "--check")

    assert rejected.returncode != 0
    assert "patch does not match installed source" in rejected.stderr


def test_package_patch_helper_rejects_offset_patch_matches(tmp_path):
    package_root = tmp_path / "node_modules"
    _archimedes_footer(package_root)
    _package(
        package_root,
        "pi-langfuse",
        "pi-langfuse",
        "1.5.12",
        'export const session = "file";\n',
    )
    archimedes = _package(
        package_root,
        "@pi-archimedes/subagent",
        "@pi-archimedes/subagent",
        "2.0.1",
        "unexpected-prefix\nexport const result = {};\n",
    )
    _archimedes_meta(package_root)
    patch_root = _fixture_patches(tmp_path / "patches")

    rejected = _run(package_root, patch_root, "--check")

    assert rejected.returncode != 0
    assert "patch does not match installed source" in rejected.stderr
    assert "maxOutputTokens" not in archimedes.read_text(encoding="utf-8")


def test_package_patch_helper_rejects_missing_score_id_dependency(tmp_path):
    package_root = tmp_path / "node_modules"
    _archimedes_footer(package_root)
    langfuse = _package(package_root, "pi-langfuse", "pi-langfuse", "1.5.12", 'export const session = "file";\n')
    score_source = langfuse.parent / "src/langfuse.ts"
    score_source.write_text(
        score_source.read_text(encoding="utf-8").replace(
            "score.id ??= randomUUID();",
            "score.id = randomUUID();",
        ),
        encoding="utf-8",
    )
    _package(
        package_root,
        "@pi-archimedes/subagent",
        "@pi-archimedes/subagent",
        "2.0.1",
        "export const result = {};\n",
    )
    _archimedes_meta(package_root)
    patch_root = _fixture_patches(tmp_path / "patches")

    rejected = _run(package_root, patch_root, "--check")

    assert rejected.returncode != 0
    assert "required source context is missing" in rejected.stderr


def test_package_patch_helper_preflights_every_package_before_mutation(tmp_path):
    package_root = tmp_path / "node_modules"
    langfuse = _package(package_root, "pi-langfuse", "pi-langfuse", "1.5.12", 'export const session = "file";\n')
    _package(
        package_root,
        "@pi-archimedes/subagent",
        "@pi-archimedes/subagent",
        "2.0.0",
        "export const result = {};\n",
    )
    meta = _archimedes_meta(package_root)
    _archimedes_footer(package_root)
    patch_root = _fixture_patches(tmp_path / "patches")

    rejected = _run(package_root, patch_root)

    assert rejected.returncode != 0
    assert "expected @pi-archimedes/subagent 2.0.1" in rejected.stderr
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
    for ancestor in (
        "bdfeea3ed77392a2d02617fa1e0d4aa5fd8317e3",
        "c717d96239488a5199aa17747a4839f52cb649df",
        "61955d2e28102cdc36fc62b8b528ac4ea7174565",
    ):
        assert subprocess.run(
            ["git", "-C", str(ARCHIMEDES_VENDOR), "merge-base", "--is-ancestor", ancestor, "HEAD"],
        ).returncode == 0


def test_langfuse_vendor_submodule_pins_combined_runtime_head():
    head = subprocess.run(
        ["git", "-C", str(LANGFUSE_VENDOR), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
    )

    assert head.returncode == 0, head.stderr
    assert head.stdout.strip() == LANGFUSE_VENDOR_HEAD
    assert "branch = vendor/pi-setup-1512" in GITMODULES.read_text(encoding="utf-8")
    for ancestor in (
        "c79c527a7294e1d4b8153525d5218e87354cbcb1",
        "9c4103d5c0e704b494ed018e4b789f8c4bf64f26",
        "bcaa42a928c7df8ceecc18ececf263cbf9632300",
    ):
        assert subprocess.run(
            ["git", "-C", str(LANGFUSE_VENDOR), "merge-base", "--is-ancestor", ancestor, "HEAD"],
        ).returncode == 0


def test_runtime_patchset_contains_only_minimum_vendor_contract():
    langfuse = (PATCHES / "pi-langfuse-1.5.12.patch").read_text(encoding="utf-8")
    archimedes = (PATCHES / "pi-archimedes-subagent-2.0.1.patch").read_text(encoding="utf-8")
    footer = (PATCHES / "pi-archimedes-footer-2.0.1.patch").read_text(encoding="utf-8")
    meta = (PATCHES / "pi-archimedes-meta-2.0.1.patch").read_text(encoding="utf-8")
    added = "\n".join(
        line[1:] for line in (langfuse + archimedes + footer + meta).splitlines()
        if line.startswith("+") and not line.startswith("+++")
    )

    assert "ExtensionContext" not in langfuse
    assert "getSessionId" not in langfuse
    assert "getSessionFile" not in langfuse
    assert 'basename(sessionFile, ".jsonl")' not in langfuse
    assert "score.id ??= randomUUID()" not in langfuse
    assert "id?: string;" not in langfuse
    assert "diff --git a/index.ts" not in langfuse
    assert "diff --git a/src/types.ts" not in langfuse
    assert "MAX_INGESTION_REQUEST_BYTES" in langfuse
    assert "scoreEventIds" in langfuse
    assert "AbortSignal.any" in langfuse
    assert "getLegacyTraceApiCapability" not in langfuse
    assert "runShutdownStep" not in langfuse
    assert "MALFORMED_MEDIA_DATA_URI" in langfuse
    assert "OMITTED_MEDIA_DATA_URI" in langfuse
    assert "isLangfuseMediaDataUri" in langfuse
    assert "preserveMedia" in langfuse
    assert "observation.model = prepareRestFallbackValue" in langfuse
    assert "uploadMedia" not in langfuse
    assert "ResolvedChildExecution" in archimedes
    assert "maxProviderRequests" in archimedes
    assert "maxOutputTokens" in archimedes
    assert "PI_ARCHIMEDES_OUTPUT_LIMIT" in archimedes
    assert "isCodexResponsesPayload" in archimedes
    assert 'state.error = typeof message.errorMessage' in archimedes
    assert "workspace:*" not in archimedes
    assert "PARALLEL_OUTPUT_MAX_CHARS" in archimedes
    assert "turnTokens" in archimedes
    assert "turnCount" in archimedes
    assert "streamingParts" in archimedes
    assert "assistantMessageEvent" in archimedes
    assert "STREAMING_OUTPUT_MAX_CHARS" in archimedes
    assert "executionEvidence" in archimedes
    assert "provider: state.provider" in archimedes
    assert 'reason: "repeated-error"' in archimedes
    assert "MAX_TRACKED_TOOL_CALL_IDS" in archimedes
    assert "MAX_FINGERPRINT_DEPTH" in archimedes
    assert "MAX_FINGERPRINT_CHARS" in archimedes
    assert "json.length > MAX_FINGERPRINT_CHARS" in archimedes
    assert '"--no-tools", "--no-extensions", "--no-skills", "--no-context-files"' in archimedes
    assert '"./config": "./src/config.ts"' in archimedes
    assert "getExtensionStatuses" in footer
    assert "truncateToWidth" in footer
    assert "subagentMaxProviderRequests" in meta
    assert "DEVELOPMENT.md" not in langfuse
    assert "diff --git a/test/" not in langfuse
    assert "diff --git a/src/" in meta
    assert ".test.ts" not in archimedes + footer + meta
    assert '"--mode", "json", "--no-session", "-p"' in archimedes
    assert "invocationId" not in added


def test_langfuse_runtime_patch_uses_zero_context_without_losing_source_removals():
    patch = (PATCHES / "pi-langfuse-1.5.12.patch").read_text(encoding="utf-8")
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
    assert all(not any(line.startswith(" ") for line in hunk) for hunk in hunks)
    assert any(any(line.startswith("-") for line in hunk) for hunk in hunks)
