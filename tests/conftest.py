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


@pytest.fixture(autouse=True)
def isolate_provider_circuit_state(monkeypatch, tmp_path):
    monkeypatch.setenv("AGNT_PROVIDER_CIRCUIT_DIR", str(tmp_path / "provider-circuits"))


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
