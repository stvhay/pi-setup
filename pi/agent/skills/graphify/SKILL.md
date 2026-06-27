---
name: graphify
description: Use when the user invokes /graphify, asks to build or query a project knowledge graph, or asks codebase architecture/file-relationship questions where graphify-out/ exists.
---

# Graphify

Use Graphify to build and query persistent project knowledge graphs from code, docs, schemas, and media.

Pi integration rule: use the Pi helper surface first:

```bash
agnt graphify [ARGS...]
```

`agnt graphify` runs an installed `graphify` binary when available and falls back to `uv tool run --from graphifyy graphify`. Do not install or enable project-local Graphify refresh hooks unless the user explicitly approves hook installation in the current conversation. If needed, set `AGNT_GRAPHIFY_HOOKS=0` or pass `--no-hook-check` for ordinary graph commands.

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

For a faster or CI-friendly first pass, skip clustering/visualization when appropriate:

```bash
agnt graphify extract . --no-cluster
```

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

## Project refresh hooks

Manage per-project hooks explicitly when needed:

```bash
agnt graphify hooks status
agnt graphify hooks install
agnt graphify hooks uninstall
```

Hook installation changes repository behavior and requires explicit user approval in the current conversation. Checking hook status is allowed; installing, enabling, or uninstalling hooks is not allowed without approval.

The hooks are best-effort `post-commit`, `post-merge`, and `post-checkout` hooks that run `agnt graphify --no-hook-check update .` in the background. They are installed in the current Git repo's hooks directory, respect `core.hooksPath`, and use a marked block so existing hook content is preserved. They should not block commits or make generated `graphify-out/` tracked.

## Backend and environment notes

- Graphify's PyPI package is `graphifyy`; the CLI command is `graphify`.
- `uv` is the preferred installer/runner in this Pi setup.
- Extraction may require an LLM backend/API key depending on content and selected flags. Do not ask for secrets unless the command fails and the error explicitly requires one.
- Never commit generated `graphify-out/` artifacts unless the project explicitly asks to version them.
- If the graph is stale or missing, say so and offer the smallest useful build/update command.

## Answering with graph results

When using graph results:

1. State that you queried Graphify.
2. Summarize the relevant nodes/edges or paths.
3. Verify important claims against source files when the answer will drive edits or decisions.
4. If graph results are sparse or stale, fall back to normal filesystem inspection and say that the graph was insufficient.
5. The graph reflects the last commit (`built_at_commit` in `graph.json`); uncommitted edits and newly added symbols are absent. Use it for pre-change structure and impact analysis, not to inspect brand-new code.
