---
name: graphify
description: Use for /graphify, project knowledge-graph work, or architecture and dependency questions when graphify-out exists.
---

# Graphify

Use Graphify to build and query persistent project knowledge graphs from code, docs, schemas, and media.

Pi integration rule: use the Pi helper surface first:

```bash
agnt graphify [ARGS...]
```

`agnt graphify` runs an installed `graphify` binary when available and falls back to `uv tool run --from graphifyy graphify`. This tracked wrapper is adapted to Graphify 0.9.25. Do not install or enable project-local Graphify refresh hooks unless the user explicitly approves hook installation in the current conversation.

## Fast path: existing graph

Before broad codebase exploration, check whether `graphify-out/graph.json` exists in the current project.

If it exists and the user is asking an architecture, dependency, data-flow, file-relationship, or project-content question, query the graph before grepping or reading many files.

Query matching is lexical, not semantic: query terms are matched against node labels, then expanded by BFS. Sentence-form questions usually seed-match the wrong node and return almost nothing. Use short identifier/concept keywords and run 2-3 probes:

```bash
agnt graphify query "routing"            # keyword, not "How is routing implemented?"
agnt graphify explain "cmd_route"        # one node's callers/dependents with file:line
agnt graphify path "invoke.py" "routing.py"
```

Treat output as a map of `file:line` locations to read next, not as an answer. Use focused file reads afterward to verify or deepen the answer.

Do not rebuild the graph unless the user asks to build, update, refresh, export, or diagnose it.

## Invocation mapping

When the user types `/graphify`:

- `/graphify --help` or `/graphify -h`: run `agnt graphify --help` and summarize the relevant commands.
- `/graphify` or `/graphify .`: build/extract the current project graph.
- `/graphify <path>`: build/extract that path.
- `/graphify <url>`: use Graphify's GitHub/URL support if available; otherwise explain the required CLI flow.
- `/graphify query <question>`: query `graphify-out/graph.json`.
- `/graphify path <A> <B>`: find a shortest path between nodes.
- `/graphify explain <node>`: explain a node and neighbors.
- `/graphify update`: update the existing graph incrementally.

Use the real CLI help as the authority when commands or flags differ:

```bash
agnt graphify --help
```

## Common commands

Build a graph for the current project:

```bash
agnt graphify extract .
```

Force a full rebuild after extractor or node-ID changes. Graphify 0.9.25 emits path-qualified IDs that avoid same-name file collisions:

```bash
agnt graphify extract . --force
```

For a deterministic code-only or CI pass, skip semantic files and clustering when appropriate:

```bash
agnt graphify extract . --code-only --no-cluster
```

A full semantic rebuild uses configured Gemini credentials for documents, papers, and images. Show corpus size and obtain informed approval before a potentially material model call. Use `--max-concurrency` and `--token-budget` when the approved cost or load boundary requires them.

Update an existing graph after code changes:

```bash
agnt graphify update .
```

Query the graph:

```bash
agnt graphify query "routing"
agnt graphify explain "cmd_route"
agnt graphify path "AGENTS.md" "agnt route"
```

Export an architecture/call-flow HTML page:

```bash
agnt graphify export callflow-html
```

Diagnose graph issues:

```bash
agnt graphify diagnose multigraph --graph graphify-out/graph.json
```

After a full rebuild, verify diagnostics, path-qualified IDs, manifest/root metadata, and shrink protection before trusting the graph. Detailed 0.9.25 workflows live under `references/`: `extraction-spec.md`, `query.md`, `update.md`, `github-and-merge.md`, `add-watch.md`, `hooks.md`, `exports.md`, and `transcribe.md`. Load only the reference needed for the current operation.

## Project refresh hooks

Manage per-project hooks explicitly when needed:

```bash
agnt graphify hooks status
agnt graphify hooks install
agnt graphify hooks uninstall
```

Hook installation changes repository behavior and requires explicit user approval in the current conversation. Checking hook status is allowed; installing, enabling, or uninstalling hooks is not allowed without approval.

The hooks are best-effort `post-commit`, `post-merge`, and `post-checkout` hooks that run `agnt graphify update .` in the background. They are installed in the current Git repo's hooks directory, respect `core.hooksPath`, and use a marked block so existing hook content is preserved. They should not block commits or make generated `graphify-out/` tracked.

## Backend and environment notes

- Graphify's PyPI package is `graphifyy`; the CLI command is `graphify`.
- `uv` is the preferred installer/runner in this Pi setup.
- Code extraction is deterministic. Semantic extraction uses Gemini only when `GEMINI_API_KEY` or `GOOGLE_API_KEY` is already available; never print or request existing secrets.
- Warn before scanning more than 500 files or 2,000,000 words. Proceed with an approved whole-project rebuild or narrow to a subfolder.
- Never commit generated `graphify-out/` artifacts unless the project explicitly asks to version them.
- If the graph is stale or missing, say so and offer the smallest useful build/update command.

## Answering with graph results

When using graph results:

1. State that you queried Graphify.
2. Summarize the relevant nodes/edges or paths.
3. Verify important claims against source files when the answer will drive edits or decisions.
4. If graph results are sparse or stale, fall back to normal filesystem inspection and say that the graph was insufficient.
5. The graph reflects its saved manifest/root and build revision; uncommitted edits and newly added symbols may be absent. Use it for pre-change structure and impact analysis, not to inspect brand-new code.
6. Never invent an edge. Preserve and report `EXTRACTED`, `INFERRED`, and `AMBIGUOUS` provenance, raw cohesion values, token cost, and graph-health warnings.
