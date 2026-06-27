# Scenario: Biomedical mechanism hypotheses

## Prompt
Generate research hypotheses for why Drug X appears to reduce inflammatory marker Y in Treatment Z non-responders. We have five mixed papers and no obvious mechanism. Produce useful next steps.

## Expected weak baseline
The agent lists a few plausible mechanisms, overstates certainty, does not separate novelty from plausibility, and gives generic experiments without falsification criteria.

## Expected with skill
The agent clarifies the objective, grounds hypotheses in cited/source context if available, generates diverse candidates, critiques and ranks them tournament-style, surfaces critical flaws, and proposes falsifiable experiments.

## Assertions
- Must produce multiple candidate hypotheses before choosing winners.
- Must include explicit ranking criteria.
- Must identify critical flaws or disconfirming evidence for top hypotheses.
- Must include testable/falsifiable research plans.
- Must not present hypotheses as established facts.
