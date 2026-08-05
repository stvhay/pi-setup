# Scenario: resolved review closeout

## Prompt
The requirement review is finished. Produce the durable closeout update and handoff plan without implementing code. Baseline is 5,200 production-plus-focused-test lines. Accepted decisions, in order:

1. Drop legacy Adapter: current net removal 700–1,100; gross future avoidance 100–200.
2. Replace descendant cleanup mechanism: current net removal 450–650, but 100–200 overlaps legacy Adapter tests counted above.
3. Keep sibling Sessions: zero delta.
4. Require observable Delegations: required future additions 150–300.
5. Drop transparent recovery: gross future avoidance 250–450; zero current delta.

Repository uses Beads. Several downstream Beads and design docs still contain old requirements. Show latest-decision delta, overlap-adjusted current total, gross future avoidance, required future additions, net future avoidance, contradiction audit, and non-duplicative successor ownership. No questions remain.

## Expected weak baseline
Agent adds all ranges mechanically, mixes current deletion with future avoidance, omits required additions, leaves stale design text untouched, creates duplicate work items, or starts implementation during closeout.

## Expected with skill
Agent records review as complete only after source alignment and verification, computes current net removal as 950–1,650 after overlap, computes gross future avoidance as 350–650, required additions as 150–300, and net future avoidance as 50–500. It reports latest decision delta as zero current and 250–450 gross future avoidance, maps every accepted cut/addition to one successor Bead, checks dependencies/readiness, and leaves implementation untouched.

## Assertions
- Current overlap-adjusted net-removal range is 950–1,650.
- Gross future-avoidance range is 350–650.
- Required future-addition range is 150–300.
- Net future-avoidance range is 50–500 using `[gross low - additions high, gross high - additions low]`.
- Latest decision delta is zero current and 250–450 gross future avoidance.
- Retained sibling Sessions remain explicit with zero delta.
- Normative docs and stale downstream Beads are audited and aligned without claiming unimplemented behavior exists.
- Each accepted current cut and required addition receives one non-duplicative successor owner with dependency and ready-queue checks.
- Review Bead closes only after artifact commit and verification.
- No implementation code is changed.
