# Language and Quality Checks

Use this reference only after reading upstream rules and representative code. It supplements project standards; it does not replace them.

## Precedence

1. Correctness, safety, licensing, and accessibility.
2. Upstream-required build, test, formatter, linter, type, generated-file, and manual checks.
3. Upstream style and local conventions.
4. Advisory language best practices and extra tools.

A repository-configured tool is a gate. A tool introduced only for evaluation is advisory unless the human and upstream project adopt it.

## Changed-scope method

For an advisory checker not configured upstream:

1. Run it in a temporary workspace without changing manifests or lockfiles.
2. Record tool/version/configuration.
3. Run on clean target baseline and candidate.
4. Compare total, changed-file, and changed-line findings.
5. Fix new findings in scope when they expose a concrete correctness or safety defect.
6. Do not repair baseline findings or reformat untouched code.
7. If upstream style conflicts with an advisory style rule, follow upstream style unless it creates a concrete correctness or safety defect.

Never state that a file "passes lint" when it only introduces no new findings. Say exactly which claim evidence supports.

## Subjective style assessment

Inspect enough representative code to identify patterns, usually:

- entrypoint and touched module;
- shared types and utilities;
- two nearby production implementations;
- two nearby tests;
- recent accepted commits or PRs when available.

Compare naming, control flow, type discipline, error handling, comments, formatting, test structure, API boundaries, and abstraction depth. Separate inherited debt from patch variance. Record confidence and concrete file examples in the upstream profile; keep subjective style narration out of the PR body.

## Initial language matrix

Last checked: 2026-08-05. Treat this as a routing aid, not current tool documentation; verify installed versions and project configuration before use.

Use project-installed tools first. Do not add dependencies solely for advisory analysis without approval.

| Language | Core project gates to discover | Useful advisory checks | Common scope traps |
|---|---|---|---|
| TypeScript/JavaScript | `tsc --noEmit`, package test script, configured ESLint/Biome/Oxlint, formatter | type-aware `typescript-eslint`, SonarJS, Knip, dependency-cycle tooling | strict presets create large baseline debt; tests and ambient shims need separate interpretation |
| Python | project test command, Ruff/Flake8, formatter, mypy/Pyright, packaging/build | Ruff rule expansion, Bandit, import/dead-code analysis | generated files, fixtures, type-check exclusions, environment-dependent tests |
| Go | `gofmt`, `go test ./...`, `go vet`, project linter | Staticcheck, `golangci-lint`, race detector when relevant | broad formatter churn, platform/build tags, expensive integration suites |
| Rust | `cargo fmt --check`, `cargo check`, `cargo test`, configured Clippy | stricter Clippy groups, Miri or sanitizers when relevant | workspace-wide churn, feature matrices, MSRV incompatibility |
| Shell | `bash -n`/shell parser, project tests | ShellCheck, shfmt in check mode | shell dialect assumptions and formatter-wide rewrites |
| C/C++ | project build/test matrix, configured formatter, compiler warnings | clang-tidy, sanitizers, static analyzers | toolchain/version noise, generated code, repository-specific formatting |

## TypeScript profile seed

When TypeScript style is ambiguous:

- prefer public types over local duplicate interfaces when project shims support them;
- validate values crossing `any`/`unknown` boundaries;
- use repository import order, quote, semicolon, brace, and array-type conventions;
- treat `no-floating-promises`, unsafe-any rules, unnecessary assertions, exhaustiveness, and ignored exceptions as correctness-oriented;
- treat array notation, optional stylistic rewrites, and modern-syntax preferences as advisory unless configured upstream;
- run test files with the project's runner; Node's native TypeScript stripping may not support the project's syntax or `.js` source specifiers.

Update this matrix only from verified project experience or current primary tool documentation. Include `last_checked` metadata for substantial additions.
