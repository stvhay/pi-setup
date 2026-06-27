# Vision verification

The protocol that prevents the failure mode the user surfaced as
"Why can't you see them? What else can't you see?". Read before Phase 5.

## The overconfidence trap

This section exists because Opus's analytical capabilities are tempting
but lossy for visual claims. The model defaults to reasoning when it
should default to looking. **Reasoning about a screenshot is not a
substitute for taking and loading one.**

You are in the trap if you find yourself thinking, writing, or saying:

- "Specificity-wise, this rule should win, so..."
- "Given the cascade, the button will now be..."
- "The change is small / obvious / mechanical, so I don't need to verify..."
- "Earlier screenshots passed, so this similar change..."
- "I can tell from the diff that..."
- "The CSS reads correctly, therefore..."
- "Tracing through the rules: ..."

Every one of these substitutes a *model of the visual* for the *visual
itself*. A model can be wrong. A PNG loaded into vision context cannot
disagree with what the page actually rendered.

**Decision rule.** When you want to make any claim about how something
*looks* — alignment, contrast, color, focus state, spacing, "this fixed
it," "this didn't change anything else" — there are exactly two valid
moves:

1. **Run Playwright** (`scripts/screenshot.py`) to produce a fresh
   screenshot of the post-edit state.
2. **Read the PNG** (Read tool on `screenshots/dark/<label>.png`) so it
   enters vision context this turn.

Both. In that order. Then write the claim, citing what you actually
observed in the image.

If you skip either step and the user catches the regression, that is the
exact failure mode that produced the LuCI session's escalation: "Why
can't you see them? Why are there pages you are unable to test?"

The vision API call is **definitive**. The analytical chain is
**probabilistic**. They are not equivalent. A screenshot taken and read
costs ~zero; being wrong about a visual claim costs the user's trust.

## Why this protocol exists

Theme work is *visual*. Every textual proxy — selector chains, CSS rules,
contrast math — can pass while the rendered output still looks broken.
And in the LuCI run the user repeatedly caught issues that the agent had
"verified" without actually loading the screenshot into vision context.

The fix is mechanical: every iteration ends with the agent loading the dark
screenshots as image content (not paths in prose) and reporting what they
show. If the screenshot doesn't appear in your vision context, you have not
verified it.

## When the render gate applies (always, after any edit)

After **every** edit to the userscript or a fixture, before any claim
about whether the change works:

```bash
python scripts/screenshot.py
```

The harness's V8 syntax pre-check + the produced PNGs are the artifacts
that discharge Iron Law #3. The PNGs alone, without the syntax check, do
not — a stray backtick would yield identical-looking baselines.

## When the vision gate applies

Always, when making a claim about visuals. Never optional. Specifically:

- After every screenshot run, before saying "the change rendered correctly".
- After a regression report, before saying "I reproduced it" or "I fixed it".
- Before declaring a fixture done, an iteration done, the theme done.
- When the user pushes back on a visual point — Read the PNG *again*; the
  prior reading is in a previous turn and is not in your current context.

When the vision gate does **not** apply:

- Mechanical work: editing CSS rules, refactoring selectors, renaming
  tokens. (But the next claim about the result requires the gate.)
- Pure logic: contrast.py output is structured, parseable text — read it
  directly without a PNG. (But contrast.py is not a substitute for the
  vision gate; it covers a strict subset of visual issues.)

## The vision pass

After every screenshot run, for each fixture **and each declared
interactive state of that fixture**:

1. **Read the dark image.** Use the Read tool on
   `screenshots/dark/<label>.png` and on each
   `screenshots/dark/<label>--<state>.png`. The tool returns image
   content directly into context — this is how Claude actually sees it.
2. **Read the light image too** for the same fixture/state pair. Visual
   diff is the sharpest tool you have.
3. **Walk the checklist below**, written into the response *as you look*,
   not after.

**The vision gate applies per state, not per fixture.** A static
screenshot passing does not discharge the gate for a hover, focus, or
modal-open state of the same fixture. The Routing/NAT Offloading
regression slipped because the dropdown was visible by default; if the
state had instead been hover-only and we had only checked the static
PNG, we'd have shipped the regression. Don't.

If a state's PNG was not produced (the fixture didn't declare it), that
is a *coverage gap*, not a free pass — escalate via the regression
assessment Branch 1b in `templates/regression-assessment.md`.

## Per-fixture checklist (run for each)

For each rendered page, check:

### Surfaces & depth

- [ ] Page bg is the deepest tier (`--bg`, ~`#121417`).
- [ ] Header / sidebar / footer are `--bg-1`, visibly darker than `--bg-2`
  cards but lighter than `--bg`.
- [ ] Cards, modals, dropdown popovers sit on `--bg-2`, with a 1px
  `--border` outline so they read as raised.
- [ ] No "white box" surprise — every region has been re-toned.

### Text

- [ ] All body text is `--fg` (~14:1 against its bg).
- [ ] Secondary / muted text is `--fg-2` (~7.5:1) — visibly distinct from
  primary, but legible.
- [ ] No `--fg-3` on small text (it fails AA below 18px).
- [ ] Text inside coloured fills (status pills, accent buttons) uses the
  matching `--on-*` token, not `--fg`.
- [ ] No legacy browser-blue link (`#0000EE`) anywhere.

### Interactive states

