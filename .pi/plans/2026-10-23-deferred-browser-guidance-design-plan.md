# Deferred browser guidance design-plan

Bead: pi-b9gn

## Goal and smallest implementation

Keep a concise browser discovery/policy summary always visible. Return complete, policy-adapted upstream browser instructions in the already-required browser_evidence initialize result, before any subsequent browser operation. Tell callers to return/read that result before issuing browser actions, including codemode batches. Preserve permission enforcement and prompt composition. No new tool, router, activation state, memory change, or deployment.

Files: pi/agent/extensions/browser-permissions.ts; tests/test_browser_permissions.py; pi/README.md. Dependency prerequisite currently also changes package.json/package-lock.json and requires the matching SDK pin assertion in tests/test_beads_workspace.py.

## Verification

Baseline: 12 browser permission tests pass on both Pi SDK 1.3.0 and 1.4.0. Add failing tests for absent detailed startup guidance, full initialization guidance with effective policy, unchanged later tool results, and SDK section/forced prompt composition. Run existing policy regression tests, actual BetterWright 2.9.0 initialization without launching browser, and complete project gate after review. Measure character reduction separately from unmeasured provider tokens/latency.

## Approved dependency exception (pi-qqmy)

Latest Pi SDK 1.4.0 installed with ignore-scripts; npm update refreshed allowed dependencies; npm audit reports zero vulnerabilities. Latest upstream SDK pins older transitive packages (e.g. @anthropic-ai/sdk 0.129.0, openai 7.19.0, typebox 1.3.27). Others have incompatible parent major ranges. A latest-only graph cannot satisfy those published constraints without overrides or maintaining forks. No overrides applied. Retaining this graph requires explicit user exception under project policy, not an inferred exemption for upstream pins.

Proposed exception: retain the exact installed versions below for pi-b9gn's test SDK graph, using package-lock.json for exact paths/integrities. Reason: preserve published upstream compatibility constraints during this browser-guidance change instead of introducing unverified provider/SDK migrations. Revisit at next Pi SDK upgrade or any relevant security advisory, whichever comes first. This exception does not approve deployment or unrelated package drift.

| Package | Installed version proposed for exception | Latest stable observed |
|---|---|---|
| @anthropic-ai/sdk | 0.129.0 | 1.1.0 |
| @aws-sdk/client-bedrock-runtime | 3.1127.0 | 3.1156.0 |
| @aws-sdk/token-providers | 3.1127.0 | 3.1156.0 |
| @aws-sdk/token-providers | 3.1155.0 | 3.1156.0 |
| @babel/runtime | 7.29.10 | 8.0.7 |
| @google/genai | 2.21.0 | 2.31.0 |
| @stablelib/base64 | 1.0.1 | 2.0.1 |
| @types/retry | 0.12.0 | 0.12.5 |
| agent-base | 7.1.4 | 9.0.0 |
| balanced-match | 4.0.4 | 5.0.0 |
| bignumber.js | 9.3.1 | 11.1.5 |
| chalk | 6.0.0 | 6.0.1 |
| data-uri-to-buffer | 4.0.1 | 8.0.0 |
| diff | 8.0.4 | 9.0.0 |
| fetch-blob | 3.2.0 | 4.0.0 |
| gaxios | 7.3.1 | 8.3.1 |
| gcp-metadata | 8.1.2 | 9.2.2 |
| get-east-asian-width | 1.6.0 | 1.7.0 |
| google-auth-library | 10.9.1 | 11.3.1 |
| google-logging-utils | 1.1.3 | 2.1.0 |
| highlight.js | 10.7.3 | 11.12.0 |
| hosted-git-info | 9.0.3 | 10.1.1 |
| https-proxy-agent | 7.0.6 | 9.1.0 |
| ignore | 7.0.8 | 7.0.13 |
| isexe | 2.0.0 | 4.0.0 |
| marked | 18.0.11 | 18.1.1 |
| marked-cjk-friendly | 0.1.2 | 0.1.3 |
| node-domexception | 1.0.0 | 2.0.2 |
| openai | 7.19.0 | 7.43.0 |
| p-retry | 4.6.2 | 8.0.1 |
| path-key | 3.1.1 | 4.0.0 |
| protobufjs | 7.6.6 | 8.8.1 |
| quickjs-wasi | 3.6.2 | 3.6.3 |
| retry | 0.12.0 | 0.13.1 |
| shebang-regex | 3.0.0 | 4.0.0 |
| signal-exit | 3.0.7 | 4.1.0 |
| typebox | 1.3.27 | 1.4.3 |
| undici | 8.10.2 | 8.12.3 |
| undici-types | 8.9.0 | 8.12.3 |
| web-streams-polyfill | 3.3.3 | 4.3.0 |
| which | 2.0.2 | 7.0.0 |
| yaml | 2.9.0 | 2.9.1 |

## Status

Human approved the listed test-SDK version exceptions through pi-qqmy. Browser guidance tests observed RED (details still in startup prompt; no initialization guidance), then GREEN on Pi SDK 1.4.0. package.json and package-lock.json contain task-owned SDK update. Existing unrelated untracked files untouched. Focused verification: 15 tests passed (14 browser tests plus SDK pin assertion). Real BetterWright 2.9.0 initialization canary passed without starting a browser: full guidance 4,418 characters; startup pointer/policy 579; 3,839 characters removed (86.9%). Token and latency savings unmeasured. Canary: .pi/reviews/pi-b9gn/browser-canary.mjs and browser-canary.json. Subscription Astra review returned no findings; validated result: .pi/reviews/pi-b9gn/findings.json. Final candidate gate and commit results are recorded in Bead pi-b9gn to avoid changing the candidate after its gate.
