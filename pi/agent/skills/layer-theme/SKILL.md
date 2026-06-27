---
name: layer-theme
description: Use when the user asks to dark-mode, restyle, re-theme, retone, skin, or layer a custom theme onto an existing website or web app — typically delivered as a Tampermonkey/Greasemonkey/Stylus userscript or a UserStyle. Also use when the user references a previously named saved style ("apply the luci-dark-material style to X") or asks for a Material/Fluent/etc. dark mode for a third-party site. Skip for native app theming, design-system authoring inside a codebase you control, or one-off CSS tweaks to your own page.
---

# Layer Theme

Override the visual layer of a website you don't own — dark mode, brand
re-tone, density adjustments — without forking the source. Deliverable is a
**single userscript file** (or stylesheet) that the user installs via
Tampermonkey / Greasemonkey / Stylus.

The work is fundamentally **archaeological + visual**: read the upstream
designer's intent from their CSS variables and class names, override at the
right tier, and verify with screenshots that the result respects the
underlying UX hierarchy rather than just patching individual selectors.

## Iron Laws

These are the failure modes this skill exists to prevent. They came from a
single day of theming work that hit each one. Do not skip them.

1. **Vendor the real CSS.** Never approximate the target's stylesheet. Save
   it under `theme-vendor/` and link to it from your fixtures. Approximated
   CSS produces approximated bugs.
2. **Study before selecting.** Spend the first phase reading upstream's
   custom-property API and class taxonomy. Almost every site has a public
   `--var` API that re-tones half the UI for free if you override it. Find
   it before writing selector rules.
3. **Render gate (Playwright is mandatory).** No claim that a CSS or JS
   change "works" without a fresh artifact from `scripts/screenshot.py`
   produced *after* that change. Reasoning about cascade, selector
   specificity, or what the rule "should" do does not satisfy this gate. If
   the harness hasn't run since your last edit, you don't know yet.
4. **Vision gate (Read the PNG).** No claim about how the rendered page
   *looks* — alignment, contrast, "looks good now," "I see it" — without
   having just used the Read tool on the relevant `screenshots/dark/*.png`
   in this turn. Analytical reasoning about what the screenshot would
   show is **not** a substitute for actually loading it. The cost of one
   extra Read is ~zero; the cost of being wrong is the user typing
   "why can't you see this?" for the third time. If you catch yourself
   inferring visual outcomes from CSS rules instead of from a PNG, you
   are violating this gate. See `references/vision-verification.md`
   § "The overconfidence trap".
5. **Cache-bust every iteration.** Browser cache, gist CDN, and userscript
   manager update intervals all conspire against you. When the user reports
   "I'm still on 0.1.5", they're not lying — bump version, append `?v=N` to
   raw URLs, and tell them to force-update.
6. **Parse-check the userscript before screenshotting.** A stray backtick
   inside a CSS template literal will silently produce a screenshot that
   looks identical to the unstyled fixture. Use the `scripts/screenshot.py`
   pre-check that runs `new Function(body)` in V8 — it catches every syntax
   error without executing the script.
7. **Avoid stacking-context traps.** Properties like `filter`, `transform`,
   `opacity < 1`, `will-change`, `mix-blend-mode`, `mask`, `clip-path`, and
   `isolation: isolate` create a containing block for positioned descendants.
   If a hover tooltip or dropdown lives inside the styled element, applying
   `filter: saturate(.7)` to the element will clip the tooltip. Prefer
   `color-mix()` on `background-color` over filter-based desaturation.
8. **Element-level contrast, not background-level.** A button can be
   "dark grey on dark page" — passing the page check while failing on
   itself. The contrast pass must compare each text node's computed color to
   its actual rendered background, not to the page bg.
9. **Generality over specificity (the "don't whack-a-mole" rule).**
   A theme's quality is measured by how *few* and how *general* its
   rules are. Every site-specific selector — page IDs, `nth-child`
   indexes, single-element targets — is debt. When the user says
   something looks "half-baked," stop adding rules and produce a
   critique document first; list principles (saturation, weight tier,
   slot pattern, hover progression) and group findings under them.
   When the user says something looks complex, refactor to use the
   framework's class families before adding more selectors. The fix
   list falls out of the principles, not the symptoms. See
   `references/design-principles.md` § "Generality is a quality
   metric".

## When to use

Trigger when the user asks for any of:

- "Make a dark mode for `<site>`"
- "Restyle / reskin / re-tone this web app"
- "Tampermonkey theme", "Greasemonkey theme", "Stylus userstyle"
- "Apply the `<saved-name>` style to `<new-site>`" (look in `themes/`)
- "Theme this LuCI / Grafana / phpMyAdmin / etc. install"

