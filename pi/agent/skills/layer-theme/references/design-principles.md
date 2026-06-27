# Design principles

The checklist that the LuCI session surfaced as load-bearing. Every rule
here exists because skipping it produced a regression or a "half-baked"
critique. Read at the start of Phase 3.

## Generality is a quality metric

A theme is *better* the more general its rules are. Specific rules
("`#admin-status-overview .ifacebox-head` should be light") work today
but rot the moment upstream renames a class. General rules ("text
inside coloured fills uses the matching `--on-*` token") survive
upstream churn, transfer to other sites, and produce a smaller
maintenance surface.

This is the single most important principle in this file. Every other
rule below is in service of generality:

- **Tokens over literals** — one palette change re-tones the whole UI.
- **Slot patterns over per-intent rules** — adding a new button intent
  is a one-line addition, not a new rule block.
- **Class-family selectors over single-element selectors** — `.btn-*`
  catches every button intent at once.
- **Framework-aware tiers (1/2/3)** — work with the framework's design
  language, not against it.

**Phase 6 self-test.** Before declaring the theme done, walk every rule
and ask: *would this rule make sense on a different site that uses the
same framework family?* If the answer is no — if you have selectors
that target a single page, a single ID, an `nth-child` index, or a
specific text node — that's site-specific debt. Push it back to Tier 3
where possible: find the class family the framework already provides
and use it. If no class family exists, that's a signal to consider a
small JS tagger (the "semantic-attribute tagger" pattern in the
template) that *creates* a class family — generalising once at the JS
boundary instead of repeating site-specific selectors.

The LuCI session converged to a complex solution before refactoring it
back to general principles. The user explicitly asked to "study the
source code…to understand the intent of the web designers on how
consistent colors should flow through the design. Doing this may help
us vastly reduce the complexity of this theme." That instruction was
right; bake it in.

**Counter-pattern to recognize.** If you find yourself adding a fourth
or fifth selector for the same logical concept, stop. The framework
has a class family for this. Find it. If you can't find one, check
whether the upstream theme inherits from a known framework
(Bootstrap, Material, Bulma) — those families propagate through.

## The two-tier override architecture

Modern frameworks expose a public CSS-variable API but also bake hardcoded
color literals into the cascade. Override at both tiers.

**Tier 1 — Public variable API.** Re-map the framework's `--color-*` /
`--mdc-theme-*` / `--ant-primary-color` etc. to your dark tokens. This
re-tones every selector that uses `var(--*)`, which is usually the
majority. Highest leverage; do this first.

**Tier 2 — Hardcoded literals.** Grep upstream for `#[0-9a-f]+`, `rgb(`,
`rgba(` *outside* `:root` definitions. Those bypass the var system. Hit
them with semantic selector groups (page bg, card surface, table stripe,
code block, etc.).

**Tier 3 — Class taxonomy semantics.** The framework's button/alert/input
class families need to be re-coloured in your dark palette while preserving
the original *intent* (action vs. neutral vs. destructive vs. status).

## Tokens you should always define

Don't scatter colors across the file. Define a `:root` token block at the top.

```css
:root {
  /* Surfaces — 4–5 elevation tiers for visual depth */
  --bg:        #121417;  /* page */
  --bg-1:      #1a1d22;  /* sidebar / header / footer */
  --bg-2:      #21252b;  /* card / panel / modal */
  --bg-3:      #2d3239;  /* hover row, alt-row, dropdown */
  --bg-4:      #393f48;  /* selected / focused */
  --bg-code:   #0c0e11;  /* code blocks, terminals */

  /* Text — primary / secondary / tertiary */
  --fg:        #e6e8eb;  /* ~14:1 on bg */
  --fg-2:      #a4a9b0;  /* ~7.5:1 secondary */
  --fg-3:      #6c7178;  /* disabled, large UI only — fails AA on small text */
  --fg-link:   #4ad0f4;

  /* Borders — visible, not ghosted */
  --border:    #363b43;
  --border-2:  #444a54;  /* stronger for inputs / focus rings */
  --shadow:    rgba(0,0,0,0.45);

  /* Accent — site brand, lifted into dark-friendly territory */
  --accent:     #22c1f0;
  --accent-2:   #4ad0f4;
  --accent-dim: #155a72;
  --on-accent:  #062330;  /* dark text on bright accent, ~9:1 */

  /* Status — paired with on-* tokens that pass AA on the fill */
  --success:    #5ec979;  --on-success: #0a1d10;
  --warning:    #f1c453;  --on-warning: #2a1e00;
  --danger:     #e57373;  --on-danger:  #2a0d0d;

  /* Tonal surfaces — color-mix() tracks the accent if user customizes it */
  --accent-tonal-bg:  color-mix(in srgb, var(--accent) 14%, transparent);
  --accent-tonal-bd:  color-mix(in srgb, var(--accent) 35%, transparent);

  /* Font-weight — three semantic tiers, NOT scattered literals */
  --fw-body:   400;  /* body / ambient */
  --fw-medium: 500;  /* interactive: buttons, active sidebar/tab, h1–h3 */
  --fw-bold:   600;  /* small-text emphasis: chips, pills, labels at <13px */

  /* Single transition token — uniform interaction feel */
  --trans: 150ms ease;
}
```

The named-style memory writes this exact structure. When reusing a saved
style for a new site, copy the token block and Tier-1 override block;
Tier-2/3 selectors are site-specific.

## Contrast (WCAG AA, non-negotiable)

- Body text vs. its background ≥ **4.5:1**.
- UI text ≥ 18px or ≥ 14px bold ≥ **3:1** ("large text" exemption).
- Non-text UI (icons, focus rings, status indicators) ≥ **3:1** vs. their
  surroundings.
- Disabled text is exempt — but make it visibly disabled, not just dim.

**Status colors on dark.** White text on `#5cb85c` / `#d9534f` / `#f0ad4e`
fails AA at 2.4–3.7:1. Switch to dark text on the bright fill (`#0a1d10` on
green, `#2a0d0d` on red, `#2a1e00` on yellow) — passes at 7:1+.

**Element-level, not page-level.** A button can be "dark grey on dark page,"
passing the page bg check while failing on itself. Use `scripts/contrast.py`
which walks every text node.

**`color-mix` tonal backgrounds.** When you want a 14%-tinted surface for
sidebar-active or alert-info, derive it via `color-mix(in srgb, var(--accent)
14%, transparent)` rather than hardcoding `rgba(34,193,240,0.14)`. Tonal
surfaces then track the accent automatically when the palette is customized.

## Alignment / typography (the "papercut" checklist)

These are upstream UX papercuts — not strictly dark-mode work, but bundle
them. Reviewers value the polish.

- **Tabular data left-aligned.** Many themes apply `text-align: center
  !important` to every section-table cell. IPs, MACs, names, status text
  become unscannable. Override to left; keep action columns right-aligned;
  centre only single-icon button cells.
- **Column titles bold + left-aligned.** Aligned with the values they label.
- **Three-tier font-weight system.** Body (400) / interactive (500) /
  emphasis (600). Don't scatter literal `font-weight: 500` across 7
  selectors — name them.
- **Consistent transitions.** One `--trans: 150ms ease` token, applied to
  every interactive surface. Mismatched durations feel cheap.
- **Visible focus rings.** `:focus-visible { outline: 2px solid
  var(--border-2); outline-offset: 2px; }` on every interactive element.
  Even on mouse-only sites — keyboard users exist.
- **Keep scoped link colors.** Do **not** write `a { color: ... }` without a
  scope or `:not()` — you'll override sidebar/tab/breadcrumb link styles
  that the upstream theme defines specifically. Default unscoped `<a>`
  fall back to browser blue (`#0000EE`) which is unreadable on dark, so a
  reset is needed, but limit it: `body :not(.btn):not(.menu-item) > a`.

## Button slot pattern (kills duplicate rules)

Don't define five separate rule blocks for `cbi-button-action`,
`-apply`, `-reset`, `-remove`, `-neutral`. Define a single slot and let
each intent class set the slot values.

```css
.btn {
  background: var(--btn-bg);
  color: var(--btn-fg);
  border: 1px solid var(--btn-bd);
  transition: background var(--trans), color var(--trans);
}
.btn:hover { background: var(--btn-hover, var(--btn-bg)); }

.btn-action  { --btn-bg: var(--accent);  --btn-fg: var(--on-accent);  --btn-bd: var(--accent); }
.btn-apply   { --btn-bg: var(--success); --btn-fg: var(--on-success); --btn-bd: var(--success); }
.btn-remove  { --btn-bg: var(--danger);  --btn-fg: var(--on-danger);  --btn-bd: var(--danger); }
.btn-neutral { --btn-bg: var(--bg-2);    --btn-fg: var(--fg);         --btn-bd: var(--border-2); }
```

Same trick for alerts, input states, badges. Cuts the file by ~40%.

## Stacking-context traps

These properties create a containing block for absolutely-positioned
descendants. Never apply them to an element whose hover tooltip or
dropdown menu is positioned by being placed inside it:

- `filter` (any value, including `filter: saturate(0.7)`)
- `transform` (any value)
- `opacity < 1` (yes, even 0.99)
- `will-change`
- `mix-blend-mode`
- `mask`, `clip-path`
- `isolation: isolate`
- `perspective`

The LuCI run hit this: zone-badges desaturated with `filter: saturate(.7)
brightness(.88)` worked great visually, but the firewall-zone hover tooltip
sat inside the badge in the DOM, and the filter clipped it. Fix: replace
filter with a `color-mix()` on the background:

```css
/* BAD — creates stacking context */
.zone-badge { filter: saturate(0.7) brightness(0.88); }

/* GOOD — same visual, no stacking context */
.zone-badge {
  background-color: color-mix(in srgb, var(--zone-color) 70%, var(--bg-2));
}
```

## Hover state progression

A consistent vocabulary:

- **Tonal → filled** for primary actions (subtle bg → coloured bg on hover).
  Promises actionability without shouting.
- **Brightness up** for filled buttons (`filter: brightness(1.06)` works
  here because buttons rarely contain positioned descendants — verify).
  Or use `*-hi` token: `--success-hi: #4eb869`.
- **Background +1 tier** for navigation and rows (`bg → bg-3` on hover).
- **Underline** on text-only links — never colour-shift.

## Sidebar / tab active state

The "modern Material You / Fluent" pattern:

- 3px accent stripe on the leading edge.
- Tinted background (`var(--accent-tonal-bg)` ≈ 14% accent over surface).
- Text in primary `--fg`, weight `--fw-medium`.
- Hover state for inactive items: bg-3, no stripe.

Avoid: solid-colour active blocks (looks dated), or no visual change at all.

## Native widget harmonization

Browsers render these in light mode by default unless told otherwise:

- `<input type="checkbox" / radio>` → set `accent-color: var(--accent)`.
- Selection highlight → `::selection { background: var(--accent-dim);
  color: var(--fg); }`.
- Scrollbar (Chromium) → `::-webkit-scrollbar { background: var(--bg-1); }`
  + `::-webkit-scrollbar-thumb { background: var(--border-2); }`.
- `<details>` triangle, `<input type="date">` calendar — these are vendor
  UA chrome and may resist theming. Use `color-scheme: dark` on `:root`
  to flip browser-controlled UI.

## Icon visibility

Sidebar carets, logout glyphs, status icons that are dark SVG-on-dark:
- If they're inline SVG with `currentColor`, set the parent's `color`.
- If they're `<img>` of dark SVG/PNG, `filter: invert(1) hue-rotate(180deg)`
  is a quick fix. (Yes, `filter` — but `<img>` rarely contains positioned
  descendants, so it's safe here.)
- Better: vendor a copy of the icon and tweak its fill, or replace with a
  CSS background using `mask-image`.

## Responsive / media-query gotcha

Toggling `display` on a pseudo-element inside a media query can drop the
`content` property. If `::before` works on desktop but vanishes on mobile,
restate `content`:

```css
@media (max-width: 600px) {
  .header::before {
    content: 'Menu';   /* upstream may have set this only at >600px */
    display: block;
  }
}
```

## Simplification (Phase 6 pass)

Common reductions that are safe:

1. **Over-specific selector chains.** `table > tbody > tr > td` collapses to
   `tr > td` if specificity already wins. Verify with screenshots.
2. **Duplicated intent rules → slot pattern** (see button slot above).
3. **Hardcoded weights → named tiers.** `font-weight: 500` × 7 → `var(--fw-medium)`.
4. **Hardcoded transitions → single token.**
5. **Hardcoded rgba() shadows / tints → color-mix() over tokens.**

Common reductions that are **unsafe** without verification:

- **Hedged selectors** (`.input:focus` AND `.input-text:focus`) when the
  framework applies the latter class to non-`<input>` widgets. Run the full
  screenshot suite and the contrast pass after removal; revert if anything
  regresses.
- **!important removal** — `!important` was usually added because something
  else won. Remove only if you can prove nothing relies on the precedence.
