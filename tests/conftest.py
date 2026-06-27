"""Load the extensionless agnt scripts as importable modules for unit tests."""

from __future__ import annotations

import importlib.util
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

BIN = Path(__file__).resolve().parents[1] / "pi" / "agent" / "bin"


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
