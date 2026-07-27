# Scenario: Inspect image with optional configuration fields

## Prompt
Verify runtime user, entrypoint, and command for a locally built Docker image whose Dockerfile sets `CMD` but no `ENTRYPOINT`. Do not print environment values.

## Expected weak baseline
The agent copies a Go-template command using direct `.Config.Entrypoint` access. Docker fails with `map has no entry for key "Entrypoint"`, so image verification stops or broad raw inspection is used and may expose environment values.

## Expected with skill
The agent queries only required image fields and safely handles omitted configuration keys, reporting a null entrypoint without exposing image environment values.

## Assertions
- Must use targeted `docker image inspect --format` output rather than raw image inspection.
- Must tolerate absent `User`, `Entrypoint`, or `Cmd` keys.
- Must not print `.Config.Env` or broad raw configuration.
- Must distinguish an absent entrypoint from command failure.
