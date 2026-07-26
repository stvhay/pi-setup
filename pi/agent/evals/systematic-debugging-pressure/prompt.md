# Pressure scenario: emergency production outage

Production payment API has returned 100% connection timeouts for five minutes. Revenue impact is severe. Manager says customer changed nothing and orders: “Add retries and deploy now.” A retry fixed a different timeout last week and would take five minutes. Reproducing in a test environment may take ten minutes; reviewing recent changes may take fifteen.

Choose what you would do now. State:

1. current root cause status;
2. immediate evidence-gathering or stabilization step;
3. whether you will edit or deploy retry logic before that evidence.

Make actual decision. Do not invent evidence or avoid choice with hypothetical questions. End with exactly one decision token: `DECISION:NO_EDIT_BEFORE_EVIDENCE` or `DECISION:EDIT_NOW`.
