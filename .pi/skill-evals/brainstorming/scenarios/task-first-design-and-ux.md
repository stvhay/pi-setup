# Scenario: task-first-design-and-ux

## Prompt
R8: Give divergent ideas, do not choose / turn requirements into design. R10: Rewrite button text / redesign approval preview / explain uncertainty. R18: Polish owned GUI / restyle third-party site. M2: Brainstorm interface with unclear users, approve design, then plan.

## Expected weak baseline
Source-observed at pre-implementation baseline (not model-observed): UX claims brainstorming calls it but caller lacks link; UX graph jumps to writing-plans and output uses docs/plans; layer-theme references absent frontend-design.

## Expected with skill
Ideate stays divergent; brainstorming converges only with approval. Conditional UX handoff returns requirements. Copy, consent and trust remain standalone. Owned GUI uses design-principles; third-party theming uses layer-theme.

## Assertions
- No writes/planning from obvious user model alone. M2 reads exact UX path, carries constraints and allowed effects, returns for design approval, then uses agnt plans-dir. No missing frontend-design pointer.
- Written scenarios and static checks do not measure model selection recall; real-model comparison NOT_VERIFIED.
