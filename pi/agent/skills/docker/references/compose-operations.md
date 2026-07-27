# Docker Compose and operations

Use for current Compose Specification and `docker compose` V2. Preserve legacy syntax only when project tooling is demonstrably pinned.

## Compose design

- Prefer `compose.yaml`; omit obsolete top-level `version`.
- Keep core services unprofiled. Use profiles for optional debugging, admin, observability, or one-off tools.
- Use service names for internal DNS. Publish only ports host/external clients need; bind development-only ports to loopback where appropriate.
- Declare networks only when isolation or stable topology needs them. Default network is enough for many apps.
- Use named volumes for durable container-managed state, bind mounts for intentional host-file sharing, and tmpfs for ephemeral sensitive/high-churn data.
- Mount config/read-only content read-only. Avoid mounting Docker socket; it grants control comparable to host root.
- Keep development bind mounts and hot reload out of production overrides.
- Put secrets in Compose `secrets` or external secret mechanisms. Environment variables are configuration, not safe secret storage.
- Use explicit image/build tags. Production should deploy a tested immutable image, not rebuild mutable source on host unless workflow explicitly requires it.

## Readiness and lifecycle

`depends_on` startup order is not readiness. When consumer cannot retry safely, add application-relevant healthcheck and long-form dependency:

```yaml
services:
  app:
    depends_on:
      db:
        condition: service_healthy
  db:
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 20s
```

Prefer application retry/backoff too: dependencies can fail after startup. Set stop grace period when clean shutdown takes time. Use restart policy based on desired supervision; restarts do not repair bad configuration.

## Safe daily commands

Render effective config before mutation:

```bash
docker compose config --quiet
docker compose config --services
docker compose config --images
docker compose --dry-run up -d  # when supported
```

Operate smallest scope:

```bash
docker compose up -d --build <service>
docker compose up --wait <services>
docker compose exec <service> <command>
docker compose run --rm <service> <one-off-command>
docker compose restart <service>
docker compose stop <service>
docker compose down             # named volumes remain
docker compose pull <service>
docker compose up -d --no-deps <service>
```

Know distinctions:

- `exec`: command in existing container.
- `run --rm`: new one-off container; service ports not published by default.
- `restart`: same container/config; does not apply Compose config changes.
- `up`: reconciles/recreates changed services.
- `down`: removes project containers/networks; `--volumes` also deletes declared/anonymous volumes and needs explicit approval.

Use stable project name when scripts, volume names, or concurrent environments depend on isolation.

## Debugging sequence

Do not start with `down`, rebuild, or prune; these destroy evidence or change state.

```bash
docker compose config --quiet
docker compose ps --all
docker compose logs --tail=200 --timestamps <service>
docker compose top <service>
docker inspect --format '{{json .State}}' <container>
docker inspect --format '{{json .Mounts}}' <container>
docker stats --no-stream
docker events --since 10m --until 0s
```

Use `docker compose config --no-interpolate` or targeted `config` output only when structure must be inspected; full rendered output can expose interpolated secrets. Query only required `docker inspect` fields.

Check:

1. exited/restarting/health state and exit code
2. OOM kill and CPU/memory pressure
3. effective command/entrypoint, user, working directory, and platform
4. mount source/type/permissions and free host disk
5. network membership, service DNS, listening address, and published-port binding
6. rendered environment key names and interpolation source without printing secret values
7. application logs and dependency readiness
8. host/daemon events and recent image/config changes

Common root causes:

- app listens on `127.0.0.1` inside container instead of `0.0.0.0`
- host uses `localhost` where container must use service DNS name
- bind mount hides files installed in image
- bind-mounted file ownership differs across host/container UID
- command exits after spawning child or shell fails to forward signals
- healthcheck uses absent binary, wrong internal port, or escaped variable incorrectly (`$$` for container-side expansion)
- Compose interpolation substitutes unset host variable before container starts
- architecture mismatch or stale image tag
- disk full from writable layers, logs, images, or build cache

## Data, backups, and upgrades

Before stateful-service changes:

- identify exact volume and owning service
- learn application-consistent backup/restore method; copying live database files is often unsafe
- create dated backup outside volume and verify restore in disposable project/volume
- read upstream upgrade notes and required migration hops
- record current immutable image for rollback
- update one stateful service at a time and inspect health/logs/data

Never infer that `docker compose down --volumes`, `docker volume prune`, or reinitializing empty storage is acceptable. Ask first with exact volume names and consequence.

## Maintenance

Inspect usage first:

```bash
docker system df -v
docker image ls
docker container ls -a
docker volume ls
docker buildx du
```

Prefer scoped removal with age/labels. Broad `docker system prune` can affect unrelated projects; volume pruning risks durable data. Require explicit approval and state filters. Configure bounded logging (`local` driver or rotation settings) so logs cannot exhaust disk.

## Production boundary

Compose can suit controlled single-host deployments. Use production override/config to remove source bind mounts, change port exposure, add restart/logging/resource policy, and reference prebuilt images. For multi-host scheduling, autoscaling, rolling orchestration, or strong tenant isolation, surface platform need instead of stretching Compose silently.

## Primary sources

- Compose Specification reference: https://docs.docker.com/reference/compose-file/
- Production with Compose: https://docs.docker.com/compose/how-tos/production/
- Startup order and readiness: https://docs.docker.com/compose/how-tos/startup-order/
- Profiles: https://docs.docker.com/compose/how-tos/profiles/
- Compose secrets: https://docs.docker.com/compose/how-tos/use-secrets/
- Environment-variable practices: https://docs.docker.com/compose/how-tos/environment-variables/best-practices/
- Volumes: https://docs.docker.com/engine/storage/volumes/
- Pruning: https://docs.docker.com/engine/manage-resources/pruning/
- Logging drivers: https://docs.docker.com/engine/logging/configure/
