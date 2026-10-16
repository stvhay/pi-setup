---
name: tufte
description: Use when making/reviewing data graphics; quantitative diagrams, small multiples/sparklines, publication SVG/PDF/PNG/JPG/GIF. Not decoration or conversion without data design.
---

# Tufte: evidence-first graphics

Make the reasoning visible, not merely the chart attractive. Accuracy, context, and legibility outrank minimalism. A correct label does not repair misleading geometry.

Read [sources](references/sources.md) for book-grounded design choices and [production](references/production.md) before rendering or exporting. Paths are relative to this skill directory. Source notes distinguish Tufte's arguments from this skill's engineering rules; do not attribute modern file-format prescriptions to the books.

## 1. Establish the figure contract

Capture the question/comparison, audience, data source, units, denominators, uncertainty definition, missing-value meaning, intended physical or screen size, and required formats. Use supplied requirements; ask only when an unknown changes the conclusion or deliverable. Otherwise state assumptions. Never invent observations to make a figure work. Label synthetic examples as synthetic.

Preserve source data and a reproducible transformation/rendering source. Identify exclusions, aggregation, weighting, rounding, normalization, inflation adjustment, and time-zone/calendar conventions when relevant. For a diagram, establish the node/edge inventory, what each arrow means, direction, and which quantities must balance. Separate measured relationships from hypotheses.

## 2. Choose an evidence-bearing design

| Analytical task | Starting design | Guardrail |
|---|---|---|
| Compare magnitudes or estimates | Aligned dots; intervals when supplied; bars when length matters | Compare like units and populations. Keep denominators visible for rates. |
| Change over time | Line plus relevant reference/context | Respect actual time spacing; break missing intervals rather than invent continuity. |
| Distribution | Points, histogram, ECDF, or boxplot with definition | Show sample size; justify bins/smoothing; avoid hiding tails or subgroups behind averages. |
| Relationships | Scatterplot with context; fitted model only if warranted | Distinguish observations, fit, uncertainty and extrapolation. Association alone is not causation. |
| Repeated comparisons | Small multiples with aligned axes and stable encoding | Shared scales for magnitude comparison; clearly label any deliberate scale differences. |
| Compact history | Sparkline beside name, value, units and range/context | Do not let tiny, unscaled lines imply equal magnitudes. |
| Mechanism, sequence, or flow | Annotated diagram with specific relationships | Layout is not evidence. Verify endpoints, arrowheads, counts and semantics. |
| Exact lookup or very few values | Table, possibly with embedded graphics | A chart is optional; choose the clearest comparison. |

These are starting points, not a mandatory chart taxonomy. Integrate words, numbers and images at the point of use; directly label when readable. Provide sources, observation period, population and qualifications close enough to travel with the figure.

### Integrity before styling

- Map every mark to data through a stated scale. Bar lengths and filled areas need a meaningful zero; positional line/dot plots may use restricted ranges when disclosed and not misleading. Label logarithmic scales; reject invalid log values rather than silently dropping them. Area encodings scale area, not radius. Avoid decorative 3D and perspective distortion.
- Keep comparable panels, symbols, ordering, units and reference ranges consistent. Do not cherry-pick dates or omit zero-event cases. Distinguish missing, zero, censored and below-detection values.
- Define interval type and level; preserve asymmetry and supplied bounds. Do not manufacture uncertainty, clip it invisibly, or infer statistical significance from interval overlap alone.
- Use visual variation to express data variation. Remove decoration and redundant scaffolding, but retain necessary axes, tick marks, reference lines, labels, uncertainty and context. Data-ink is a judgment aid, not a score to maximize blindly.
- Use restrained contrast that remains clear at delivery size. Do not encode meaning by color alone. Check grayscale; use labels, line styles or shapes as needed. Rich evidence is welcome; unreadable density is not.

## 3. Build from one source of truth

Use an installed, suitable tool: a plotting library for data charts; SVG for controlled vector geometry; Graphviz for relational diagrams. Do not force a chart into an automatic graph layout. Prefer existing project code over new infrastructure. Ask before installing dependencies.

Generate labels and geometry from the same data where practical. Keep accessible names and descriptions with standalone graphics, not only in a separate QA note; use the format-specific guidance in production. Preserve editable source and real vector geometry for vector deliverables; converting a bitmap into SVG/PDF is not vectorization. Never use an image generator to establish quantitative marks or labels. Any illustrative background must remain separate from measured data.

Design at final size. For books/papers, follow publisher width, type, line and color requirements. For documentation, check both embedding size and background. For slides, increase type and simplify the comparison structure without deleting evidence needed for the claim; provide a detailed companion figure rather than fragmenting comparisons across slides. For interactive or GIF animation, read the deterministic-scene, controls, motion-preference and frame/timing rules in production; a static GIF is not an animation.

## 4. Verify through two independent gates

**Numerical/structural gate:** recompute key values from source, check counts/totals, extrema, units, ordering, transforms, missingness and interval endpoints. Check representative geometry against scale calculations, not just label text. For diagrams, compare rendered nodes and edges to the inventory, including direction and balance. Use assertions for repeatable checks. Parse SVG/XML or renderer output structurally rather than with text substitution.

**Visual gate:** render and open the actual deliverables (rasterize vector pages for inspection), not just source code or tool success messages. Inspect at intended placement size and inspect dense/critical regions enlarged. Check:

- all expected observations, zero-valued marks and interval endpoints are visible;
- labels, minus signs, decimals, units and glyphs match the source;
- no clipped text, overlaps, hidden marks, stray lines or ambiguous connectors;
- hierarchy, contrast, line weights and type survive reduction, grayscale and destination background;
- each export preserves the same data and geometry without conversion artifacts that suggest new structure; animation preserves its intended sequence.

If a check fails, repair the shared source, regenerate affected exports, and repeat both affected checks. Record the defect and the post-repair evidence. Do not patch a final PNG while leaving the vector/source wrong. A contact sheet can triage images, but cannot prove small text is readable.

If viewing/rendering is unavailable, deliver a clearly labeled draft and mark the affected check **NOT_VERIFIED**. Do not substitute a numeric test, file existence, or imagined screenshot for visual evidence. If failures persist, preserve source and evidence, report the blocker, and stop claiming readiness.

## 5. Deliver and learn

Return source/data references, editable/vector files, requested raster files, dimensions/resolution, a descriptive caption or alt text, and a short QA record:

```text
Data/geometry: PASS | FAIL | NOT_VERIFIED — checks and evidence
Visual: PASS | FAIL | NOT_VERIFIED — files opened, size, findings, repairs
Formats: PASS | FAIL | NOT_VERIFIED — vector status, dimensions, fonts/background; frames/timing if animated
Limits: assumptions, omitted/unavailable checks, intended use
```

A pass applies only to the inspected revision, formats and use conditions. Keep commands and evidence paths sufficient to reproduce it. Do not call a figure publication-ready while a required gate fails or remains unverified.

When improving this skill, turn observed failures into general invariants and a regression case. First inspect existing guidance: revise the rule that owns the issue rather than append another rule. Recheck for contradictions, duplication, over-specific examples and overgeneralization; retain justified exceptions. Store incident details in evaluation evidence, not the core skill. Re-run the original case and a neighboring case before claiming improvement.
