# Scenario: Preserve usable review output under liveness bounds

## Prompt
Review a high-risk diff with one cold subscription-backed discovery pass, one cold metered boundary pass, then a fresh subscription-backed agentic verifier for any serious finding.

## Expected weak baseline
Discovery workers hit a 180-second caller deadline before returning valid final JSON, or the agentic verifier gets only four provider turns and stops after healthy read-only tool work. Parent reports both as vague timeouts because partial output hides structured termination evidence.

## Expected with skill
Cold discovery relies on one-shot's intrinsic single provider request and keeps only a 300-second caller liveness window. Fresh subscription-backed verification uses the same duration bound without a default request, token, or cost cap. Parent reports caller, operator, worker-startup, and parent-cancellation sources while retaining partial output and artifact references.

## Assertions
- Cold discovery uses `maxDurationMs: 300000` without `maxProviderRequests`.
- Fresh subscription-backed agentic verification uses `maxDurationMs: 300000` without `maxProviderRequests`.
- Subscription-backed review defaults add no token or cost cap.
- Failed child content names termination reason and source even when partial output exists.
- Real deadlines preserve partial output and delegated artifact references.
