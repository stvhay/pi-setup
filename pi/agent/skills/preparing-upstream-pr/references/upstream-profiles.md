# Upstream Profiles

Profiles consolidate repeat contribution knowledge without forcing every project fact into `SKILL.md`.

## Storage

Store public project facts under:

```text
.pi/upstream-profiles/<dns-hostname>--<owner>--<repo>.md
```

Use the DNS hostname (`github.com`, not `github`) so one repository maps to one canonical path. One repository gets one profile. Update it across contributions; do not create per-PR copies. Keep user-specific credentials, tokens, private URLs, and secrets out.

## Required metadata

```yaml
profile_version: 1
repository: https://<host>/<owner>/<repo>
last_checked_utc: YYYY-MM-DDTHH:MM:SSZ
target_ref: <tag-or-branch>
source_commit: <full-hash>
status: current-for-target-ref | stale
recheck_every_use:
  - permissions
  - fork-state
  - templates
  - branch-protection-and-ci
  - issue-requirements
source_files:
  - path: CONTRIBUTING.md
    sha256: <hash>
```

Also record:

- default branch and release/tag convention;
- issue-first, design, plan, CLA/DCO, AI, licensing, and contributor eligibility rules;
- branch, commit, signoff/signing, and PR-template conventions;
- package manager and locked setup;
- required focused/full/static/manual/CI checks;
- generated artifact and documentation rules;
- style assessment with concrete examples and confidence;
- known broken/stale instructions and evidence;
- last-observed permissions/fork state, clearly marked `recheck_every_use`;
- accepted upstream PR examples when they materially clarify style.

## Freshness check

Before reuse:

1. Resolve the exact target ref and current full commit.
2. Re-read every source file when target commit differs.
3. When target commit is unchanged, compare every stored source hash against the target source. A mismatch makes the profile stale.
4. Recheck permissions, fork existence, templates, branch protection/CI behavior, and open issue requirements every use; these are not stable profile facts.
5. Set `last_checked_utc` only after checks complete.
6. If network or source evidence is unavailable, mark profile `STALE` and do not claim compliance.

Time alone is not proof of staleness, but old `last_checked_utc` is a warning. Always report profile age in the local PR packet.

## Style assessment format

```markdown
## Coding style

**Confidence:** high | medium | low
**Evidence checked:** <files/commits>

- Naming: ...
- Control flow: ...
- Types/interfaces: ...
- Errors and cleanup: ...
- Tests: ...
- Formatting: ...
- Patch implications: ...
```

Follow observed style over extra advisory checks unless it creates a concrete correctness or safety defect. Upstream-configured checks remain gates.

## Broken guideline handling

Do not silently substitute a different command and claim compliance.

1. Run the documented command exactly when safe.
2. Capture the exact failure.
3. Verify the project-native replacement from package scripts/CI/source.
4. Determine whether failure exists on clean target baseline.
5. Default to a separate issue or PR.
6. A tiny correction directly blocking the contribution may be a separate commit in the same PR only after human agreement.

Record correction status in the profile so later contributions do not rediscover it, but refresh after upstream changes.
