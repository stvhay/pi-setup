# Scenario: Preserve usable review output under liveness bounds

## Prompt
Review a high-risk diff with one cold subscription-backed discovery pass, one cold metered boundary pass, then a fresh subscription-backed agentic verifier for any serious finding.

## Expected weak baseline
Discovery workers hit a 180-second caller deadline before returning valid final JSON, or the agentic verifier gets only four provider turns and stops after healthy read-only tool work. Parent reports both as vague timeouts because partial output hides structured termination evidence.

## Expected with skill
Cold subscription discovery relies on one-shot's intrinsic single provider request and keeps only a 300-second child-activity window. Fresh subscription-backed verification uses the same idle bound without a wall-time, request, token, or cost cap. Metered calls retain approved absolute duration bounds. Parent reports caller, operator, worker-startup, idle, and parent-cancellation sources while retaining partial output and artifact references.

## Assertions
- Cold subscription discovery uses `maxIdleMs: 300000` without `maxProviderRequests`.
- Fresh subscription-backed agentic verification uses `maxIdleMs: 300000` without `maxProviderRequests` or `maxDurationMs`.
- Metered and explicit calibration runs retain absolute `maxDurationMs` bounds.
- Subscription-backed review defaults add no token or cost cap.
- Failed child content names termination reason and source even when partial output exists.
- Real deadlines preserve partial output and delegated artifact references.
