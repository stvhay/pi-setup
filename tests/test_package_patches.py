from __future__ import annotations

import json
import os
import re
import stat
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "apply-pi-package-patches.sh"
UPDATE_SCRIPT = ROOT / "scripts" / "update-pi-config.sh"
PATCHES = ROOT / "patches" / "pi-packages"
SETTINGS = ROOT / "pi" / "agent" / "settings.json"
PI_README = ROOT / "pi" / "README.md"
ARCHITECTURE = ROOT / "docs" / "ARCHITECTURE.md"
GITMODULES = ROOT / ".gitmodules"
ARCHIMEDES_VENDOR = ROOT / "forks" / "pi-archimedes"
ARCHIMEDES_UPSTREAM_210 = "2ed26aa1d3301cc01a927d9409778bbd13df4798"
ARCHIMEDES_LIMITS_HEAD = "23d8fbf7381f2081806165e26d6b0962aef13ef9"
ARCHIMEDES_ONE_SHOT_HEAD = "f277470d64d014b496efe7e4ae4d57275d8e1907"
ARCHIMEDES_REPEATED_ERRORS_HEAD = "3576ddfd154fb274813a16e07607a15520ce73b7"
ARCHIMEDES_RESULT_PORTS_HEAD = "a9efbf159ee8b2717aae1df8742bd7382e97c1a3"
ARCHIMEDES_PRE_IDLE_HEAD = "1c4750ddb844cd8579f3076922603915098e9f96"
ARCHIMEDES_VENDOR_HEAD = "8590ec0e1063811f86d1417ded9c2aeb48fd73b6"
LANGFUSE_VENDOR = ROOT / "forks" / "pi-langfuse"
LANGFUSE_VENDOR_HEAD = "94fa7f0c4410ce10da1f98c8fe4b798374c8df2e"
LANGFUSE_UPSTREAM_1514 = "04d55a12556bdf4c4b8b208038198dc2fd8e571b"
LANGFUSE_PROFILE = ROOT / ".pi" / "upstream-profiles" / "github.com--gooyoung--pi-langfuse.md"
LANGFUSE_QUALITY_PORT = ROOT / ".pi" / "plans" / "2026-08-15-pi-langfuse-quality-port-contract.md"
ARCHIMEDES_PROFILE = ROOT / ".pi" / "upstream-profiles" / "github.com--danielcherubini--pi-archimedes.md"
ARCHIMEDES_RESULT_PORT = ROOT / ".pi" / "plans" / "2026-08-15-pi-archimedes-result-port-contract.md"
ARCHIMEDES_PACKAGE_PROOF = ROOT / "scripts" / "verify-pi-archimedes-package-patches.sh"
LANGFUSE_PACKAGE_PROOF = ROOT / "scripts" / "verify-pi-langfuse-package-patch.sh"


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
        json.dumps({"name": "pi-archimedes", "version": "2.1.0"}),
        encoding="utf-8",
    )
    target.write_text("export const settings = {};\n", encoding="utf-8")

    for relative, name, source, content in (
        ("@pi-archimedes/ask", "@pi-archimedes/ask", "src/index.ts", "export const ask = {};\n"),
        ("@pi-archimedes/core", "@pi-archimedes/core", "src/bus.ts", "export const bus = {};\n"),
    ):
        support = root / relative
        (support / "src").mkdir(parents=True)
        (support / "package.json").write_text(
            json.dumps({"name": name, "version": "2.1.0"}),
            encoding="utf-8",
        )
        (support / source).write_text(content, encoding="utf-8")
    return target


def _archimedes_footer(root: Path) -> Path:
    package = root / "@pi-archimedes/footer"
    target = package / "src/index.ts"
    target.parent.mkdir(parents=True)
    (package / "package.json").write_text(
        json.dumps({"name": "@pi-archimedes/footer", "version": "2.1.0"}),
        encoding="utf-8",
    )
    target.write_text("ctx.ui.setFooter;\nexport const footer = {};\n", encoding="utf-8")
    return target


