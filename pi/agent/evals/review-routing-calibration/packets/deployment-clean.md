# Paired review packet: deployment boundary

Review only this packet. Anchors B1–B3 are candidate review locations; an anchor may be defective or safe. Report at most two concrete Critical/Important findings. Use anchor ID as finding `id`. Do not report style or generic hardening.

## Contract

- Existing package files must remain recoverable until install, patch, and validation all succeed.
- Any install, patch, or validation helper failure restores the complete previous package; pre-commit package moves/removals succeed in this fixture.
- Post-commit backup cleanup may fail, but must not invalidate the new package; a leftover backup blocks the next deployment for operator cleanup.
- Exact clean and fully patched bases are accepted.
- Interrupted or mixed patch states are rejected and reinstalled; marker presence alone is not proof of completeness.
- In this minimal fixture, a complete package contains both `package.json` and `runtime.py`.

## Patch

```python
from pathlib import Path
import shutil
import subprocess


def patch_state(package: Path, patch_file: Path):
    # ANCHOR B2
    reverse = subprocess.run(["patch", "--force", "--fuzz=0", "--reverse", "--dry-run", "-p1"],
                             cwd=package, input=patch_file.read_bytes()).returncode
    if reverse == 0:
        return "applied"
    forward = subprocess.run(["patch", "--force", "--fuzz=0", "--dry-run", "-p1"],
                             cwd=package, input=patch_file.read_bytes()).returncode
    return "pending" if forward == 0 else "invalid"


def deploy(package: Path, backup: Path, install, apply_patch, validate):
    if backup.exists():
        raise RuntimeError("stale backup requires operator cleanup")
    shutil.move(package, backup)
    try:
        install(package)
        apply_patch(package)
        validate(package)
    except Exception:
        if package.exists():
            shutil.rmtree(package)
        if backup.exists():
            shutil.move(backup, package)
        raise
    # ANCHOR B1 — committed; backup cleanup cannot invalidate the new package.
    try:
        shutil.rmtree(backup)
    except OSError:
        pass


def validate(package: Path):
    # ANCHOR B3
    required = (package / "package.json", package / "runtime.py")
    if not all(path.is_file() for path in required):
        raise RuntimeError("incomplete package")
```

## Existing tests

```python
def test_clean_and_applied_states(clean_package, applied_package, patch_file):
    assert patch_state(clean_package, patch_file) == "pending"
    assert patch_state(applied_package, patch_file) == "applied"


def test_every_late_failure_restores_old_package(package, backup, failing_helpers):
    for helpers in failing_helpers:
        old = (package / "runtime.py").read_text()
        with pytest.raises(RuntimeError):
            deploy(package, backup, *helpers)
        assert (package / "runtime.py").read_text() == old
```

## Output

Return only one JSON object. Total response must be at most 6,000 characters.

```json
{
  "schemaVersion": 1,
  "reviewId": "case-02b",
  "scope": "boundary",
  "reviewer": {"target": "calibration-candidate", "family": "codex"},
  "findings": []
}
```

Every finding must contain `id`, `severity`, `category`, `location`, `claim`, `failureScenario`, `evidence`, and `status: "unverified"`. Use an empty `findings` array for PASS.
