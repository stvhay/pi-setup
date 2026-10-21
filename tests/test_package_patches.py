from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shlex
import stat
import subprocess
import tarfile
from pathlib import Path

import pytest


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
ARCHIMEDES_PREVIOUS_HEAD = "8590ec0e1063811f86d1417ded9c2aeb48fd73b6"
ARCHIMEDES_UPSTREAM_2111 = "a44f94267239db0ef5d36d18d93391bf9d51c182"
ARCHIMEDES_VENDOR_HEAD = "59c57a18976f0d470bae8ae6d5704c6715f06ee6"
LANGFUSE_VENDOR = ROOT / "forks" / "pi-langfuse"
LANGFUSE_VENDOR_HEAD = "0ba150f5bd38c1e282feec5a488a918e6076063b"
LANGFUSE_UPSTREAM_170 = "1c4dd956597af272d1869ce897e922d7702845fe"
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
        json.dumps({"name": "pi-archimedes", "version": "2.11.1"}),
        encoding="utf-8",
    )
    target.write_text("export const settings = {};\n", encoding="utf-8")

    for relative, name, source, content in (
        ("@pi-archimedes/ask", "@pi-archimedes/ask", "src/ipc-relay.ts", "export const ask = {};\n"),
        ("@pi-archimedes/core", "@pi-archimedes/core", "src/events.ts", "export const events = {};\n"),
    ):
        support = root / relative
        (support / "src").mkdir(parents=True)
        (support / "package.json").write_text(
            json.dumps({"name": name, "version": "2.11.1"}),
            encoding="utf-8",
        )
        (support / source).write_text(content, encoding="utf-8")
    return target


def _archimedes_footer(root: Path) -> Path:
    package = root / "@pi-archimedes/footer"
    target = package / "src/index.ts"
    target.parent.mkdir(parents=True)
    (package / "package.json").write_text(
        json.dumps({"name": "@pi-archimedes/footer", "version": "2.11.1"}),
        encoding="utf-8",
    )
    target.write_text("ctx.ui.setFooter;\nexport const footer = {};\n", encoding="utf-8")
    return target


