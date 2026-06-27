# Scenario: Algorithm optimization with scorer

## Prompt
Optimize this text chunking algorithm for retrieval quality and latency. We can run `python eval_chunker.py --candidate PATH` to return MRR, recall@10, p95 latency, and cost. Find a better implementation.

## Expected weak baseline
The agent edits heuristically based on intuition, runs few or no candidates, lacks a baseline score, and cannot explain why the chosen change is better.

## Expected with skill
The agent defines the scorable task, records baseline metrics, proposes bounded candidate families, runs candidates through the evaluator, maintains a leaderboard, inspects tradeoffs, and only recommends reproducible winners.

## Assertions
- Must establish baseline score before optimization claims.
- Must define objective metric/tradeoff policy.
- Must run or specify repeatable evaluator commands.
- Must track candidates and results in a leaderboard/run log.
- Must not claim improvement without fresh scoring evidence.
