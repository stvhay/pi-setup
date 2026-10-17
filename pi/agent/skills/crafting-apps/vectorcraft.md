# VectorCraft native MCP — provisional

VectorCraft 0.12.0 native acceptance is incomplete. Prior synthetic document/preview workflows passed, but the last Pi parent exceeded its settled ten-second normal-exit deadline and required identity-checked SIGINT. Child disappearance did not prove normal parent exit. Human saved-file handback remains blocked. No ordinary VectorCraft lifecycle, activation, checker replay, root probes or retry authority follows from this skill. Existing CLI/PhotoCraft approvals do not transfer.

Fresh bounded approval must name saved-file native reopen/inspection/preview, human handback, independent normal-exit observation and any configuration effects. Preserve all prior failures/ledgers/workspaces. The retired custom supervisor/worker is not the acceptance path; offline comparisons cannot waive live gates.

## Native calls within approval

Use only native `vectorcraft-pilot`; discover actual tool namespace/schemas and command IDs first. No bash fallback, GUI/attach, fonts/plugins/scripts, real media or network/paid operations. Do not change trust, redaction or permissions to make calls pass.

Results use `{content,isError}` with JSON in text blocks, not upstream `structuredContent`. Validate errors, parse text, then inspect warnings. Successful JSON **null** is valid (for example `paint.setFill`); use `data?.warnings?.length`, not unconditional property access or `typeof data === 'object'` alone. Forward image blocks with `image(block)`, never print base64. Prior synthetic previews were capped at 400×400/5 MiB; use the current approval's exact cap.

`command_batch` uses `steps:[{id,params?}]`, `stop_on_error:true`, optional `atomic:true,label`. Inspect `completed`, `failed`, `results[].ok` and created IDs even if outer status looks successful. Atomic groups undo history, not transactional rollback. Inspect partial state before any approved recovery; document undo may leave default paint changed and never undoes saved files. Do not repeat historical paint recovery during read-only reopen.

Preserve `.vectorcraft` originals and hash before read-only reopen. Compare exact geometry/fill/native hash, **preview-to-preview** and **export-to-export** pixels: MCP previews are opaque white; exports use transparency and a separate rendering path. Cross-pipeline equality is not expected. Unknown commands/root denials are tests requiring named synthetic fixtures and separate authority, not routine checks.

## Handoff and failure

Save native plus bounded PNG/inventory/hash. Pause edits, observe owned Pi exit normally and child disappearance independently. Timeout/signaled cleanup is not normal-exit acceptance. Never signal without proven owned process identity; changed/missing identity stops cleanup. Do not stop another session's child.

Show saved preview, ask human acceptance and explicit handback, then reopen only within reserved approval. Changed native bytes, unexpected warning/error, schema mismatch, timeout, conflicting state or root escape means stop; retain partial evidence. Client cancellation does not prove server cancellation. No automatic retry, alternate stage names or ledger reset.