def _fixture_patches(root: Path) -> Path:
    root.mkdir()
    (root / "pi-langfuse-1.5.14.patch").write_text(
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
    (root / "pi-archimedes-subagent-2.1.0.patch").write_text(
        """diff --git a/src/types.ts b/src/types.ts
--- a/src/types.ts
+++ b/src/types.ts
@@ -1 +1 @@
-export const result = {};
+export const result = { maxOutputTokens: 16384, maxProviderRequests: 1 };
""",
        encoding="utf-8",
    )
    (root / "pi-archimedes-meta-2.1.0.patch").write_text(
        """diff --git a/src/settings.ts b/src/settings.ts
--- a/src/settings.ts
+++ b/src/settings.ts
@@ -1 +1 @@
-export const settings = {};
+export const settings = { subagentMaxProviderRequests: 1 };
""",
        encoding="utf-8",
    )
    (root / "pi-archimedes-footer-2.1.0.patch").write_text(
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
    (root / "pi-archimedes-ask-2.1.0.patch").write_text(
        """diff --git a/src/index.ts b/src/index.ts
--- a/src/index.ts
+++ b/src/index.ts
@@ -1 +1 @@
-export const ask = {};
+export const ask = { hasCustomInput: customInput !== undefined ? { customInput } : {} };
""",
        encoding="utf-8",
    )
    (root / "pi-archimedes-core-2.1.0.patch").write_text(
        """diff --git a/src/bus.ts b/src/bus.ts
--- a/src/bus.ts
+++ b/src/bus.ts
@@ -1 +1 @@
-export const bus = {};
+export const bus = { ArchimedesEventPayloadMap: true, ArchimedesBus: true };
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
    langfuse = _package(package_root, "pi-langfuse", "pi-langfuse", "1.5.14", "export const nativeSession = true;\n")
    archimedes = _package(
        package_root,
        "@pi-archimedes/subagent",
        "@pi-archimedes/subagent",
        "2.1.0",
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
    assert repeated.stdout.count("already applied") == 6

    package_json = package_root / "pi-langfuse/package.json"
    package_json.write_text(json.dumps({"name": "pi-langfuse", "version": "1.5.8"}), encoding="utf-8")
    rejected = _run(package_root, patch_root, "--check")
    assert rejected.returncode != 0
    assert "expected pi-langfuse 1.5.14" in rejected.stderr


def test_package_patch_helper_rejects_partial_marker_state(tmp_path):
    package_root = tmp_path / "node_modules"
    _archimedes_footer(package_root)
    langfuse = _package(
        package_root,
        "pi-langfuse",
        "pi-langfuse",
        "1.5.14",
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
        "2.1.0",
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
        "1.5.14",
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
        "2.1.0",
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
        "1.5.14",
        'export const session = "file";\n',
    )
    archimedes = _package(
        package_root,
        "@pi-archimedes/subagent",
        "@pi-archimedes/subagent",
        "2.1.0",
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
    langfuse = _package(package_root, "pi-langfuse", "pi-langfuse", "1.5.14", 'export const session = "file";\n')
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
        "2.1.0",
        "export const result = {};\n",
    )
    _archimedes_meta(package_root)
    patch_root = _fixture_patches(tmp_path / "patches")

    rejected = _run(package_root, patch_root, "--check")

    assert rejected.returncode != 0
    assert "required source context is missing" in rejected.stderr


def test_package_patch_helper_preflights_every_package_before_mutation(tmp_path):
    package_root = tmp_path / "node_modules"
    langfuse = _package(package_root, "pi-langfuse", "pi-langfuse", "1.5.14", 'export const session = "file";\n')
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
    assert "expected @pi-archimedes/subagent 2.1.0" in rejected.stderr
    assert 'session = "file"' in langfuse.read_text(encoding="utf-8")
    assert "subagentMaxProviderRequests" not in meta.read_text(encoding="utf-8")


def test_archimedes_vendor_submodule_pins_clean_210_stack():
    head = subprocess.run(
        ["git", "-C", str(ARCHIMEDES_VENDOR), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
    )

    assert head.returncode == 0, head.stderr
    assert head.stdout.strip() == ARCHIMEDES_VENDOR_HEAD
    assert "branch = vendor/pi-setup-210" in GITMODULES.read_text(encoding="utf-8")
    base = subprocess.run(
        ["git", "-C", str(ARCHIMEDES_VENDOR), "cat-file", "-e", f"{ARCHIMEDES_UPSTREAM_210}^{{commit}}"],
        text=True,
        capture_output=True,
    )
    assert base.returncode == 0, base.stderr

    stack = (
        (ARCHIMEDES_LIMITS_HEAD, ARCHIMEDES_UPSTREAM_210),
        (ARCHIMEDES_ONE_SHOT_HEAD, ARCHIMEDES_LIMITS_HEAD),
        (ARCHIMEDES_REPEATED_ERRORS_HEAD, ARCHIMEDES_ONE_SHOT_HEAD),
        (ARCHIMEDES_RESULT_PORTS_HEAD, ARCHIMEDES_REPEATED_ERRORS_HEAD),
        (ARCHIMEDES_PRE_IDLE_HEAD, ARCHIMEDES_RESULT_PORTS_HEAD),
        (ARCHIMEDES_VENDOR_HEAD, ARCHIMEDES_PRE_IDLE_HEAD),
    )
    for expected_head, predecessor in stack:
        actual = subprocess.run(
            ["git", "-C", str(ARCHIMEDES_VENDOR), "cat-file", "-e", f"{expected_head}^{{commit}}"],
            text=True,
            capture_output=True,
        )
        assert actual.returncode == 0, actual.stderr
        parents = subprocess.run(
            ["git", "-C", str(ARCHIMEDES_VENDOR), "show", "-s", "--format=%P", expected_head],
            text=True,
            capture_output=True,
        )
        assert parents.returncode == 0, parents.stderr
        assert parents.stdout.strip() == predecessor


def test_langfuse_vendor_submodule_pins_combined_runtime_head():
    head = subprocess.run(
        ["git", "-C", str(LANGFUSE_VENDOR), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
    )

    assert head.returncode == 0, head.stderr
    assert head.stdout.strip() == LANGFUSE_VENDOR_HEAD
    assert "branch = vendor/pi-setup-1514" in GITMODULES.read_text(encoding="utf-8")
    assert subprocess.run(
        ["git", "-C", str(LANGFUSE_VENDOR), "merge-base", "--is-ancestor", LANGFUSE_UPSTREAM_1514, "HEAD"],
    ).returncode == 0
    count = subprocess.run(
        ["git", "-C", str(LANGFUSE_VENDOR), "rev-list", "--count", f"{LANGFUSE_UPSTREAM_1514}..HEAD"],
        text=True,
        capture_output=True,
    )
    assert count.returncode == 0, count.stderr
    assert count.stdout.strip() == "1"



def test_active_patch_inventory_matches_maintained_fork_projections():
    expected = {
        "pi-archimedes-ask-2.1.0.patch",
        "pi-archimedes-core-2.1.0.patch",
        "pi-archimedes-footer-2.1.0.patch",
        "pi-archimedes-meta-2.1.0.patch",
        "pi-archimedes-subagent-2.1.0.patch",
        "pi-langfuse-1.5.14.patch",
    }
    helper = SCRIPT.read_text(encoding="utf-8")
    deploy = UPDATE_SCRIPT.read_text(encoding="utf-8")
    configured = set(re.findall(r"\$PATCH_ROOT/([A-Za-z0-9._-]+\.patch)", helper))
    deployed = set(re.findall(r"\$PACKAGE_PATCH_DIR/([A-Za-z0-9._-]+\.patch)", deploy))
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))

    assert {path.name for path in PATCHES.glob("*.patch")} == expected
    assert configured == expected
    assert deployed == expected
    assert {"source": "npm:pi-archimedes@2.1.0", "extensions": []} in settings["packages"]
    assert {"source": "npm:pi-langfuse@1.5.14", "extensions": []} in settings["packages"]


def test_package_projection_docs_match_adopted_public_ports():
    architecture = ARCHITECTURE.read_text(encoding="utf-8")
    pi_readme = PI_README.read_text(encoding="utf-8")

    assert "Archimedes 2.0.1" not in architecture
    assert "Archimedes 2.1.0" in architecture
    assert "`pi-langfuse/quality` is active" in pi_readme
    assert "remains unused until `pi-rxo3.25` adopts" not in pi_readme


def test_runtime_patchset_contains_only_minimum_vendor_contract():
    langfuse = (PATCHES / "pi-langfuse-1.5.14.patch").read_text(encoding="utf-8")
    archimedes = (PATCHES / "pi-archimedes-subagent-2.1.0.patch").read_text(encoding="utf-8")
    ask = (PATCHES / "pi-archimedes-ask-2.1.0.patch").read_text(encoding="utf-8")
    core = (PATCHES / "pi-archimedes-core-2.1.0.patch").read_text(encoding="utf-8")
    footer = (PATCHES / "pi-archimedes-footer-2.1.0.patch").read_text(encoding="utf-8")
    meta = (PATCHES / "pi-archimedes-meta-2.1.0.patch").read_text(encoding="utf-8")
    archimedes_patches = archimedes + ask + core + footer + meta
    added = "\n".join(
        line[1:] for line in (langfuse + archimedes_patches).splitlines()
        if line.startswith("+") and not line.startswith("+++")
    )

    assert "ExtensionContext" not in langfuse
    assert "getSessionId" not in langfuse
    assert "getSessionFile" not in langfuse
    assert 'basename(sessionFile, ".jsonl")' not in langfuse
    assert "score.id ??= randomUUID()" not in langfuse
    assert "id?: string;" not in langfuse
    assert "diff --git a/index.ts" not in langfuse
    assert "diff --git a/package.json" in langfuse
    assert '"./quality": "./src/quality.ts"' in langfuse
    assert "diff --git a/src/quality.ts" in langfuse
    assert "createObservationCapturePort" in langfuse
    assert "createServiceEvidencePort" in langfuse
    assert "diff --git a/src/types.ts" in langfuse
    assert "toolPayloadBytesVersion" in langfuse
    assert "captureToolIoBytes" in langfuse
    assert "prepareToolPayload" in langfuse
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
    assert "maxIdleMs" in archimedes
    assert 'reason: "idle-limit"' in archimedes
    assert "tool_execution_update" in archimedes
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
    assert '"./types": "./src/types.ts"' in archimedes
    assert '"./agents": "./src/agents.ts"' in archimedes
    assert "resolveAgentModel" in archimedes
    assert "SUBAGENT_OUTPUT_CONTRACTS" in archimedes
    assert "childTrace" in archimedes
    assert "outputContract" in archimedes
    assert "customInput" in ask
    assert "ArchimedesEventPayloadMap" in core
    assert "ArchimedesBus" in core
    assert "getExtensionStatuses" in footer
    assert "truncateToWidth" in footer
    assert "subagentMaxProviderRequests" in meta
    assert "subagentMaxIdleMs" in meta
    assert "defaultLimits.maxIdleMs" in meta
    assert "DEVELOPMENT.md" not in langfuse
    assert "diff --git a/test/" not in langfuse
    assert "diff --git a/src/" in meta
    assert ".test.ts" not in archimedes_patches
    assert '"--mode", "json", "--no-session", "-p"' in archimedes
    assert "invocationId" not in added


def test_archimedes_package_proof_is_executable_and_integrity_pinned():
    assert ARCHIMEDES_PACKAGE_PROOF.stat().st_mode & stat.S_IXUSR
    proof = ARCHIMEDES_PACKAGE_PROOF.read_text(encoding="utf-8")
    for package, integrity in (
        ("pi-archimedes@2.1.0", "sha512-TitGWAXRE6W+3bXwg7pIhnoKR7w3PzXW417RGpGyUwHgFIqHi20eRDAs0TipBoDO/HAsQVcdpXjB//W9D/1zRQ=="),
        ("@pi-archimedes/ask@2.1.0", "sha512-QMA0zdARYOQHVEZrZf5/310L3qWFLoBiKtQtFcgRXLfO5HAoYcye/gTfQLdjOth71DyPHJ5Bvhza/BVMjdjduA=="),
        ("@pi-archimedes/core@2.1.0", "sha512-TiZBNrhyk8trUw3J66J78HNUEVsgIWkzvDJUqGq2hxvwCDS32FcJWn0K2wX+0Og8lWawmsot2n7lsYUn0ysocw=="),
        ("@pi-archimedes/footer@2.1.0", "sha512-Xs+5DCkRUmXabagwsR+J6UxhxK70VuEJcwq9wR72TRml0ZhZ3Ouc7cnjhxBZErAZx4Sgk8HY3QhPzKiSFZ24Og=="),
        ("@pi-archimedes/subagent@2.1.0", "sha512-Num0675GR2hWcp21r4epe7mqQDIgpMomUv55C9G1a96zv1mL9Gkv5eaSPe9iudI43j1lhdPEtcK3ObJs7tK9VA=="),
    ):
        assert package in proof
        assert integrity in proof
    assert "apply-pi-package-patches.sh\" --check" in proof
    assert "FORK_HEAD=\"8590ec0e1063811f86d1417ded9c2aeb48fd73b6\"" in proof
    assert "git ls-remote --heads" in proof
    assert "patch --force --fuzz=0 --reverse --dry-run" in proof
    assert "cmp \"$package_dir/$path\" \"$fork_dir/$path\"" in proof
    assert "production_paths" in proof
    assert "! -name '*.test.ts'" in proof
    assert "diff -qr" in proof
    assert "public-ports.test.ts" in proof
    assert "index-execute.test.ts" in proof
    assert "stream.test.ts" in proof
    assert "limits.test.ts" in proof
    assert "bus.test.ts" in proof
    assert "node_modules/.bin/tsc" in proof
    assert "const resolveModel: (name: string, cwd: string) => string | undefined" in proof
    assert "const result: SubagentResult" in proof
    assert "maxIdleMs: 7" in proof
    assert 'SubagentTerminationReason = "idle-limit"' in proof
    assert "const payloads: ArchimedesEventPayloadMap" in proof
    assert 'from "@pi-archimedes/subagent/agents"' in proof
    assert 'from "@pi-archimedes/subagent/types"' in proof
    assert 'from "@pi-archimedes/core/bus"' in proof


def test_langfuse_package_proof_is_executable_and_integrity_pinned():
    assert LANGFUSE_PACKAGE_PROOF.stat().st_mode & stat.S_IXUSR
    proof = LANGFUSE_PACKAGE_PROOF.read_text(encoding="utf-8")
    assert "pi-langfuse@1.5.14" in proof
    assert "sha512-zzQ40IMj7NrGrluzGAqB6zJ645MaqHfAMTdlsOK/fPlQywlTlgPb8Y/PyQc8asSkqWT55KMMDV+qNSKAG1zyTg==" in proof
    assert "patch --force --fuzz=0 --forward" in proof
    assert "patch --force --fuzz=0 --reverse --dry-run" in proof
    assert "test/quality.test.ts" in proof
    assert "cmp " in proof
    assert "diff -qr" in proof


def test_langfuse_quality_port_maintained_fork_gate_requires_exact_evidence():
    profile = LANGFUSE_PROFILE.read_text(encoding="utf-8")
    contract = LANGFUSE_QUALITY_PORT.read_text(encoding="utf-8")
    patch = (PATCHES / "pi-langfuse-1.5.14.patch").read_text(encoding="utf-8")

    assert '"./quality": "./src/quality.ts"' in patch
    assert "createObservationCapturePort" in patch
    assert "createServiceEvidencePort" in patch
    assert "quality_port_status: maintained-fork-verified" in profile
    assert "Q18V verifies the exact `stvhay/pi-langfuse` fork commit" in profile
    for evidence in (
        "npm_published_utc: 2026-08-13T02:02:51.103Z",
        "npm_integrity: sha512-zzQ40IMj7NrGrluzGAqB6zJ645MaqHfAMTdlsOK/fPlQywlTlgPb8Y/PyQc8asSkqWT55KMMDV+qNSKAG1zyTg==",
        "maintained_fork_base: 04d55a12556bdf4c4b8b208038198dc2fd8e571b",
        "maintained_fork_head: 94fa7f0c4410ce10da1f98c8fe4b798374c8df2e",
        "maintained_fork_branch: vendor/pi-setup-1514",
        "superproject_gitlink: 94fa7f0c4410ce10da1f98c8fe4b798374c8df2e",
        "derived_patch: patches/pi-packages/pi-langfuse-1.5.14.patch",
        "derived_patch_sha256: 27abc3cbf950ceca520dd21a2ab69ed3483bc05dea25c1c4495307d6fc2a90a5",
        "package_proof: scripts/verify-pi-langfuse-package-patch.sh",
    ):
        assert evidence in profile
    for evidence in (
        "exact npm base version",
        "reviewed maintained-fork base/head",
        "published immutable `stvhay` branch ref",
        "derived-patch provenance",
        'public package export `"./quality"`',
        "package-visible type declarations",
        "installed-package contract tests",
        "deferred epic `pi-vzqq`",
        "## Q18V maintained-fork verification record",
        "https://github.com/stvhay/pi-langfuse/commit/94fa7f0c4410ce10da1f98c8fe4b798374c8df2e",
        "`pi-langfuse/quality`",
        "reinstall `pi-langfuse@1.5.14`",
    ):
        assert evidence in contract
    assert "does not gate Q20" in contract


def test_archimedes_result_port_maintained_fork_gate_requires_exact_evidence():
    profile = ARCHIMEDES_PROFILE.read_text(encoding="utf-8")
    assert ARCHIMEDES_RESULT_PORT.exists(), "tracked pi-archimedes result port contract is required"
    contract = ARCHIMEDES_RESULT_PORT.read_text(encoding="utf-8")

    assert "result_port_status: maintained-fork-verified" in profile
    assert "Q19V verifies the exact `stvhay/pi-archimedes` stack" in profile
    for evidence in (
        "npm_pi_archimedes_published_utc: 2026-08-15T10:25:15.706Z",
        "npm_pi_archimedes_integrity: sha512-TitGWAXRE6W+3bXwg7pIhnoKR7w3PzXW417RGpGyUwHgFIqHi20eRDAs0TipBoDO/HAsQVcdpXjB//W9D/1zRQ==",
        "npm_subagent_published_utc: 2026-08-15T10:25:13.730Z",
        "npm_subagent_integrity: sha512-Num0675GR2hWcp21r4epe7mqQDIgpMomUv55C9G1a96zv1mL9Gkv5eaSPe9iudI43j1lhdPEtcK3ObJs7tK9VA==",
        "npm_core_published_utc: 2026-08-15T10:24:55.193Z",
        "npm_core_integrity: sha512-TiZBNrhyk8trUw3J66J78HNUEVsgIWkzvDJUqGq2hxvwCDS32FcJWn0K2wX+0Og8lWawmsot2n7lsYUn0ysocw==",
        "maintained_fork_base: 2ed26aa1d3301cc01a927d9409778bbd13df4798",
        "maintained_fork_result_ports: a9efbf159ee8b2717aae1df8742bd7382e97c1a3",
        "maintained_fork_head: 8590ec0e1063811f86d1417ded9c2aeb48fd73b6",
        "maintained_fork_branch: vendor/pi-setup-210",
        "superproject_gitlink: 8590ec0e1063811f86d1417ded9c2aeb48fd73b6",
        "derived_patch_meta_sha256: ec78cae488833af588bbdca7c203f3e13255d0b8333c793cb4cbc94a7e8f5215",
        "derived_patch_ask_sha256: eaa4c814f481ef95c1a95866170ec59d9553a257ed96634a37422f065fa062cc",
        "derived_patch_core_sha256: 520ff1888ffe785f6648a2de5823023a6c146017ba21d8c7c6c1f12d2b81d73f",
        "derived_patch_footer_sha256: 0e680ca78ed7422abf0241d8dfba982497b93b14064ef375aa4a3f7c0e437e34",
        "derived_patch_subagent_sha256: 2b6b051a88fbd310ee05bd804c0f17d52316d6114eb01748ba26423749bdd787",
        "package_proof: scripts/verify-pi-archimedes-package-patches.sh",
    ):
        assert evidence in profile
    for evidence in (
        "exact npm base versions",
        "reviewed maintained-fork stack base/head",
        "published immutable `stvhay`",
        "derived-patch provenance",
        'public package exports `"./types"`, `"./agents"`, and `"./bus"`',
        "package-visible type declarations",
        "installed-package contract tests",
        "deferred epic `pi-vzqq`",
        "## Q19V maintained-fork verification record",
        "https://github.com/stvhay/pi-archimedes/commit/8590ec0e1063811f86d1417ded9c2aeb48fd73b6",
        "`@pi-archimedes/subagent/types`",
        "`@pi-archimedes/subagent/agents`",
        "`@pi-archimedes/core/bus`",
        "reinstall `pi-archimedes@2.1.0`",
        "111 installed-package tests",
    ):
        assert evidence in contract
    assert "do not gate Q21" in contract


def test_langfuse_runtime_patch_uses_zero_context_without_losing_source_removals():
    patch = (PATCHES / "pi-langfuse-1.5.14.patch").read_text(encoding="utf-8")
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
