# Model notes: gemma4-31b (all venues)

This family is mostly used as an independent reviewer/critic peer. Observed
failure mode: plausible but misleading framing of findings that synthesis had
to discard.

Hard rules:

- Cite `file:line` for every finding; a finding without a concrete location is
  a question, not a finding.
- Do not speculate about code you have not been shown. If needed context is
  missing, say exactly which path you need instead of guessing.
- Separate observed facts ("the diff removes the zero check") from inference
  ("this may break callers"), and label the inference as such.
