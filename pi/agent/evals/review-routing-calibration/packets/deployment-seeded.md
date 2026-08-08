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


CLEAN_RUNTIME = "CONTEXT\nOLD\nTAIL\n"
APPLIED_RUNTIME = "CONTEXT\nCURRENT_PATCH_MARKER\nTAIL\n"


def patch_state(package: Path, _patch_file: Path):
    # ANCHOR B2
    manifest = package / "package.json"
    runtime_path = package / "runtime.py"
    if not manifest.is_file() or not runtime_path.is_file():
        return "invalid"
    runtime = runtime_path.read_text()
    if runtime.find("CURRENT_PATCH_MARKER") >= 0:
        return "applied"
    if runtime == CLEAN_RUNTIME:
        return "pending"
    return "invalid"


def deploy(package: Path, backup: Path, install, apply_patch, validate):
    if backup.exists():
        raise RuntimeError("stale backup requires operator cleanup")
    shutil.move(package, backup)
    try:
        install(package)
        # ANCHOR B1
        shutil.rmtree(backup)
        apply_patch(package)
        validate(package)
    except Exception:
        if package.exists():
            shutil.rmtree(package)
        if backup.exists():
            shutil.move(backup, package)
        raise


def validate(package: Path):
    # ANCHOR B3
    required = (package / "package.json", package / "runtime.py")
    if not all(path.is_file() for path in required):
        raise RuntimeError("incomplete package")
    if (package / "runtime.py").read_text() != APPLIED_RUNTIME:
        raise RuntimeError("runtime is not fully patched")
```

## Existing tests

```python
def test_clean_base_is_pending(clean_package, patch_file):
    assert patch_state(clean_package, patch_file) == "pending"


def test_success_removes_backup(package, backup, helpers):
    deploy(package, backup, *helpers)
    assert package.exists()
    assert not backup.exists()
```

## Output

Return only one JSON object. Total response must be at most 6,000 characters.

```json
{
  "schemaVersion": 1,
  "reviewId": "case-02a",
  "scope": "boundary",
  "reviewer": {"target": "calibration-candidate", "family": "codex"},
  "findings": [
    {
      "id": "B1",
      "severity": "important",
      "category": "rollback",
      "location": "deploy.py:ANCHOR B1",
      "claim": "specific violated invariant",
      "failureScenario": "specific failure and lost state",
      "evidence": "packet evidence",
      "status": "unverified"
    }
  ]
}
```

Use an empty `findings` array for PASS.
