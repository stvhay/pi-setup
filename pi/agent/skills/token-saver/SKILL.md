---
name: token-saver
description: Use when token/context discipline matters for large-source retrieval, deterministic transformations, iterative revisions, or delegated model/tool work; not to weaken safety or verification.
---

# Token Saver

Once loaded, apply these rules for the rest of the job. Loading cannot erase or shrink the call that loaded this skill; it can only make later retrieval, calls, and revisions smaller.

## Spend rules

1. **Local code first for exact work.** Before calling any model, use shell tools or standard-library code for counting, sorting, exact text search, field extraction, date normalization, format conversion, file comparison, and output validation.
2. **Retrieve passages, not sources.** Search large transcripts, repositories, exports, and files locally. Send only matching passages with minimal surrounding context. If insufficient, add one more bounded passage at a time; never fall back to loading the whole source.
3. **Minimize tool surface.** For each new job or worker, load only tools it can use; load none for a no-tool job. If the current call's tools are already fixed, do not use unrelated tools.
4. **Choose models directly.** Use measured routing/eval history when available. Use a smaller model only when expected total job cost improves, including every call, retry, and likely human repair. If evidence is absent, keep the capable default. Never call a model to choose a model.
5. **Match requested shape.** Return only what was requested: a sentence stays one sentence. No process diary, unrequested options, or extra framing.
6. **Bound repair.** After a failed check, allow one focused repair and rerun only that check once. Never repeat a token-limit or usage-limit failure unchanged; reduce input before any continuation.

Do not weaken input validation, security, accessibility, approval, data-loss prevention, or required verification to save tokens.

## Batching and progress

- **Batch only independent read-only operations.** Issue unrelated reads, searches, and checks in one turn when tools support parallel calls. Keep dependent retrieval serial.
- **Writes, approvals, and safety gates stay serial.** Never batch operations whose order or intermediate result affects correctness, consent, or recovery.
- **Use execution-derived status.** Prefer harness tool activity, test output, and subagent progress over model-authored “still working” turns.
- **Use todos by phase.** Update `manage_todo_list` at phase boundaries, then mark a completed phase immediately. Use finer updates only when harness status is unavailable or a long step needs visible recovery state.

## Current accepted result

Keep one exact current accepted result outside chat:

- In a Git worktree, use the path returned by `git rev-parse --git-path token-saver-current`; otherwise use `${XDG_STATE_HOME:-$HOME/.local/state}/pi/token-saver-current`.
- Create directories and state yourself. Promote only after explicit user acceptance, using an atomic replacement. Keep no versions, backups, or appended history.
- Rejection leaves current state unchanged. Never promote a rejected result.
- Build each revision from current state plus the user's new change, not from the conversation that produced current state.
- If state is missing but this conversation contains an accepted result, recover it yourself with streaming/local search of `$PI_SESSION_FILE` or available harness state, emitting only the bounded matching exchange into model context.

Never ask the user to summarize old chat, choose source files by hand, create state, or learn helper-script paths.

## Accounting

When asked for usage, report only harness-provided values for fresh input, reused/cache-read input, output, model calls, and retries. Write `unavailable` for fields the harness does not report; never estimate them.
