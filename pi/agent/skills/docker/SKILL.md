---
name: docker
description: Use for Dockerfile, image, Engine, or Compose work; not Kubernetes.
---

# Docker

Build and operate the repository's actual container workflow. Prefer current Dockerfile frontend, BuildKit, Compose Specification, and `docker compose` V2 unless project evidence requires legacy behavior.

## Hard gates

- Inspect before editing or operating. Preserve project conventions and separate development from production needs.
- Never expose secrets through Dockerfile `ARG`/`ENV`, image layers, build logs, Compose YAML, committed env files, or command output. Use BuildKit secret/SSH mounts, Compose secrets, or the project's secret store.
- Treat Docker daemon access, socket mounts, `--privileged`, host PID/network namespaces, broad capabilities, and writable host mounts as host-level trust. Do not add them as shortcuts.
- Get explicit approval before deleting volumes, running broad prune commands, removing unrelated images/containers/networks, or replacing persistent data. State exact scope and recovery path.
- Do not claim readiness because a container started. Use application-level checks and evidence.
- Diagnose observed failures before changing configuration. Do not rebuild blindly.

## Discover

Start narrow and use existing scripts first:

```bash
git status --short
find . -maxdepth 4 -type f \( -iname 'Dockerfile*' -o -iname 'compose*.yml' -o -iname 'compose*.yaml' -o -iname 'docker-compose*.yml' -o -iname 'docker-compose*.yaml' -o -name '.dockerignore' -o -name 'docker-bake.hcl' \) -print | sort
rg -n 'docker( |-)?compose|docker build|buildx|hadolint|trivy|scout|cosign' . --glob '!node_modules' --glob '!vendor' --glob '!.git' 2>/dev/null || true
docker version 2>/dev/null || true
docker compose version 2>/dev/null || true
```

Read relevant Dockerfiles, Compose files, ignore files, dependency lockfiles, entrypoints, CI, and deployment scripts. Identify:

- requested target: local development, CI, single-host production, or reusable image
- build contexts, target stages, platforms, registry, and deployment consumer
- process user, ports, writable paths, signals, health endpoint, and shutdown behavior
- stateful services, named volumes, bind mounts, backups, and restore expectations
- existing validation, scanning, and release flow

## Route progressively

Open only references needed for current task:

| Need | Read |
|---|---|
| Dockerfile authoring, image size, cache, build contexts, multi-stage or multi-platform builds | `references/builds.md` |
| Compose design, daily commands, readiness, data, logs, debugging, upgrades, or cleanup | `references/compose-operations.md` |
| Runtime hardening, secrets, resource limits, CI/CD, scanning, SBOM, provenance, or production review | `references/security-delivery.md` |

For mixed work, read relevant references in that order. Recheck linked primary docs when syntax, platform support, or current image tags matter.

## Work

1. **Form evidence-based model.** Trace build, startup, readiness, networking, persistence, and deployment paths.
2. **Choose smallest fix.** Reuse current files and stack-native package/install commands. Avoid universal templates and optional infrastructure.
3. **Keep concerns separate.** Build dependencies stay in builder stages; runtime image gets only runtime artifacts. Development conveniences do not silently enter production.
4. **Preserve operability.** Main process handles signals, logs to stdout/stderr, exposes useful health state, and writes persistent data only to intentional mounts.
5. **Validate before mutation.** Render Compose before `up`; inspect planned image tags, mounts, published ports, secrets, and volume names.
6. **Run narrow verification.** Build requested target, exercise requested service path, and inspect resulting image/container state. Report unavailable daemon, credentials, registry, or platform checks as `NOT_VERIFIED`.

## Debugging order

Use current state before restart/rebuild:

```bash
docker compose config --quiet
docker compose ps --all
docker compose logs --tail=200 <service>
docker inspect --format '{{json .State}}' <container>
docker inspect --format '{{json .Mounts}}' <container>
docker events --since 10m --until 0s
docker stats --no-stream
```

Query only needed inspect fields; raw inspection can expose environment secrets. Correlate exit code, health state, OOM status, logs, mounts, network membership, DNS names, effective environment key names (never values), and rendered Compose structure. Fix root cause once, then recreate only affected services when possible.

## Verification

Choose applicable checks; do not run every command by habit:

```bash
docker compose config --quiet
docker buildx build --check -f <Dockerfile> <context>
docker buildx build --load -t <local-tag> -f <Dockerfile> <context>
docker image inspect --format '{{json (index .Config "User")}} {{json (index .Config "Entrypoint")}} {{json (index .Config "Cmd")}}' <local-tag>
docker compose up --wait <services>
docker compose ps
docker compose down                 # keeps named volumes
git diff --check
```

Also run application tests in the same image/stage used by CI when requested. Before changing production or pushing images, verify immutable tag/digest strategy, rollback image, persistent-data backup, health behavior, and registry authentication.

## Report

State:

- files and runtime objects changed
- root cause or design rationale
- verification commands and observed results
- image/tag/target tested
- persistent data and secrets impact
- remaining `NOT_VERIFIED` production, platform, registry, or recovery checks
