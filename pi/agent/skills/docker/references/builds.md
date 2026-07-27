# Dockerfiles and builds

Use for authoring/reviewing Dockerfiles and BuildKit workflows. Adapt examples to repository stack and lockfiles; do not replace working stack-specific behavior with generic templates.

## Design checklist

### Base and stages

- Start from trusted, maintained images. Choose smallest base compatible with required libc, certificates, timezone data, native modules, and debugging needs.
- Use multi-stage builds when compilation, test tools, package managers, or source need not ship at runtime.
- Name stages and build a test stage in CI before production stage.
- Pin deliberate versions. For releases, immutable digests maximize reproducibility, but require an update process so security fixes still arrive.
- Rebuild regularly and intentionally refresh base images (`--pull`) rather than assuming immutable images self-update.
- Prefer one clear application process. Use exec-form `ENTRYPOINT`/`CMD`; ensure wrappers use `exec` and forward signals.
- Set explicit `WORKDIR`. Create and switch to non-root runtime user after privileged setup. Match ownership during `COPY` when useful.
- Copy only runtime artifacts into final stage. Do not ship compilers, test data, package caches, credentials, or unnecessary shells.

### Context and layers

- Keep context small with `.dockerignore`; exclude VCS data, local dependencies, build output, credentials, editor files, tests/docs when runtime does not need them.
- Copy dependency manifests and lockfiles before frequently changing source. Use deterministic install mode (`npm ci`, frozen/locked equivalents).
- Combine package index update, install, and cleanup in one `RUN` when using distro package managers.
- Prefer `COPY` for local files. Use `ADD` only when its URL, Git, checksum, or archive behavior is intentional.
- Do not add layers solely to delete secrets or large files copied earlier; deletion does not remove bytes from previous layers.

### BuildKit

Use current frontend where needed:

```dockerfile
# syntax=docker/dockerfile:1
```

Cache package downloads without storing them in image layers:

```dockerfile
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --require-hashes -r requirements.txt
```

Use secret or SSH mounts, never secret `ARG`/`ENV`:

```dockerfile
RUN --mount=type=secret,id=npmrc,target=/root/.npmrc npm ci
RUN --mount=type=ssh git clone git@github.com:org/private-repo.git
```

Pass them from trusted client/CI secret storage:

```bash
docker buildx build --secret id=npmrc,src="$HOME/.npmrc" .
docker buildx build --ssh default .
```

For CI/cache sharing, use Buildx cache exporters/importers only when chosen backend is access-controlled and cache lifecycle is understood. Never place secrets in cache keys or exported layers.

### Cross-platform

- Declare `--platform` only when needed; avoid hardcoding host architecture.
- Use `BUILDPLATFORM` for native builder tools and `TARGETOS`/`TARGETARCH` for cross-compilation where stack supports it.
- Test each published platform. A manifest existing does not prove binaries run there.
- Push multi-platform output to registry or use suitable exporter; `--load` generally targets local single-platform image store.

## Review traps

- `latest` or floating tags in a release path without update/rollback policy.
- Package installation without lockfile/frozen mode.
- Full source copied before dependency installation, invalidating cache.
- Secret values in `ARG`, `ENV`, `RUN`, copied config, shell history, or build output.
- Runtime as root without demonstrated need.
- `curl | sh`, unverified remote downloads, or imported signing keys without fingerprint/checksum verification.
- `chmod 777`, broad ownership changes, privileged ports, or writable filesystem used as convenience fixes.
- Healthcheck requiring tools absent from final image.
- `EXPOSE` mistaken for published port or access control.
- `HEALTHCHECK` testing process existence instead of useful application readiness.
- Shell-form command swallowing signals; wrapper not using `exec`.
- Image size optimized at cost of compatibility, patchability, or incident diagnosis without evidence.

## Verification

```bash
# Parse and apply built-in Dockerfile checks without producing image.
docker buildx build --check -f <Dockerfile> <context>

# Build explicit stage/platform and show plain logs when diagnosing cache.
docker buildx build --progress=plain --target <stage> -f <Dockerfile> <context>

# Build local runtime image when daemon supports it.
docker buildx build --load -t <tag> -f <Dockerfile> <context>
docker image inspect --format '{{json (index .Config "User")}} {{json (index .Config "Entrypoint")}} {{json (index .Config "Cmd")}}' <tag>
docker history <tag>  # avoid --no-trunc; history can contain sensitive build arguments

# Optional tools only when already available or project requires them.
hadolint <Dockerfile>
docker scout cves <tag>
```

Test startup, signal-driven shutdown, healthcheck, required writable paths, and expected architecture. Compare image size only against relevant baseline; size alone is not quality.

## Primary sources

- Docker build best practices: https://docs.docker.com/build/building/best-practices/
- Dockerfile reference: https://docs.docker.com/reference/dockerfile/
- Multi-stage builds: https://docs.docker.com/build/building/multi-stage/
- Build cache optimization: https://docs.docker.com/build/cache/optimize/
- Build secrets: https://docs.docker.com/build/building/secrets/
- Build checks: https://docs.docker.com/build/checks/
