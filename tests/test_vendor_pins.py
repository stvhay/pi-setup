from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check-vendor-pins.sh"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
BRANCH = "vendor/test"


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def _fixture(tmp_path: Path, *, unpublished: bool) -> tuple[Path, str]:
    vendor = tmp_path / "vendor"
    vendor.mkdir()
    _git(vendor, "init", "-b", BRANCH)
    _git(vendor, "config", "user.name", "Test")
    _git(vendor, "config", "user.email", "test@example.com")
    (vendor / "vendor.txt").write_text("published\n", encoding="utf-8")
    _git(vendor, "add", "vendor.txt")
    _git(vendor, "commit", "-m", "published")
    published_pin = _git(vendor, "rev-parse", "HEAD")

    remote = tmp_path / "vendor.git"
    _git(tmp_path, "clone", "--bare", str(vendor), str(remote))

    if unpublished:
        (vendor / "vendor.txt").write_text("unpublished\n", encoding="utf-8")
        _git(vendor, "commit", "-am", "unpublished")
    pin = _git(vendor, "rev-parse", "HEAD")

    superproject = tmp_path / "superproject"
    superproject.mkdir()
    _git(superproject, "init", "-b", "main")
    _git(superproject, "config", "user.name", "Test")
    _git(superproject, "config", "user.email", "test@example.com")
    (superproject / ".gitmodules").write_text(
        f'[submodule "forks/vendor"]\n'
        "\tpath = forks/vendor\n"
        f"\turl = {remote}\n"
        f"\tbranch = {BRANCH}\n",
        encoding="utf-8",
    )
    _git(superproject, "add", ".gitmodules")
    _git(superproject, "update-index", "--add", "--cacheinfo", f"160000,{published_pin},forks/vendor")
    _git(superproject, "commit", "-m", "pin published vendor")
    if unpublished:
        _git(superproject, "update-index", "--cacheinfo", f"160000,{pin},forks/vendor")
    return superproject, pin


def _check(superproject: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=superproject,
        text=True,
        capture_output=True,
    )


def test_vendor_pin_preflight_accepts_commit_reachable_from_remote_branch(tmp_path):
    superproject, _pin = _fixture(tmp_path, unpublished=False)

    result = _check(superproject)

    assert result.returncode == 0, result.stderr
    assert "PASS: all vendor pins are published" in result.stdout


def test_vendor_pin_preflight_rejects_unpublished_commit_with_recovery_order(tmp_path):
    superproject, pin = _fixture(tmp_path, unpublished=True)

    result = _check(superproject)

    assert result.returncode != 0
    assert pin in result.stderr
    assert BRANCH in result.stderr
    assert "Publish vendor commit before committing its superproject gitlink" in result.stderr


def test_ci_checks_vendor_pins_before_initializing_submodules():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "scripts/check-vendor-pins.sh" in workflow
    assert workflow.index("scripts/check-vendor-pins.sh") < workflow.index("git submodule update --init --recursive")
