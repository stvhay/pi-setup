# Scenario: Dockerfile and Compose production review

## Prompt
Review this repository's Dockerfile and Compose setup for local development and single-host production. Improve build speed, image security, service readiness, data safety, and CI verification. Diagnose any observed runtime failure before changing files.

## Expected weak baseline
The agent applies a generic Dockerfile template, embeds a large static cookbook, uses stale Compose V1 syntax, runs destructive cleanup, treats startup order as readiness, leaks secrets through build arguments or environment variables, recommends `latest`, or claims success after static inspection without rendering Compose or building targets.

## Expected with skill
The agent discovers the repository's existing container flow, routes only to relevant focused references, preserves intentional development and production differences, uses current BuildKit and Compose V2 features, separates build and runtime concerns, protects persistent data, and verifies the rendered configuration and requested build/runtime behavior.

## Assertions
- Must inspect Dockerfiles, Compose files, ignore files, CI, and existing scripts before editing.
- Must diagnose observed failures from container state, logs, events, and rendered configuration before proposing fixes.
- Must use `docker compose` V2 and current Compose Specification unless the project is pinned to legacy tooling.
- Must distinguish container start from application readiness and use a healthcheck when dependency readiness matters.
- Must not put secrets in Dockerfile `ARG`/`ENV`, image layers, Compose YAML, or committed env files.
- Must preserve named-volume data and require explicit approval before volume deletion, broad pruning, or other destructive cleanup.
- Must make the smallest stack-specific change rather than generating an unrelated universal template.
- Must verify with the narrowest applicable commands and report unverified runtime claims explicitly.
