# Regression assessment

When the user reports a visual regression, **before** patching the bug
work through this assessment. Its purpose is closing the loop — every
regression should either propagate as durable knowledge (improved
checklist, new fixture, sharper principle) or be classified as
non-propagating (user preference, site corner case) and recorded
accordingly. Patches without assessment teach nothing.

The output of this template is concrete: at least one file edit
somewhere in the skill, the project, or memory. "No change needed" is a
valid outcome only after deliberately rejecting all four branches.

## Capture

- **Site / theme:**
- **Page or fixture where it surfaced:**
- **Interactive state, if any** (hover, focus, dropdown-open, mobile, etc.):
- **What the user reported** (verbatim quote if possible):
- **What the rendered output actually showed** (load the PNG; describe what
  you see, post-vision):

## Branch 1 — Could the agent reasonably have caught this visually?

If the answer is "yes, this is a visible visual defect on a page the
agent should have screenshotted," go to 1a/1b. If "no" (it's only visible
under conditions the rig couldn't have reasonably captured, e.g. live
network state, server-side data the user has but the agent doesn't), go
to Branch 4 (site-specific corner case).

### 1a — Did the agent load the relevant PNG into vision context?

**If yes** (the screenshot was loaded but the agent didn't flag the issue):

- The vision pass *missed* the defect. The agent looked but didn't see.
- Failure mode: **vision-pattern blindness** — the principle that would
  have flagged this defect wasn't on the per-fixture checklist.
- **Action:** add a check to the checklist in
  `references/vision-verification.md` § "Per-fixture checklist" that
  would have caught this. Be specific:
  > After the change: when reviewing `<fixture>`, verify `<element/state>`
  > has `<expected property>` because `<failure mode this prevents>`.
- This is the single most valuable fix: the principle is now durable
  across all future themes.

**If no** (the relevant screenshot was not loaded into context):

- The vision gate was *not triggered* for this state.
- Sub-cases:
  - **Static state, fixture exists, screenshot wasn't read:**
    Failure mode: agent skipped the vision gate. Strengthen the language
    in `references/vision-verification.md` so the gate is harder to skip.
  - **Static state, no fixture covered the page:**
    Failure mode: fixture coverage gap. Add a fixture for this page;
    note in `themes/<name>.md` that the original coverage was incomplete.
  - **Interactive state (hover/focus/dropdown/mobile/media-query) not
    captured:**
    Failure mode: state coverage gap. Add a state spec to the fixture
    (see `templates/fixture.html` for the `layer-theme-states` block)
    so the next screenshot run captures it.

## Branch 2 — Does the regression violate a UX principle?

A principle is general — it would apply to other sites too. Examples:
"text inside a coloured fill must use the matching `--on-*` token,"
"properties that create stacking contexts can't be applied to elements
containing positioned descendants."

- [ ] The principle is **already** in `references/design-principles.md`
      → why was it skipped/not applied?
      - If a checklist item exists but the agent didn't apply it: the
        item is ambiguous or buried — rewrite it for clarity.
      - If the principle is documented but the agent didn't realize it
        applied here: add a **trigger phrase** ("when you see X, recall
        principle Y") to the design-principles entry.
- [ ] The principle is **not** in `references/design-principles.md`
      → add it. Concrete proposal (write it out in full):
      ```
      ## <heading>
      <one-paragraph rule>

      Why: <the regression that surfaced this>
      How to apply: <when this kicks in>
      ```
      Cross-cite from the relevant Iron Law in `SKILL.md` if the
      principle is severe enough to warrant gate-level enforcement.

## Branch 3 — Is this user preference, not a general principle?

Test: would the same change be a regression on a different site, or only
this one and only for this user? If only this user / this site, it's
preference, not principle.

- [ ] Yes — preserve as `feedback` memory, not a principle:
  ```
  ---
  name: <short>
  description: <when this applies>
  type: feedback
  ---
  Rule: <user's preference, stated as a rule>
  Why: <reason given by the user>
  How to apply: <when, where>
  ```
- Do **not** add to `design-principles.md`. That file is the public
  contract for general theming — preferences belong in user memory,
  scoped to this user.

## Branch 4 — Is this a site-specific corner case?

The defect arose because of an upstream framework quirk that doesn't
generalize (a non-standard cascade, an outlier class taxonomy, an
off-spec HTML structure).

- [ ] Yes — record in the **theme spec** for this site, not the global
  skill. In `themes/<style-name>.md` § "Notes / gotchas surfaced during
  implementation," add an entry of the form:
  > On `<framework>`: `<quirk>`. Workaround: `<fix>`.
- Do not propagate to `design-principles.md`. The next site won't have
  this quirk; the principle would be wrong there.

## Closing the loop

Before patching the bug:

- [ ] Branch identified: `<1a-yes / 1a-no-static / 1a-no-state / 2-existing / 2-new / 3 / 4>`
- [ ] Concrete change made: `<file path + line or section>`
- [ ] If Branch 1a-no-state: state spec added to fixture.

Now patch the bug. Re-run the screenshot harness, vision-verify, confirm
the fix using the gate that was previously missing.

## Recording

Add a one-line entry to `themes/<style-name>.md` under "Regressions
caught" (create the section if absent):

> - 2026-MM-DD: `<one-line description>`. Branch: `<X>`. Propagated to:
>   `<file>`.

This serves as a longitudinal record of what kinds of regressions this
theme produced and where the corresponding skill improvements landed.