Do **not** trigger for: native-app theming (Electron-but-native count varies —
ask), design-system authoring in a codebase the user controls (use
`frontend-design`), or single-page CSS tweaks to a file the user owns.

## The 6-phase workflow

Each phase has a gate. Don't move on until the gate passes.

### Phase 1 — Capture intent

Ask, in one round, only what you can't infer:

- **Site URL or live install** the theme should apply to.
- **Goal:** dark mode, brand re-tone (which brand?), density, accessibility,
  or pure aesthetic preference.
- **Named-style reuse?** If the user says "use the X style", check
  `themes/X.md` exists and load it as the design spec for this run. Skip the
  study phase and go straight to fixture rig.
- **Delivery format:** Tampermonkey/Greasemonkey userscript (most common,
  ships JS too), Stylus userstyle (CSS-only), or a paste-into-DevTools
  stylesheet.
- **Browser access:** can you reach the live site, or only static HTML the
  user pastes / saves? See `references/upstream-acquisition.md`.

If the answers are obvious from context (e.g. user says "dark mode for my
LuCI router"), don't interrogate — proceed.

### Phase 2 — Acquire upstream

Read `references/upstream-acquisition.md`. The short version:

1. **Identify the upstream project.** Search GitHub / the site's source for
   the actual theme repo (e.g. `luci-theme-material`, `grafana/grafana`).
   Note the license — your output should match (Apache, MIT, etc.).
2. **Look for an existing community theme.** Read
   `references/existing-themes.md`. For popular sites (GitHub, YouTube,
   Reddit, Twitter, Grafana, phpMyAdmin), there are mature dark themes on
   userstyles.world / Stylus / Greasy Fork — fetch and study them as
   reverse-engineered design references. Do not copy wholesale. Cite them
   in the userscript header if used as inspiration.
3. **Vendor the upstream CSS.** Download every stylesheet the site loads
   into `theme-vendor/` (preserve filenames). Also vendor logos / icon SVGs
   you'll need to invert. If the source is unreachable from the agent
   environment, ask the user to save the page (Save Page As → Webpage,
   Complete) and drop the resulting folder in.
4. **Vendor representative HTML.** Pick 5–8 high-traffic pages and save
   them as static fixtures under `fixtures/`. Strip dynamic JS; rewrite
   `<link>` hrefs to point at `theme-vendor/`. The LuCI run vendored login,
   overview, interfaces, firewall, system, UCI changes — small enough to
   render quickly, broad enough to surface most components.

**Gate:** the fixtures load and render in the browser without console errors,
matching the live site's appearance pixel-roughly.

### Phase 3 — Design study

Read `references/design-principles.md`. Then:

1. **Find the public CSS variable API.** Grep the upstream CSS for
   `--`-prefixed custom properties. Most modern frameworks expose 20–60 of
   them as the public theming contract — re-mapping these is Tier 1, the
   highest-leverage work.
2. **Find the hardcoded color literals.** Grep for `#[0-9a-f]{3,8}`, `rgb(`,
   `rgba(` *outside* the variable definitions. These bypass the var system
   and need direct selector overrides — Tier 2.
3. **Find the class taxonomy.** Identify the framework's button/alert/input
   class families (`btn-*`, `cbi-button-*`, `mat-flat-button`, etc.). They
   are the targets for Tier 3 (semantic re-coloring).
4. **Map elevation tiers.** Sites usually have 3–5 surface depths
   (page bg, header/sidebar, card, hover row, selected row). Name them.
5. **Inventory what's "half-baked".** Open the live light-mode site and
   note papercuts unrelated to dark mode — center-aligned tabular data,
   missing focus rings, illegible disabled states. Bundle these fixes;
   reviewers value the polish.

**Gate:** produce a `critique.md` (template in `templates/critique.md`) that
lists every Tier 1 var, every Tier 2 literal range, every class family, and
every papercut found. This is the design brief. Show it to the user before
writing CSS.

### Phase 4 — Fixture rig

1. Copy `templates/userscript.user.js` to `<project>/dark-mode.user.js` (or
   similar). Fill in the metadata block (`@match`, `@version`, `@homepageURL`).
2. Copy `scripts/screenshot.py` to `<project>/scripts/`. The harness:
   - Reads `dark-mode.user.js`, extracts the CSS template and the JS body
     separately, runs a real V8 syntax check before doing anything else.
   - Loads each fixture twice — light (no script) and dark (script injected
     with a `GM_addStyle` polyfill that defers append until the parser has
     created `documentElement`).
   - **Renders every declared interactive state** (see step 4 below) for
     each fixture, in both light and dark.
   - Saves to `screenshots/{light,dark}/<label>.png` plus
     `screenshots/{light,dark}/<label>--<state>.png` for each state.
3. `uv venv && uv pip install playwright pillow && playwright install chromium`.
4. **Declare interactive states for every fixture that contains
   interactive elements.** Static screenshots alone are insufficient —
   the LuCI Routing/NAT regression was visible only when a dropdown was
   in its default-open state, and a similar bug in a hover-only state
   would slip through entirely. For each fixture, add a
   `<script id="layer-theme-states">` JSON block declaring the states to
   capture (see `templates/fixture.html` for the full schema).
   Coverage rule of thumb:
   - For every hoverable element *type* in the fixture (button intent,
     link, row, etc.), at least one hover state.
   - For every focusable element type (input, select, textarea), at
     least one focus state.
   - For every disclosure widget (details/summary, dropdown, modal
     trigger), at least one click-to-open state.
   - At least one alternate viewport (mobile if responsive).
   - Where the theme uses `@media (prefers-*)` queries, one state per
     media value covered.
5. Run the harness once before adding any theme rules. Confirm the
   light and dark static images are identical and every declared state
   captures cleanly (the userscript is a no-op at this stage).

**Gate:** `python scripts/screenshot.py` produces a screenshot per
fixture × {light, dark} × {static + every declared state}, all
matching, no console errors. If a fixture has interactive elements but
no declared states, that is an uncovered surface — add states or
explicitly justify why the static state is sufficient.

### Phase 5 — Write, screenshot, vision-verify, iterate

This is the inner loop. **Read `references/vision-verification.md` first**
— specifically § "The overconfidence trap" — and refresh it any time you
catch yourself reasoning about CSS as a substitute for screenshotting.

Two gates apply throughout this phase: the **render gate** (Iron Law #3)
and the **vision gate** (Iron Law #4). Both are mechanical. Neither can
be discharged by analysis.

For each batch of changes:

1. **Prefer one tier per batch.** Tier 1 changes (var-API remaps), Tier 2
   (literal repaints), and Tier 3 (class semantics) each have different
   blast radii and different failure modes. Doing a tier-at-a-time makes
   regressions trivially attributable. Bundle across tiers only when
   the changes are tightly coupled (a Tier-1 var rename that requires a
   Tier-3 selector update to land together) — agent judgment, not a
   hard rule. If you bundle and a regression appears, your bisect cost
   is the price you pay; budget for it.
2. **Re-run the screenshot harness — every batch, no exceptions.**
   `python scripts/screenshot.py`. Render gate (#3): until this completes
   for the current edit, you have no evidence the change rendered. *Do not*
   reason from the diff to the visual outcome. Run the harness.
3. **When a visual claim is needed, load the PNG.** Vision gate (#4):
   any statement about how the page looks must be preceded by `Read
   screenshots/dark/<label>.png` *in the same turn*. This includes
   self-talk ("the sidebar should now…"). If you're tempted to skip the
   Read because the change is "obvious," that is the overconfidence trap
   and you must Read anyway. Compare to `screenshots/light/<label>.png`
   side-by-side. Look for: text inside coloured backgrounds you forgot,
   native widgets (checkbox, scrollbar, selection) still in light mode,
   focus rings missing, status pills with insufficient contrast,
   alignment changes, clipped tooltips.
4. **Run the contrast check.** `scripts/contrast.py` (Playwright) walks
   every text node in each fixture, reads computed color and effective
   background, and flags pairs below WCAG AA (4.5:1 normal, 3:1 large).
   Fix everything it flags before declaring the batch done. This is also
   mechanical — *not* a substitute for the vision gate, which catches
   issues contrast.py misses (alignment, layout breakage, missing
   elements, layered z-index bugs).
5. **Repeat until clean.**

### When the user reports a regression

A regression report is a signal worth more than the bug itself — it
identifies a *class* of defect the rig didn't catch. Patching without
classifying loses that signal.

**Before patching, run the 4-branch assessment** in
`templates/regression-assessment.md`. Copy it next to the project as
`regression-<short-slug>.md` and fill it in. The branches:

1. **1a — Vision saw it but didn't flag it** → add the missing check to
   the per-fixture checklist in `references/vision-verification.md`.
2. **1b — Vision didn't see it** → either fixture coverage gap (add a
   fixture / page), state coverage gap (add an interactive state to the
   fixture's `layer-theme-states` block), or vision-gate-skipped
   (sharpen the gate language).
3. **2 — Violates a general UX principle** → add the principle to
   `references/design-principles.md` (or sharpen an existing entry that
   was buried).
4. **3 — User preference, not principle** → save as `feedback` memory,
   *not* a principle.
5. **4 — Site-specific corner case** → record in `themes/<style-name>.md`
   gotchas, *not* the global skill.

Then reproduce the regression in a fixture (or interactive state) and
fix. A fixture for the bug stays as a regression test for future
iterations. Add a one-line entry to `themes/<style-name>.md` under
"Regressions caught" with date, branch, and where the fix propagated.

This is the skill's self-improvement loop. Skipping it means the next
theme — and the next user — meet the same failure mode.

**Gate:** all fixtures pass vision review (you can describe them from a
PNG you just Read, and they look intentional, not patched), and
contrast.py reports zero failures.

### Phase 6 — Finalize and name the style

Once the user signs off ("looks much better"):

1. **Generality self-check.** Read `references/design-principles.md` §
   "Generality is a quality metric". Walk every rule in the userscript
   and ask: *would this rule make sense on a different site that uses
   the same framework family?* Flag every rule that targets a single
   page ID, an `nth-child` index, a single text node, or other
   site-specific debt. For each flagged rule, push it back to a Tier 3
   class family if one exists; if none does, consider whether a small
   JS tagger could *create* a class family (the
   `data-action`/`data-luci-action` pattern in the template). The goal:
   the smaller and more general the final ruleset, the more durable the
   theme — and the cleaner the eventual saved style spec.
2. **Code-simplification pass.** Read `references/design-principles.md` §
   "Simplification". Common reductions: collapse over-specific selector
   chains (`table > tbody > tr > td` when `tr > td` already wins), merge
   per-intent button rules into slot patterns (`--btn-bg/fg/bd/hover`),
   replace scattered font-weight literals with three named tiers, replace
   hardcoded transition durations with one token. Re-screenshot after each
   reduction; revert any that break visuals.
3. **Save the named style.** Copy `templates/theme-spec.md` to
   `themes/<style-name>.md` (kebab-case, descriptive — `luci-dark-material`,
   `grafana-mono-amber`). Fill in the palette, weight tiers, slot patterns,
   elevation tiers, status semantics, focus-ring spec, and any
   site-agnostic principles that came up. The theme-spec is the
   reusable artifact; the userscript is the site-specific instance.
4. **Save a memory pointer.** Write a `reference`-type memory entry in the
   user's memory system pointing at the saved theme spec, so future
   conversations can find it by name. Format:
   ```
   - [Saved theme: <name>](theme_<name>.md) — <one-line aesthetic summary>
   ```
5. **Ship the userscript.** If publishing as a gist, use a versioned URL
   so the userscript manager auto-updates. Tell the user to bump the
   `@version` and append `?v=N` to the raw URL the first time, since
   the gist CDN caches aggressively.

**Gate:** `themes/<name>.md` exists, the userscript ships, the memory
pointer is saved.

## Reusing a saved style

When the user says "apply the `<name>` style to `<new-site>`":

1. Read `themes/<name>.md` — this is the design spec.
2. Skip Phase 3 (study); go straight to Phase 4 (fixture rig) using the new
   site's CSS, applying the spec's palette and patterns.
3. Don't expect a clean port. Sites have different class taxonomies, and
   you'll still spend Tier 2 work on the new site's hardcoded literals. But
   the palette / weight tiers / slot patterns transfer directly.

## Outputs

By the end of a successful run, you've produced:

- `<project>/dark-mode.user.js` (or similar) — the deliverable.
- `<project>/theme-vendor/` — vendored upstream CSS + assets.
- `<project>/fixtures/*.html` — synthetic test pages.
- `<project>/scripts/screenshot.py` + `contrast.py` — the test rig.
- `<project>/screenshots/{light,dark}/` — baseline visuals.
- `<project>/critique.md` — the Phase-3 design brief.
- `themes/<name>.md` (in this skill's directory) — the reusable style spec.
- A memory pointer.

## See also

- `references/upstream-acquisition.md` — vendoring + asking the user.
- `references/design-principles.md` — the principles checklist.
- `references/vision-verification.md` — Claude Vision protocol.
- `references/existing-themes.md` — community theme sources for popular sites.
- `templates/critique.md`, `templates/theme-spec.md`, `templates/userscript.user.js`, `templates/fixture.html`.
- `scripts/screenshot.py`, `scripts/contrast.py`.
- `themes/` — the named-style catalog. Browse it before starting; reuse beats reinvention.
