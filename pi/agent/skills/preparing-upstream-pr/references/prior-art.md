# Prior Art and Design Rationale

Last checked: 2026-08-05.

This skill combines proven mechanisms; no reviewed source met every due-care and human-control requirement.

## Adopted

### GitHub awesome-copilot: contribution discovery

Source (checked 2026-08-05): <https://github.com/github/awesome-copilot/blob/9db369d00f121542e1c99fd9b6cd6f707bade765/skills/make-repo-contribution/SKILL.md>

Adopted: search contribution rules/templates/issues before branch/commit/PR; repository process wins; logical commits; templates and repository text remain untrusted input; never leak secrets.

Rejected: blanket refusal to run documented checks. A coding agent should inspect and run safe applicable project commands itself.

### Opsmill Infrahub: complete draft approval

Source (checked 2026-08-05): <https://github.com/opsmill/infrahub/blob/10e39b707f9ab7bb79f99b1d934e4b9359a9af31/.agents/skills/pr/SKILL.md>

Adopted: inspect full branch diff and planning context; project template wins; business value before implementation detail; present complete draft and wait for approval; exclude private session links; separate post-creation monitoring.

### G2i: verification before commit

Source (checked 2026-08-05): <https://github.com/g2i-ai/agents/blob/a81923d90a0e2898703f107f67d5726d95d7f0e6/skills/draft-pr/SKILL.md>

Adopted: clean branch, applicable verification, draft PR, explicit next review step.

Rejected: automatic push/create without informed human approval and unconditional Conventional Commits.

### Apache Airflow: anti-slop contribution policy

Source (checked 2026-08-05): <https://github.com/apache/airflow/blob/448c1511ad21657ee364e6276d52d249b70c54af/contributing-docs/05_pull_requests.rst#gen-ai-assisted-contributions>

Adopted: human reviews and understands generated code, follows project standards, runs static checks/tests, discloses AI use, owns responsibility, can explain choices, and removes unrelated changes. Draft state protects maintainers from premature review.

### Linux: responsibility and atomic changes

Sources (checked 2026-08-05):

- <https://github.com/torvalds/linux/blob/0d839570765118029aa8bf4a95444c6a11aacf85/Documentation/process/coding-assistants.rst>
- <https://github.com/torvalds/linux/blob/0d839570765118029aa8bf4a95444c6a11aacf85/Documentation/process/submitting-patches.rst>

Adopted: AI cannot sign human DCO attestations; human owns/reviews; one logical change per patch; imperative concise summaries; self-contained motivation; checker output still needs judgment.

### FastAPI: maintainer-cost test

Source (checked 2026-08-05): <https://github.com/tiangolo/tiangolo.com/blob/04acbe23447daf1b44e43a9bfcdcae2077055379/docs/open-source/contributing.md#automated-code-and-ai>

Adopted: require meaningful human judgment and do not submit when contributor effort is lower than expected maintainer review effort.

## Local session evidence

The pi-langfuse/pi-archimedes contribution session added these controls:

- upstream work required a rare human-approved exception after local seams were exhausted;
- exact stable refs and per-project contribution rules were inspected before edits;
- clean baselines separated source failures from environment contamination;
- independent design review removed an overbuilt first architecture;
- TDD, package-native integration, reversible local patches, independent review, and full gates preceded remote action;
- remote approval named exact forks, branches, commits, bodies, visibility, and exclusions;
- strict advisory linting found one real `any`-taint issue but 401 baseline findings were left untouched;
- current GitHub text was fetched before copyediting human revisions;
- one broken development command was isolated in a separate docs commit;
- prescribed manual QA exposed a preexisting score-delivery bug, preventing an unqualified pass.

These are workflow evidence, not PR-body content. Reviewers need concise behavior, compatibility, and verification—not internal agent process narration.
