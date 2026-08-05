# Temporary Pi package patches

These version-locked runtime patches unblock canonical parent/subagent telemetry until upstream releases contain the fixes. Reviewed upstream branches are pinned as submodules under `forks/pi-langfuse` and `forks/pi-archimedes`; runtime patches contain only the production hunks needed by installed npm packages. `forks/pi-langfuse` tracks temporary branch `vendor/pi-setup`, which combines upstream PRs [#9](https://github.com/gooyoung/pi-langfuse/pull/9) and [#10](https://github.com/gooyoung/pi-langfuse/pull/10) without rewriting either PR branch.

| Package | Base | Patch |
|---|---:|---|
| `pi-langfuse` | 1.5.9 | Prefer Pi's logical `SessionManager.getSessionId()` before the legacy session-file fallback and assign stable entity IDs to queued scores. |
| `@pi-archimedes/subagent` | 1.8.3 | Return the existing ephemeral child Pi session UUID as `childSessionId`. |

Apply after Pi has installed the exact pinned packages:

```bash
scripts/apply-pi-package-patches.sh --check
scripts/apply-pi-package-patches.sh
```

`--check` is read-only. Apply is idempotent and rejects version, source-context, or incomplete-patch mismatches. Apply is not filesystem-transactional: after an interrupted write or permission failure, reinstall the exact pinned packages before checking and applying again. Remove each patch and its package pin after a verified upstream release includes the corresponding change.

No patch changes `--no-session`, persists child transcripts, or adds invocation/trace transport.
