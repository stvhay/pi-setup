# Persisted reviewer-output recovery evaluation

## Protocol

Ran `recover-persisted-review-before-retry.md` with the same isolated `openai-codex/gpt-5.6-luna` low-thinking setup before and after the tracked skill change. Both runs force-loaded only `requesting-code-review`, disabled tools and ambient context, and received the same hypothetical resolver/artifact outcome.

Runtime evidence:

- tracked baseline: `/tmp/pi-1fgw3-baseline-1.out`
- tracked candidate: `/tmp/pi-1fgw3-candidate-1.out`

## Comparison

| Assertion | baseline | candidate |
|---|---:|---:|
| Resolve delegated-results root before provider retry | pass | pass |
| Read exact referenced suffix without another URI | incomplete | pass |
| Check schema, invocation, child, and usable output | incomplete | pass |
| Save and validate recovered output | pass | pass |
| Complete artifact causes zero reviewer retries | pass | pass |
| Artifact failure permits at most one repair retry | pass | pass |
| **Total** | **4/6** | **6/6** |

Candidate named exact resolved suffix, validated `schemaVersion: 1`, invocation identity, child index, and non-empty `finalOutput`, then finished with reviewer retry count 0. Missing or invalid artifact recovery remained bounded to one concise format-repair retry.

Baseline already avoided the nominal retry in this one sample, so no runtime helper was justified. Explicit guidance plus deterministic contract test closes observed ambiguity without adding storage, URI, resolver, or provider-call logic.