def _fixture_patches(root: Path) -> Path:
    root.mkdir()
    (root / "pi-langfuse-1.7.0.patch").write_text(
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
    (root / "pi-archimedes-subagent-2.11.1.patch").write_text(
        """diff --git a/src/types.ts b/src/types.ts
--- a/src/types.ts
+++ b/src/types.ts
@@ -1 +1 @@
-export const result = {};
+export const result = { maxOutputTokens: 16384, maxProviderRequests: 1 };
""",
        encoding="utf-8",
    )
    (root / "pi-archimedes-meta-2.11.1.patch").write_text(
        """diff --git a/src/settings.ts b/src/settings.ts
--- a/src/settings.ts
+++ b/src/settings.ts
@@ -1 +1 @@
-export const settings = {};
+export const settings = { subagentMaxProviderRequests: 1 };
""",
        encoding="utf-8",
    )
    (root / "pi-archimedes-footer-2.11.1.patch").write_text(
        """diff --git a/src/index.ts b/src/index.ts
--- a/src/index.ts
+++ b/src/index.ts
@@ -1,2 +1,2 @@
 ctx.ui.setFooter;
-export const footer = {};
+export const footer = { INLINE_STATUS_KEYS: true };
""",
        encoding="utf-8",
    )
    (root / "pi-archimedes-ask-2.11.1.patch").write_text(
        """diff --git a/src/ipc-relay.ts b/src/ipc-relay.ts
--- a/src/ipc-relay.ts
+++ b/src/ipc-relay.ts
@@ -1 +1 @@
-export const ask = {};
+export const ask = { hasCustomInput: customInput !== undefined ? { customInput } : {} };
""",
        encoding="utf-8",
    )
    (root / "pi-archimedes-core-2.11.1.patch").write_text(
        """diff --git a/src/events.ts b/src/events.ts
--- a/src/events.ts
+++ b/src/events.ts
@@ -1 +1 @@
-export const events = {};
+export const events = { patched: true };
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


def test_package_patch_helper_is_checked_idempotent_and_version_locked(tmp_path, patch_implementation):
    package_root = tmp_path / "node_modules"
    langfuse = _package(package_root, "pi-langfuse", "pi-langfuse", "1.7.0", "export const nativeSession = true;\n")
    archimedes = _package(
        package_root,
        "@pi-archimedes/subagent",
        "@pi-archimedes/subagent",
        "2.11.1",
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
    assert "INLINE_STATUS_KEYS" in footer.read_text(encoding="utf-8")

    repeated = _run(package_root, patch_root)
    assert repeated.returncode == 0, repeated.stderr
    assert repeated.stdout.count("already applied") == 6

    package_json = package_root / "pi-langfuse/package.json"
    package_json.write_text(json.dumps({"name": "pi-langfuse", "version": "1.5.8"}), encoding="utf-8")
    rejected = _run(package_root, patch_root, "--check")
    assert rejected.returncode != 0
    assert "expected pi-langfuse 1.7.0" in rejected.stderr


def test_package_patch_helper_rejects_partial_marker_state(tmp_path):
    package_root = tmp_path / "node_modules"
    _archimedes_footer(package_root)
    langfuse = _package(
        package_root,
        "pi-langfuse",
        "pi-langfuse",
        "1.7.0",
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
        "2.11.1",
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
        "1.7.0",
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
        "2.11.1",
        "export const result = {};\n",
    )
    _archimedes_meta(package_root)
    patch_root = _fixture_patches(tmp_path / "patches")

    rejected = _run(package_root, patch_root, "--check")

    assert rejected.returncode != 0
    assert "patch does not match installed source" in rejected.stderr


@pytest.mark.parametrize("applied", [False, True])
def test_package_patch_helper_rejects_offset_patch_matches(tmp_path, patch_implementation, applied):
    package_root = tmp_path / "node_modules"
    _archimedes_footer(package_root)
    _package(
        package_root,
        "pi-langfuse",
        "pi-langfuse",
        "1.7.0",
        'export const session = "file";\n',
    )
    archimedes = _package(
        package_root,
        "@pi-archimedes/subagent",
        "@pi-archimedes/subagent",
        "2.11.1",
        "export const result = {};\n",
    )
    _archimedes_meta(package_root)
    patch_root = _fixture_patches(tmp_path / "patches")

    if applied:
        result = _run(package_root, patch_root)
        assert result.returncode == 0, result.stderr
    archimedes.write_text("unexpected-prefix\n" + archimedes.read_text(encoding="utf-8"), encoding="utf-8")
    before = {path: path.read_bytes() for path in package_root.rglob("*") if path.is_file()}

    # Both check and apply must reject drift before modifying any package.
    for args in [("--check",), ()]:
        rejected = _run(package_root, patch_root, *args)
        assert rejected.returncode != 0
        expected = "partially patched" if applied else "patch does not match installed source"
        assert expected in rejected.stderr
        assert {path: path.read_bytes() for path in package_root.rglob("*") if path.is_file()} == before


def test_package_patch_helper_rejects_missing_score_id_dependency(tmp_path):
    package_root = tmp_path / "node_modules"
    _archimedes_footer(package_root)
    langfuse = _package(package_root, "pi-langfuse", "pi-langfuse", "1.7.0", 'export const session = "file";\n')
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
        "2.11.1",
        "export const result = {};\n",
    )
    _archimedes_meta(package_root)
    patch_root = _fixture_patches(tmp_path / "patches")

    rejected = _run(package_root, patch_root, "--check")

    assert rejected.returncode != 0
    assert "required source context is missing" in rejected.stderr


def test_package_patch_helper_preflights_every_package_before_mutation(tmp_path):
    package_root = tmp_path / "node_modules"
    langfuse = _package(package_root, "pi-langfuse", "pi-langfuse", "1.7.0", 'export const session = "file";\n')
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
    assert "expected @pi-archimedes/subagent 2.11.1" in rejected.stderr
    assert 'session = "file"' in langfuse.read_text(encoding="utf-8")
    assert "subagentMaxProviderRequests" not in meta.read_text(encoding="utf-8")


def test_archimedes_vendor_submodule_pins_clean_2111_port_and_preserves_old_stack():
    head = subprocess.run(
        ["git", "-C", str(ARCHIMEDES_VENDOR), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
    )

    assert head.returncode == 0, head.stderr
    assert head.stdout.strip() == ARCHIMEDES_VENDOR_HEAD
    assert "branch = vendor/pi-setup-2111" in GITMODULES.read_text(encoding="utf-8")
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
        (ARCHIMEDES_PREVIOUS_HEAD, ARCHIMEDES_PRE_IDLE_HEAD),
        (ARCHIMEDES_VENDOR_HEAD, ARCHIMEDES_UPSTREAM_2111),
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
    assert "branch = vendor/pi-setup-170" in GITMODULES.read_text(encoding="utf-8")
    assert subprocess.run(
        ["git", "-C", str(LANGFUSE_VENDOR), "merge-base", "--is-ancestor", LANGFUSE_UPSTREAM_170, "HEAD"],
    ).returncode == 0
    count = subprocess.run(
        ["git", "-C", str(LANGFUSE_VENDOR), "rev-list", "--count", f"{LANGFUSE_UPSTREAM_170}..HEAD"],
        text=True,
        capture_output=True,
    )
    assert count.returncode == 0, count.stderr
    assert count.stdout.strip() == "1"



def test_active_patch_inventory_matches_maintained_fork_projections():
    expected = {
        "pi-archimedes-ask-2.11.1.patch",
        "pi-archimedes-core-2.11.1.patch",
        "pi-archimedes-footer-2.11.1.patch",
        "pi-archimedes-meta-2.11.1.patch",
        "pi-archimedes-subagent-2.11.1.patch",
        "pi-langfuse-1.7.0.patch",
    }
    helper = SCRIPT.read_text(encoding="utf-8")
    deploy = UPDATE_SCRIPT.read_text(encoding="utf-8")
    configured = set(re.findall(r"\$PATCH_ROOT/([A-Za-z0-9._-]+\.patch)", helper))
    deployed = set(re.findall(r"\$PACKAGE_PATCH_DIR/([A-Za-z0-9._-]+\.patch)", deploy))
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))

    assert {path.name for path in PATCHES.glob("*.patch")} == expected
    assert configured == expected
    assert deployed == expected
    assert {"source": "npm:pi-archimedes@2.11.1", "extensions": []} in settings["packages"]
    assert {"source": "npm:pi-langfuse@1.7.0", "extensions": []} in settings["packages"]


def test_package_projection_docs_match_adopted_public_ports():
    architecture = ARCHITECTURE.read_text(encoding="utf-8")
    pi_readme = PI_README.read_text(encoding="utf-8")

    assert "Archimedes 2.0.1" not in architecture
    assert "Archimedes 2.11.1" in architecture
    assert "`pi-langfuse/quality` is active" in pi_readme
    assert "remains unused until `pi-rxo3.25` adopts" not in pi_readme


def test_runtime_patchset_contains_only_minimum_vendor_contract():
    langfuse = (PATCHES / "pi-langfuse-1.7.0.patch").read_text(encoding="utf-8")
    archimedes = (PATCHES / "pi-archimedes-subagent-2.11.1.patch").read_text(encoding="utf-8")
    ask = (PATCHES / "pi-archimedes-ask-2.11.1.patch").read_text(encoding="utf-8")
    core = (PATCHES / "pi-archimedes-core-2.11.1.patch").read_text(encoding="utf-8")
    footer = (PATCHES / "pi-archimedes-footer-2.11.1.patch").read_text(encoding="utf-8")
    meta = (PATCHES / "pi-archimedes-meta-2.11.1.patch").read_text(encoding="utf-8")
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
    assert "extractUsageCount" in langfuse
    assert "cacheRead !== undefined" in langfuse
    assert "MAX_INGESTION_REQUEST_BYTES" in langfuse
    assert "scoreEventIds" in langfuse
    assert "AbortSignal.any" in langfuse
    assert "getLegacyTraceApiCapability" not in langfuse
    langfuse_added = "\n".join(line[1:] for line in langfuse.splitlines() if line.startswith("+") and not line.startswith("+++"))
    assert "runShutdownStep" not in langfuse_added
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
    assert "ArchimedesEventPayloadMap" not in core
    assert "src/bus.ts" not in core
    assert '"@earendil-works/pi-coding-agent": "1.3.0"' in core
    assert "getExtensionStatuses" in footer
    assert "wrapStatusToChunks" in footer
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
        ("pi-archimedes@2.11.1", "sha512-mtG8nkfEPDusDJgHuf72bT1CePc4TzPQchT9DCEIpbIiYQRqLE5lYMQPwYn3jq5L7OZUPQS4UzRmeYJoxYl+NQ=="),
        ("@pi-archimedes/ask@2.11.1", "sha512-Su2ck665KjXP0BxI3FmCDFHqF8quj70veXPq4XWOLm4R4YItWpUkhaa72Ff2ZzMpzbiu9X4pyKurf6BFpoGtvQ=="),
        ("@pi-archimedes/core@2.11.1", "sha512-zeiBPDLj6cb9VaFye+1YNGVf/GYH61uTp+tHD2Pwl1+IUz7TXlC7EDGpzNT+GqlkPnDr7gQOmS40HyoYzw3T0A=="),
        ("@pi-archimedes/footer@2.11.1", "sha512-K1Ic+qs7G6HmBkY4vOy4Fg9nHifboFGRKAQUXDxrJvt/NuxsXjGivRaiN0iS9aZgSzgutkoU3IpH1tzgnhrQJQ=="),
        ("@pi-archimedes/subagent@2.11.1", "sha512-5GK78g89o2FCuelZjgRulww+5M0uq0F7RkD9/iGCyvhaTT2zTwmqthVdk8ya9Wc4fA6Jpl8k3ibqr+YbMlZdcg=="),
    ):
        assert f"|{package.rsplit('@', 1)[0]}|{integrity}" in proof
        assert integrity in proof
    assert "apply-pi-package-patches.sh\" --check" in proof
    assert "FORK_HEAD=\"59c57a18976f0d470bae8ae6d5704c6715f06ee6\"" in proof
    assert "git ls-remote --heads" in proof
    assert '"$patch_bin" --verbose --force --fuzz=0 --reverse --dry-run' in proof
    assert "cmp \"$package_dir/$path\" \"$fork_dir/$path\"" in proof
    assert "production_paths" in proof
    assert "! -name '*.test.ts'" in proof
    assert "diff -qr" in proof
    assert 'cp "$FORK/packages/$package/src/"*.test.ts' in proof
    assert 'for package in subagent footer ask' in proof
    assert 'src/events.test.ts src/events-host-bus.test.ts' in proof
    assert 'PI_ARCHIMEDES_TEST_SCHEMA=' in proof
    assert 'test_subagent_reports.py' in proof
    assert '[ "$LOCAL_CANDIDATE" -eq 0 ]' in proof
    assert "node_modules/.bin/tsc" in proof
    assert "const resolveModel: (name: string, cwd: string) => string | undefined" in proof
    assert "const result: SubagentResult" in proof
    assert "maxIdleMs: 7" in proof
    assert 'SubagentTerminationReason = "idle-limit"' in proof
    assert "const events = createEventBus()" in proof
    assert 'from "@pi-archimedes/subagent/agents"' in proof
    assert 'from "@pi-archimedes/subagent/types"' in proof
    assert 'from "@pi-archimedes/core/events"' in proof


def test_langfuse_package_proof_is_executable_and_integrity_pinned():
    assert LANGFUSE_PACKAGE_PROOF.stat().st_mode & stat.S_IXUSR
    proof = LANGFUSE_PACKAGE_PROOF.read_text(encoding="utf-8")
    assert "pi-langfuse@1.7.0" in proof
    assert "sha512-dXMv4NLySMzOfIBmaSNUsu83HQNh3N4qxjgD9l5hvmWARSJ75W2YnD1dfIoRi9QUb2LnJsmSVHqJV9ENDL5K8w==" in proof
    assert "patch --force --fuzz=0 --forward" in proof
    assert '"$patch_bin" --verbose --force --fuzz=0 --reverse --dry-run' in proof
    assert "test/quality.test.ts" in proof
    assert 'FORK_HEAD="0ba150f5bd38c1e282feec5a488a918e6076063b"' in proof
    assert 'BASE_HEAD="1c4dd956597af272d1869ce897e922d7702845fe"' in proof
    for contract in ("tool", "generation", "redaction", "cache-contract", "langfuse", "managed-wrapper"):
        assert f"test/{contract}.test.ts" in proof
    assert "cmp " in proof
    assert "diff -qr" in proof


def test_langfuse_quality_port_maintained_fork_gate_requires_exact_evidence():
    profile = LANGFUSE_PROFILE.read_text(encoding="utf-8")
    contract = LANGFUSE_QUALITY_PORT.read_text(encoding="utf-8")
    patch = (PATCHES / "pi-langfuse-1.7.0.patch").read_text(encoding="utf-8")

    assert '"./quality": "./src/quality.ts"' in patch
    assert "createObservationCapturePort" in patch
    assert "createServiceEvidencePort" in patch
    assert "quality_port_status: maintained-fork-local-verified" in profile
    assert "Q18V verifies the quality-port ancestor `94fa7f0c`" in profile
    for evidence in (
        "npm_published_utc: '2026-10-08T02:13:34.481Z'",
        "npm_integrity: sha512-dXMv4NLySMzOfIBmaSNUsu83HQNh3N4qxjgD9l5hvmWARSJ75W2YnD1dfIoRi9QUb2LnJsmSVHqJV9ENDL5K8w==",
        "maintained_fork_base: 1c4dd956597af272d1869ce897e922d7702845fe",
        "maintained_fork_head: 0ba150f5bd38c1e282feec5a488a918e6076063b",
        "maintained_fork_branch: vendor/pi-setup-170",
        "superproject_gitlink: 0ba150f5bd38c1e282feec5a488a918e6076063b",
        "derived_patch: patches/pi-packages/pi-langfuse-1.7.0.patch",
        "publication_status: published",
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

    assert "result_port_status: maintained-fork-local-verified" in profile
    assert "Q19V verifies the exact `stvhay/pi-archimedes` stack" in profile
    for evidence in (
        "publication_status: published",
        "maintained_fork_base: a44f94267239db0ef5d36d18d93391bf9d51c182",
        "maintained_fork_head: 59c57a18976f0d470bae8ae6d5704c6715f06ee6",
        "maintained_fork_branch: vendor/pi-setup-2111",
        "superproject_gitlink: 59c57a18976f0d470bae8ae6d5704c6715f06ee6",
        "historical_vendor_head: 8590ec0e1063811f86d1417ded9c2aeb48fd73b6",
        "npm_meta_published_utc: '2026-10-16T15:19:01.021Z'",
        "npm_meta_integrity: sha512-mtG8nkfEPDusDJgHuf72bT1CePc4TzPQchT9DCEIpbIiYQRqLE5lYMQPwYn3jq5L7OZUPQS4UzRmeYJoxYl+NQ==",
        "npm_subagent_published_utc: '2026-10-16T15:21:23.629Z'",
        "npm_subagent_integrity: sha512-5GK78g89o2FCuelZjgRulww+5M0uq0F7RkD9/iGCyvhaTT2zTwmqthVdk8ya9Wc4fA6Jpl8k3ibqr+YbMlZdcg==",
        "npm_core_published_utc: '2026-10-16T15:19:30.406Z'",
        "npm_core_integrity: sha512-zeiBPDLj6cb9VaFye+1YNGVf/GYH61uTp+tHD2Pwl1+IUz7TXlC7EDGpzNT+GqlkPnDr7gQOmS40HyoYzw3T0A==",
        "derived_patch_meta_sha256: 44c46ab575f598effc2ca6f00d1b56e60106ab1b387e2c6ba9648c9f2ff9280c",
        "derived_patch_ask_sha256: 1e7ab9454a3fabf403654e4c377ec0f0579d14802c155a1da93c49a2b1fe9eb3",
        "derived_patch_core_sha256: cf5e116a07abbe388ceb783dcaa5269d19334c828486120b02118b83612357e6",
        "derived_patch_footer_sha256: 4508468a3eb7823c51e849002a4a637e92ef5575b748e0171482c8daccab42eb",
        "derived_patch_subagent_sha256: 9447255b8af98424151fbe1e6e4a3d7684ff9d0e7642bc25e313734b144278c2",
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


def test_projection_context_and_added_source_whitespace():
    # Unified context markers are syntax, not added source indentation.
    for path in PATCHES.glob("*.patch"):
        lines = path.read_text().splitlines()
        assert any(line.startswith(" ") for line in lines), path.name
        assert any(line.startswith("-") and not line.startswith("---") for line in lines), path.name
        for line in lines:
            if not line.startswith("+") or line.startswith("+++"):
                continue
            source = line[1:]
            assert source == source.rstrip(" \t"), (path.name, line)
            indentation = source[:len(source) - len(source.lstrip(" \t"))]
            assert " \t" not in indentation, (path.name, line)


@pytest.mark.parametrize("package", ["meta", "ask", "footer", "subagent", "langfuse"])
def test_actual_projection_source_round_trip(tmp_path, patch_implementation, package):
    """Exercise real production hunks, not simplified applicator fixtures."""
    langfuse = package == "langfuse"
    fork = LANGFUSE_VENDOR if langfuse else ARCHIMEDES_VENDOR
    base = LANGFUSE_UPSTREAM_170 if langfuse else ARCHIMEDES_UPSTREAM_2111
    prefix = "" if langfuse else ("meta" if package == "meta" else f"packages/{package}")
    patch_name = "pi-langfuse-1.7.0.patch" if langfuse else f"pi-archimedes-{package}-2.11.1.patch"
    sections = (PATCHES / patch_name).read_text().split("diff --git ")[1:]
    source_sections = [part for part in sections if shlex.split(part.splitlines()[0])[0].startswith("a/src/")]
    assert source_sections
    patch = "".join("diff --git " + part for part in source_sections)
    fixture = tmp_path / "package"
    fixture.mkdir()
    archive = subprocess.run(
        ["git", "-C", str(fork), "archive", base, "--", f"{prefix}/src".lstrip("/")],
        check=True, capture_output=True,
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as entries:
        for entry in entries.getmembers():
            if not entry.isfile():
                continue
            relative = Path(entry.name).relative_to(prefix or ".")
            assert relative.parts[0] == "src" and ".." not in relative.parts
            destination = fixture / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(entries.extractfile(entry).read())

    def snapshot():
        return {str(path.relative_to(fixture)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in fixture.rglob("*") if path.is_file()}

    original = snapshot()
    for direction in ("--forward", "--reverse"):
        result = subprocess.run(
            [str(patch_implementation), "--verbose", "--force", "--fuzz=0", direction, "-p1", "-d", str(fixture)],
            input=patch, text=True, capture_output=True, check=True,
            env={**os.environ, "LC_ALL": "C"},
        )
        assert not re.search(r"offset|fuzz", result.stdout + result.stderr, re.I)
        if direction == "--forward":
            for section in source_sections:
                relative = shlex.split(section.splitlines()[0])[1].removeprefix("b/")
                assert (fixture / relative).read_bytes() == (fork / prefix / relative).read_bytes(), relative
    restored = snapshot()
    changed = sorted(path for path in original.keys() | restored.keys() if original.get(path) != restored.get(path))
    assert not changed, f"{patch_implementation}: reverse changed {changed}"


def test_package_proofs_cover_path_and_system_patch_engines():
    for proof in (LANGFUSE_PACKAGE_PROOF, ARCHIMEDES_PACKAGE_PROOF):
        source = proof.read_text()
        assert '/usr/bin/patch' in source
        assert '"${PATCH_ENGINES[@]}"' in source
        assert '--verbose' in source
        assert 'diff -qr' in source
