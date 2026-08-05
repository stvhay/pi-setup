# Temporary Pi package patches

These version-locked runtime patches unblock canonical parent/subagent telemetry until upstream releases contain the fixes. Reviewed upstream branches are pinned as submodules under `forks/pi-langfuse` and `forks/pi-archimedes`; runtime patches contain only the production hunks needed by installed npm packages.

| Package | Base | Patch |
|---|---:|---|
| `pi-langfuse` | 1.5.9 | Prefer Pi's logical `SessionManager.getSessionId()` before the legacy session-file fallback. |
| `@pi-archimedes/subagent` | 1.8.3 | Return the existing ephemeral child Pi session UUID as `childSessionId`. |

Apply after Pi has installed the exact pinned packages:

```bash
scripts/apply-pi-package-patches.sh --check
scripts/apply-pi-package-patches.sh
```

`--check` is read-only. Apply is idempotent and rejects version or source-context mismatches. Remove each patch and its package pin after a verified upstream release includes the corresponding change.

No patch changes `--no-session`, persists child transcripts, or adds invocation/trace transport.
