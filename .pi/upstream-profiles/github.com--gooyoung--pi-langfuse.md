---
profile_version: 1
repository: https://github.com/gooyoung/pi-langfuse
last_checked_utc: 2026-08-07T17:18:34Z
target_ref: v1.5.9
source_commit: 3243208ea89d6fdc2b5f0e66660a4a626880ebd0
status: current-for-target-ref
recheck_every_use:
  - permissions
  - fork-state
  - templates
  - branch-protection-and-ci
  - issue-requirements
source_files:
  - path: README.md
    sha256: a2ca04dbf6650c37890bb464a63988d73586554fa7623f259b335990ac62b706
  - path: README_CN.md
    sha256: eb47226dd64b98fb582734cb8b928994002fb053be35d8d0886846cd941712a9
  - path: AGENTS.md
    sha256: 2d0b44fb79d7814319741acd9e25cdb0d16ea559dbdda54aae0e7439e16cd8ab
  - path: DEVELOPMENT.md
    sha256: 4f466210982ef6ac900ed86a08a38be5dc2024fce93c0ba44b37b0d024bfb4e7
  - path: DEVELOPMENT_CN.md
    sha256: 065f7e8b6432341ef5c8119b3c2fd346ba7ba753842fe73938ae4018c63a0910
  - path: package.json
    sha256: 0baffc5ad02f9c053722e1be5437b8301661dd067f165f0b26cf5fc9c8d26e3b
  - path: package-lock.json
    sha256: b8856f9352f81cac3dda502cd3b371f6c386e02a85c9f879774bc2292b4d19e7
  - path: .github/workflows/publish.yml
    sha256: c5e0be88634700712947da8645490c3ec4a87e304ca9c4fde9020869fa40c672
  - path: index.ts
    sha256: 1a4f8b0c122fe0397d3c7ce95b0dc22e7c3ca296e1ca73f274c612b52a9ce89f
  - path: src/state.ts
    sha256: b1bf3e3af672c1aa1bec9166acb1f110f8552297434ee806b5a5f85bebedcd0f
  - path: src/langfuse.ts
    sha256: aa2e74e14bbe498265353c9bf50ab21334dcf88362964353db1f93b813a5f922
  - path: src/types.ts
    sha256: c99b36ed5021784fb606b780eaeeb62459f3b8b6df327b264fbb3d99e906bb69
  - path: test/index.test.ts
    sha256: e1ab7efa6ca1a73f574d499610df80507be68b87ee91a5ee552c538b8de281d3
  - path: test/state.test.ts
    sha256: 471fcaaac505569ad5d1dfaa30d786853a605948661464fc51407a0367e6944b
  - path: test/langfuse.test.ts
    sha256: fcc9d756ebaf8109f77b4d5ac99d9258b8b19ede7782cf0c75267c5e2176004b
---

# gooyoung/pi-langfuse upstream profile

## Contribution workflow

- Default branch observed: `main`; target tag matched `origin/main` when checked.
- npm project; install with `npm ci` and use package scripts.
- Required candidate checks: `npm run typecheck`, hermetic `npm test`, `npm pack --dry-run`, and diff checks.
- `DEVELOPMENT.md` and `DEVELOPMENT_CN.md` at this target ref prescribe `node --test test/*.test.ts`, which fails on the clean baseline under Node v22.22.3. `npm test` is the working package-native command. Treat correction as separate by default.
- No PR template or repository AI-contribution policy observed in checked sources.
- Mutable state rechecked 2026-08-07T17:18:34Z: upstream permission `READ`; `stvhay/pi-langfuse` exists with `ADMIN`; upstream has two open issues, no PR/issue templates observed, open PRs #13, #10, #9, and draft #6, plus fork-local drafts `stvhay/pi-langfuse#1` and `#2`; branch-protection details were unavailable through the API (HTTP 404).
- Publish workflow is release/tag driven; PR approval does not authorize release or publication.

## Policy findings

- License: root `package.json` declares MIT; no root license file was present at the target ref.
- CLA/DCO, contributor eligibility, commit signoff/signing, branch naming, and issue-first requirements: none observed in checked sources. Recheck repository settings and current GitHub metadata every use.
- Documentation: user-facing behavior is documented in paired English/Chinese READMEs; assess both when behavior changes.
- Generated artifacts: `package-lock.json` is tracked. No generated-source update rule was observed; package contents are checked with `npm pack --dry-run`.

## Coding style

**Confidence:** high

- TypeScript entrypoint with small local helpers, explicit lifecycle handlers, defensive ignored catches, semicolons, and double quotes.
- Tests use `node:test`, `assert`, synthetic IDs, fake runtime objects, handler capture, `try/finally`, and public-boundary assertions.
- Ambient Pi declarations under `types/` are the repository-compatible type seam; importing complete external Pi types caused unrelated existing errors during the reviewed contribution.
- Existing code includes `any`, unbraced one-line conditionals, mixed `Array<T>`/`T[]`, and ignored catches. Do not modernize these broadly.

## PR implications

- Prefer public Pi context types available through the ambient shim.
- Validate `unknown` at external/runtime boundaries.
- Preserve legacy behavior only where compatibility needs it; state grouping discontinuities explicitly.
- Keep repository-wide advisory strict-lint debt out of reviewer prose; required checks and changed behavior matter.
- Use direct public behavior tests rather than private-helper tests.
