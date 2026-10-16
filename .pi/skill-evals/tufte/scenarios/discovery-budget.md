# Scenario: Restore discovery reserve after adding Tufte

## Prompt
Choose relevant skills for these requests, then distinguish the near neighbors:

| Skill | Positive requests | Near neighbors / boundaries |
| --- | --- | --- |
| tufte | Create or review data visualizations, quantitative diagrams, small multiples or sparklines; Tufte-style publication figures for papers, books, docs or slides in SVG/PDF/PNG/JPG/GIF. | Decorative illustration or image conversion without data-design work does not select Tufte. Publication includes all four destinations; formats do not limit ordinary data-graphics work. |
| laya-integration | Integrate Laya/Jev, System 1 or typed decision models; classify/route text, triage, detect spam/phishing/toxicity/intent, score rubrics. | Text generation or multi-step reasoning alone does not select Laya. |
| subagent-driven-development | Explore or execute independent implementation-plan tasks via peers or isolated worktrees. | Coupled tasks or shared mutable writes do not justify parallel implementation. |
| receiving-code-review | Assess human, GitHub or model code-review feedback before deciding whether/how to fix it. | Requesting a new review differs from assessing feedback already received; assessment may reject a proposed fix. |
| delegation-oversight | Design human-AI handoff and when agents should ask versus act. | Designing an approval button alone is approval-confirmation; diagnosing a failure handoff is failure-choreography. |
| stamp-stpa-sec | Threat-model control structures for adversarial/cyber, attack-surface or combined security/safety risks. | Retrospective incident analysis routes to CAST; non-adversarial prospective safety analysis to STPA. |
| stamp-cast | Systemically review accidents, incidents, near-misses, root-cause claims or failed controls. | Prospective hazards alone do not become retrospective incident analysis. |
| failure-choreography | Design graceful agent-system failure, preservation of partial progress or dignified human handoff. | Routine ask-versus-act delegation without failure is delegation-oversight. |

## Expected weak baseline
At source HEAD 49dd1ea, discovery uses 7332 of 8000 characters; remaining 668 fails the existing >1000 reserve assertion. Commit bdf0940 added Tufte's 341-character row to a 6991-character baseline. The other 47 contributions are unchanged.

## Expected with skill
The same trigger families and exclusions remain discoverable while remaining reserve exceeds 1000. Description compression does not authorize automatic fixes, parallel writes or weakened safety controls.

## Assertions
- Preserve every routing concept and boundary above; review descriptions alongside unchanged bodies.
- Change only approved description lines; preserve all other skill content and automatic discovery.
- Keep existing discovery calculation, 8000 hard limit, inclusive 1000 warning and reserve test unchanged.
- Existing tests still prove warning at remaining 1000, silence at 1001, over-budget failure, manual-only exclusion and contributor reporting.
- Do not hide the separate existing Laya skill-size warning.

## Verification
Baseline observed before editing: isolated-HOME `pytest tests/test_agnt.py -k context_health -q --tb=short` gives 18 passes and one `assert 668 > 1000` failure.

Run the same focused tests, `pytest tests/test_context_architecture.py -q`, and `pi/agent/bin/agnt context-health --strict`. Compare all non-description lines against the source revision and review this table against the candidate wording.

Trigger preservation is static semantic review, not a measured model-selection benchmark. No live deployment or model canary is part of this correction.
