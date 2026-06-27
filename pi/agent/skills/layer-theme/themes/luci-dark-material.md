# Theme spec — `luci-dark-material`

## One-line aesthetic summary

Material Design dark — five elevation tiers on near-black, OpenWrt cyan
accent (`#22c1f0`), three-tier weight system, slot-based button intents,
14% tonal sidebar-active. WCAG AA across the board (most pairs at 7:1+).

## Origin

- First implemented for: OpenWrt LuCI Material (`luci-theme-material`)
- Date finalized: 2026-04-26
- Reference userscript: `luci-material-dark-mode/dark-mode.user.js` v0.3.2
- License: Apache-2.0 (matching upstream LuCI theme)

## Palette

```css
:root {
    /* Surfaces — 5 elevation tiers + code */
    --t-bg:        #121417;   /* body / page */
    --t-bg-1:      #1a1d22;   /* sidebar, header, footer */
    --t-bg-2:      #21252b;   /* cards, modals */
    --t-bg-3:      #2d3239;   /* alt-row, hover, dropdown */
    --t-bg-4:      #393f48;   /* selected row, focused dropdown */
    --t-bg-code:   #0c0e11;   /* code blocks, syslog */

    /* Text — primary ~14:1, secondary ~7.5:1, tertiary large-only */
    --t-fg:        #e6e8eb;
    --t-fg-2:      #a4a9b0;
    --t-fg-3:      #6c7178;
    --t-fg-link:   #4ad0f4;

    /* Borders / shadow — visible, not ghosted */
    --t-border:    #363b43;
    --t-border-2:  #444a54;
    --t-shadow:    rgba(0, 0, 0, 0.45);

    /* Accent (OpenWrt brand cyan, lifted into dark) */
    --t-accent:     #22c1f0;
    --t-accent-2:   #4ad0f4;
    --t-accent-dim: #155a72;
    --t-on-accent:  #062330;   /* dark text on cyan, ~9:1 */

    /* Status — dark on-* text on bright fills, ~7:1+ */
    --t-success:   #5ec979;  --t-success-hi:#4eb869;  --t-on-success:#0a1d10;
    --t-warning:   #f1c453;  --t-warning-hi:#e8b440;  --t-on-warning:#2a1e00;
    --t-danger:    #e57373;  --t-danger-hi: #d96565;  --t-on-danger: #2a0d0d;
    --t-error:     #ff6b6b;  --t-on-error:  #2a0d0d;

    /* Notice — derived from accent so it tracks palette customization */
    --t-notice:    color-mix(in srgb, var(--t-accent) 35%, var(--t-bg-2));
    --t-on-notice: #ffffff;
}
```

## Tonal surfaces

Used for sidebar-active, alert-info, selected-row backgrounds. `color-mix`
keeps them tracked to the accent if the user customizes the palette —
hardcoded `rgba()` literals would not.

```css
--t-accent-tonal-bg:  color-mix(in srgb, var(--t-accent)  14%, transparent);
--t-accent-tonal-bd:  color-mix(in srgb, var(--t-accent)  35%, transparent);
--t-success-tonal-bg: color-mix(in srgb, var(--t-success) 14%, transparent);
--t-success-tonal-bd: color-mix(in srgb, var(--t-success) 35%, transparent);
--t-danger-tonal-bg:  color-mix(in srgb, var(--t-danger)  14%, transparent);
--t-danger-tonal-bd:  color-mix(in srgb, var(--t-danger)  35%, transparent);
```

## Weight tiers

```css
--t-fw-body:   400;
--t-fw-medium: 500;   /* buttons, sidebar/tab active, h1–h3, panel-title,
                         table column headers, alert headings */
--t-fw-bold:   600;   /* chips, pills, labels at <13px */
```

## Transition

```css
--t-trans: 150ms ease;
```

Applied to every interactive surface.

## Slot pattern — buttons

```css
.btn {
    background: var(--btn-bg);
    color:      var(--btn-fg);
    border: 1px solid var(--btn-bd);
    font-weight: var(--t-fw-medium);
    transition: background var(--t-trans), color var(--t-trans),
                border-color var(--t-trans);
}
.btn:hover { background: var(--btn-hover, var(--btn-bg));
             filter: brightness(1.06); }

.btn-action  { --btn-bg: var(--t-accent);  --btn-fg: var(--t-on-accent);  --btn-bd: var(--t-accent);  }
.btn-apply   { --btn-bg: var(--t-success); --btn-fg: var(--t-on-success); --btn-bd: var(--t-success); }
.btn-remove  { --btn-bg: var(--t-danger);  --btn-fg: var(--t-on-danger);  --btn-bd: var(--t-danger);  }
.btn-neutral { --btn-bg: var(--t-bg-2);    --btn-fg: var(--t-fg);         --btn-bd: var(--t-border-2); }
.btn-reset   { --btn-bg: transparent;      --btn-fg: var(--t-fg-2);       --btn-bd: var(--t-border-2); }
```

