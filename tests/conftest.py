"""Load the extensionless agnt scripts as importable modules for unit tests."""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

BIN = Path(__file__).resolve().parents[1] / "pi" / "agent" / "bin"


def run_node(script: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    return subprocess.run(
        [node, "--experimental-strip-types", "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
    )


@pytest.fixture(params=["path", "system"])
def patch_implementation(request, monkeypatch, tmp_path):
    """Exercise PATH patch and the OS patch (Apple on macOS), without replacing other tools."""
    discovered = shutil.which("patch")
    candidate = Path(discovered) if request.param == "path" and discovered else Path("/usr/bin/patch")
    if not candidate.is_file():
        pytest.skip(f"patch unavailable: {candidate}")
    if request.param == "system" and discovered and candidate.resolve() == Path(discovered).resolve():
        pytest.skip("OS patch is already covered by PATH")
    bin_dir = tmp_path / "patch-bin"
    bin_dir.mkdir()
    (bin_dir / "patch").symlink_to(candidate.resolve())
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    return candidate


@pytest.fixture(autouse=True)
def isolate_provider_circuit_state(monkeypatch, tmp_path):
    monkeypatch.setenv("AGNT_PROVIDER_CIRCUIT_DIR", str(tmp_path / "provider-circuits"))


@pytest.fixture(autouse=True)
def isolate_work_lifecycle_state(agnt, monkeypatch, tmp_path):
    # Lifecycle ownership is owner-private and shared across worktrees in real
    # use. Tests must never reserve the developer's live execution checkout.
    from agnt_lib import authority, work_lifecycle

    # Session fixtures choose their own IDs. Never pair them with a real host
    # transcript inherited from the developer's Pi process.
    monkeypatch.delenv("PI_SESSION_FILE", raising=False)
    root = tmp_path.parent / f"{tmp_path.name}-lifecycle"
    monkeypatch.setattr(work_lifecycle, "runtime_store", lambda *_: work_lifecycle.LifecycleStore(root))
    private_authority = authority.AuthorityStore(tmp_path.parent / f"{tmp_path.name}-authority")
    monkeypatch.setattr(work_lifecycle, "authority_store", lambda: private_authority)


def load_script(name: str):
    loader = SourceFileLoader(name.replace("-", "_"), str(BIN / name))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def agnt():
    return load_script("agnt")


@pytest.fixture(scope="session")
def instructions():
    return load_script("agent-instructions")


@pytest.fixture(scope="session")
def common():
    sys.path.insert(0, str(BIN))
    import _agnt_common

    return _agnt_common
