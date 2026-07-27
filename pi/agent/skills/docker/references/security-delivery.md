# Security and delivery

Apply controls by threat model and deployment environment. Keep host, daemon, build, image, registry, runtime, and application boundaries distinct.

## Runtime hardening

Default posture where application permits:

- trusted minimal image; patched through regular rebuilds
- explicit non-root `USER`; consider rootless Docker for daemon-level risk reduction
- no `--privileged`, Docker socket, host namespaces, device access, or added capabilities without concrete need
- drop capabilities, then add only required ones
- default seccomp/AppArmor/SELinux confinement retained
- read-only root filesystem plus explicit writable volume/tmpfs paths when application supports it
- read-only mounts for config/content
- CPU and memory limits based on observed demand; reservations where platform supports them
- narrow port publication and network reachability
- bounded logs and graceful stop behavior

Never claim containers are a security boundary equivalent to virtual machines. Docker daemon access is highly privileged; protect its socket and remote API. Prefer rootless mode where compatible, but document networking/storage/cgroup tradeoffs.

## Secret handling

Keep secret lifecycle outside image and source control:

| Phase | Preferred mechanism |
|---|---|
| Build | BuildKit `--secret` or `--ssh` mount |
| Local Compose runtime | Compose secret file sourced from ignored/local secret material |
| CI | CI secret store passed to BuildKit/registry action without echo |
| Production | Deployment platform secret manager or externally managed Compose secret material |

Do not use Dockerfile `ARG`/`ENV` for secrets. Do not bake `.env`, credentials, package-manager config, cloud config, SSH keys, or registry auth into context/layers. Avoid printing full rendered config or environment when it may contain values. Rotate any secret found in history; deleting it in a later layer is insufficient.

## Supply chain

- Use trusted upstream images and registries. Review publisher, maintenance, platform support, and update cadence.
- Pin release inputs deliberately; digest pinning requires automated/manual refresh path.
- Build once, test same artifact, promote by immutable digest/tag, and retain rollback image.
- Generate SBOM and provenance attestations for published images when registry/deployment path preserves them.
- Scan source/Dockerfile and built image. Set severity/fixability policy based on exploitability and ownership, not raw count alone.
- Verify downloaded artifacts with cryptographic checksum/signature from independent trusted metadata.
- Sign images only if deployment verifies signatures and key/identity policy is operated; signature generation alone gives little protection.
- Minimize CI credentials, use short-lived identity where possible, and separate pull from push permissions.
- Do not expose untrusted pull-request secrets or privileged Docker socket/build runners.

Buildx attestations:

```bash
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --sbom=true \
  --provenance=mode=max \
  --tag <registry>/<image>:<immutable-tag> \
  --push .
```

Attestations attached to an image index normally require registry output; verify registry and consumer retain/inspect them.

## CI/CD path

Minimum useful pipeline:

1. validate Dockerfile/build checks and `docker compose config --quiet`
2. build explicit test target with cache scoped to trusted context
3. run tests against built artifact/stage
4. build release image once
5. inspect/scan image and enforce documented policy
6. publish immutable tag/digest only from trusted branch/tag
7. attach SBOM/provenance where supported
8. deploy same digest, wait for health, run smoke check
9. retain previous digest and tested rollback procedure

Avoid parallel jobs overwriting same mutable tag. Record source revision, build inputs, image digest, target platforms, scan result, and attestation result. Never treat local `--load` single-platform build as proof of multi-platform publication.

## Production review

Confirm before deployment:

- who can access daemon, registry, CI runner, and host
- image digest and rollback digest
- required host mounts/devices/capabilities and why
- secret sources, rotation owner, and leak response
- published ports, TLS termination, and network trust
- resource limits, log retention, monitoring, health, and alerting
- persistent volumes, backup consistency, restore test, and upgrade migration
- patch/rebuild cadence and vulnerability exception owner
- architecture support and runtime compatibility

Changes touching data, exposure, privileges, or secret sources need explicit impact statement and recovery plan.

## Verification

Use available project-approved tooling; do not install a scanner solely to satisfy checklist without approval.

```bash
docker buildx build --check -f <Dockerfile> <context>
docker image inspect --format '{{json (index .Config "User")}} {{json (index .Config "Entrypoint")}} {{json (index .Config "Cmd")}}' <image>
docker history <image>  # avoid --no-trunc; history can contain sensitive build arguments
docker scout cves <image>          # when Docker Scout is configured
docker scout policy <image>        # when organization policy exists
docker buildx imagetools inspect <registry-image>
```

Runtime evidence:

```bash
docker inspect --format '{{json .State}}' <container>
docker inspect --format '{{json .Mounts}}' <container>
docker inspect --format '{{json .HostConfig.CapDrop}} {{json .HostConfig.CapAdd}} {{json .HostConfig.SecurityOpt}} {{json .HostConfig.ReadonlyRootfs}}' <container>
docker stats --no-stream <container>
docker exec <container> id
docker compose ps
docker compose logs --tail=100 <service>
```

Verify actual runtime user, mounts, capabilities/security options, health, restart behavior, resource constraints, and listening ports. Never print secret values while inspecting.

## Primary sources

- Docker Engine security: https://docs.docker.com/engine/security/
- Rootless mode: https://docs.docker.com/engine/security/rootless/
- Resource constraints: https://docs.docker.com/engine/containers/resource_constraints/
- Continuous integration with Docker: https://docs.docker.com/build/ci/
- GitHub Actions build guidance: https://docs.docker.com/build/ci/github-actions/
- Build attestations: https://docs.docker.com/build/metadata/attestations/
- Docker Scout policy evaluation: https://docs.docker.com/scout/policy/