Same trick scales to alerts (`.alert-success`, etc.) and badges.

## Active sidebar / tab pattern

The "modern Material You / Fluent" look. 3px accent stripe + 14% tonal
background + primary fg + medium weight. Replaces upstream's solid-color
active block (looks dated on dark).

```css
.sidebar-item.active {
    background: var(--t-accent-tonal-bg);
    box-shadow: inset 3px 0 var(--t-accent);
    color: var(--t-fg);
    font-weight: var(--t-fw-medium);
}
```

## Hover progression

- **Tonal → filled** on primary buttons (signals actionability).
- **Brightness +6%** on filled buttons via `filter: brightness(1.06)` —
  safe here because buttons rarely contain positioned descendants.
- **bg-3** background on row hover and inactive sidebar/tab hover.
- **Underline** on text links — never colour-shift.

## Focus ring

```css
:focus-visible {
    outline: 2px solid var(--t-border-2);
    outline-offset: 2px;
}
```

Applied to every interactive element. Even on mouse-only sites.

## Native widget harmonization

```css
:root { color-scheme: dark; accent-color: var(--t-accent); }
::selection { background: var(--t-accent-dim); color: var(--t-fg); }
::-webkit-scrollbar { background: var(--t-bg-1); }
::-webkit-scrollbar-thumb {
    background: var(--t-border-2);
    border-radius: 6px;
}
::-webkit-scrollbar-thumb:hover { background: var(--t-fg-3); }
```

## Status semantics

- Bright fill + dark on-* text (passes WCAG AA at ≥7:1) on actual
  status pills and filled buttons.
- Tonal version (14% color-mix) for inline alerts — readable on dark
  surface without shouting.

## Tabular data alignment

Override upstream's `text-align: center !important` on table cells. IPs,
MACs, names, status text are unscannable when centered.

```css
table td, table th {
    text-align: left !important;
}
table td.actions, table th.actions { text-align: right !important; }
table td.icon-only { text-align: center; }      /* single-icon columns ok */
```

## Mobile pseudo-element gotcha

If responsive media queries toggle `display` on a `::before`/`::after`,
the `content` property may not survive. Restate it:

```css
@media (max-width: 600px) {
    .header::before {
        content: 'Menu';   /* upstream sets this only at >600px */
        display: block;
    }
}
```

(Surfaced as a real upstream LuCI bug. Document in a comment when fixed.)

## Notes / gotchas surfaced during implementation

- **No `filter` on elements containing tooltips.** `.zone-badge` originally
  used `filter: saturate(.7) brightness(.88)`, which created a stacking
  context that clipped the hover tooltip. Replaced with
  `background-color: color-mix(in srgb, var(--zone-color) 70%, var(--t-bg-2))`.
- **Don't unscope link colour resets.** `a { color: var(--t-fg-link) }`
  alone overrides sidebar/tab/breadcrumb link styles. Use a `:not()` chain
  or scope to body content.
- **Dark-on-dark icons** need `filter: invert(1) hue-rotate(180deg)` on
  the `<img>` (sidebar caret, logout glyph in LuCI's case). Safe because
  `<img>` rarely contains positioned descendants.

## Tier-1 variable map (LuCI Material custom.css)

For reference if porting to another LuCI variant. The full list is in the
reference userscript; representative entries:

| Upstream | Maps to |
|---|---|
| `--main-color` | `var(--t-accent)` |
| `--secondary-color` | `var(--t-accent-2)` |
| `--header-bg` | `var(--t-bg-1)` |
| `--menu-bg-color` | `var(--t-bg-1)` |
| `--submenu-bg-hover-active` | `var(--t-accent-dim)` |
| `--green-color` | `var(--t-success)` |
| `--on-green-color` | `var(--t-on-success)` |
| `--red-color` | `var(--t-danger)` |
| `--white-color` | `var(--t-bg-2)` |
| `--black-color` | `var(--t-fg)` |

## Reuse

To apply this style to another site:

1. Read this file as the design spec.
2. Copy the `:root` block above into the target's userscript.
3. Identify the target framework's public-API vars; map them to
   `--t-*` (Tier 1).
4. Find hardcoded literals; override them in semantic groups (Tier 2).
5. Apply the slot pattern, sidebar/tab pattern, focus ring, native-widget
   harmonization verbatim — these are framework-agnostic.

The palette + weight tiers + slot patterns transfer cleanly. Tier 2 work
is always site-specific.
