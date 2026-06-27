# Contributing

## Workflow

Every meaningful change follows this process:

1. File or reference a GitHub issue for persistent work tracking.
2. Use `/skill:brainstorming` for non-trivial design choices.
3. Use `/skill:writing-plans` to create an implementation plan under `.pi/plans/`.
4. Implement in small, reviewable steps.
5. Use `/skill:verification-before-completion` before claiming done.
6. Use `/skill:documentation-standards` to validate docs when behavior, APIs, architecture, or workflows change.
7. Use `/skill:requesting-code-review` for non-trivial diffs.
8. Use `/skill:finishing-a-development-branch` for branch readiness before PR/merge.

## Test Commands

Document the project-specific commands here, for example:

```bash
# unit tests
<test command>

# lint/typecheck, if applicable
<lint command>
```

## Environment

This project uses direnv + Nix. After cloning:

```bash
direnv allow
```

The committed `.envrc` loads `flake.nix` and shell snippets from `.envrc.d/`.
Local-only snippets can go in `.envrc.local.d/`, which is gitignored.

## Code of Conduct

Be kind, be constructive, and assume good intent.