- [ ] Buttons have visible borders or a tonal bg (not invisible).
- [ ] Active sidebar / tab item has the accent stripe + tonal bg + bold
  weight pattern.
- [ ] Hover state visible on at least row hover and button hover.
- [ ] Focus ring is visible — Tab through the page mentally and confirm
  every interactive target shows a `--border-2` outline.
- [ ] Native checkboxes / radios pick up `accent-color`.

### Status / colour

- [ ] Success / warning / danger fills carry their `--on-*` text colour
  (dark text on bright fill is the WCAG-AA-passing pattern).
- [ ] Status pills don't look pastel-out-of-place against the dark page —
  they should read as saturated, not greyed-out.
- [ ] Code blocks / terminal output use `--bg-code` (deepest), monospace.

### Stacking / overlays

- [ ] Hover tooltips render fully, aren't clipped.
- [ ] Dropdown popovers escape their parent card.
- [ ] Modal overlays cover the full viewport with `--shadow` scrim.
- [ ] Z-index order: modal > dropdown > tooltip > toast > sticky header > body.

### Mobile (run at 414×896)

- [ ] Sidebar collapses or transforms appropriately.
- [ ] Tappable targets ≥ 44px hit-area.
- [ ] Tabular data wraps or scrolls horizontally — no clipping.
- [ ] Pseudo-element `content` properties survive responsive breakpoints
  (the LuCI mobile-header bug).

### Interactive states (per declared state PNG)

For each `<label>--<state>.png`, beyond the static checklist:

- [ ] **Hover states:** background or border or fg shift is visible —
  not subtle. The tonal→filled or +brightness progression should be
  perceivable at a glance.
- [ ] **Hover states:** any tooltip or popover that hover triggers
  renders fully, isn't clipped, and respects z-index order.
- [ ] **Focus states:** `:focus-visible` outline is on every
  focusable element, with sufficient offset to clear native chrome.
- [ ] **Click-to-open states:** revealed content (modal/dropdown/details
  body) inherits the dark surfaces, not light defaults.
- [ ] **Click-to-open states:** opener element's pressed/active state
  is visually distinct from its rest state.
- [ ] **Alternate viewport states:** layout reflows cleanly; no
  overflow, clipped chrome, or missing pseudo-elements.
- [ ] **`prefers-contrast: more`:** borders thicken / contrast lifts
  visibly compared to default; no regression to light defaults.
- [ ] **`prefers-reduced-motion`:** transitions stripped or shortened;
  layout/colour identical to default state.
- [ ] **`forced-colors: active`** (Windows high-contrast): theme yields
  to system colors gracefully — text remains readable.

If a declared state PNG is missing or fails the checklist, that is the
single most common source of post-ship regressions. Treat as blocking.

## Cache-busting (the "still on 0.1.5" problem)

The user installs your script through Tampermonkey, which caches via:

1. **`@updateURL` polling interval** — Tampermonkey defaults to 24h. Force
   a check: dashboard → script → "Check for userscript updates".
2. **GitHub raw / gist CDN** — caches `?` URLs aggressively. Bust with a
   query string: `https://gist.../raw/dark-mode.user.js?v=3`.
3. **The browser** caches the page itself.
4. **The userscript manager's compiled cache** — Tampermonkey re-compiles
   on version bump, *not* on content change.

**Iteration discipline:**

- Bump `@version` on **every** push. Even mid-debug. The userscript manager
  treats same-version pushes as "no change" and does not refresh.
- When sharing a raw URL with the user, append `?v=N` and increment N each
  push.
- If the user reports the script "isn't updating," ask them to:
  1. Open Tampermonkey dashboard.
  2. Click the script.
  3. Check the version number visible in the editor header.
  4. Click "Update" / "Check for updates".
  5. Hard-reload the target page (Cmd/Ctrl-Shift-R).

If they're still on the old version, paste the userscript directly into
Tampermonkey to bypass the gist entirely while debugging.

## Pre-screenshot syntax check

The screenshot harness (`scripts/screenshot.py`) runs a real V8 syntax check
before screenshotting. It is the single most valuable check because:

- A backtick error inside a CSS template literal compiles to "no CSS
  injected, screenshot looks like the unstyled fixture, you assume the
  rules don't match."
- Tampermonkey reports the syntax error in the user's browser console at
  load time — but only if they install the broken script. The pre-check
  catches it offline.

If the harness errors with `userscript syntax check failed: ...`, fix
before doing anything else. Do not screenshot a syntactically broken
script and try to interpret the result.

## Element-level contrast pass

After vision review, run `scripts/contrast.py`. It walks every text node in
each fixture, reads the computed `color` and the *effective* background
(walking up through transparent ancestors until it hits an opaque one), and
flags pairs below WCAG AA. Treat its output as a checklist — fix every
flagged element.

The agent-eye contrast guess is unreliable. The mechanical check is not.

## What "done" looks like

A fixture is "done" when:

1. Light and dark screenshots both load cleanly into vision context.
2. The dark screenshot, scanned via the per-fixture checklist above,
   surfaces zero unaddressed items.
3. `contrast.py` reports zero failures for the fixture.
4. Mobile variant (if applicable) passes the same.

A theme is "done" when every fixture is done **and** the user has seen the
deployed userscript on the live site and approved.

The user's "this looks much better" or equivalent is the stop condition,
not the agent's belief. The agent's belief was wrong four times in the
session that produced this skill.
