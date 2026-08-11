# Scenario: Preserve usable review output under liveness bounds

## Prompt
Review a high-risk diff with one cold subscription-backed discovery pass, one cold metered boundary pass, then a fresh subscription-backed agentic verifier for any serious finding.

## Expected weak baseline
Discovery workers hit a 180-second caller deadline before returning valid final JSON, or the agentic verifier gets only four provider turns and stops after healthy read-only tool work. Parent reports both as vague timeouts because partial output hides structured termination evidence.

## Expected with skill
Cold discovery keeps one provider request but allows a 300-second liveness window. Fresh subscription-backed verification gets thirty provider requests and the same 300-second window without token or cost caps. Parent reports caller, operator, worker-startup, and parent-cancellation sources while retaining partial output and artifact references.

## Assertions
- Cold discovery uses `maxProviderRequests: 1` and `maxDurationMs: 300000`.
- Fresh agentic verification uses `maxProviderRequests: 30` and `maxDurationMs: 300000`.
- Subscription-backed review defaults add no token or cost cap.
- Failed child content names termination reason and source even when partial output exists.
- Real deadlines preserve partial output and delegated artifact references.
