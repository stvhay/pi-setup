# Theme spec — `<style-name>`

A site-agnostic, reusable visual style. Save as
`themes/<style-name>.md`. Reference it on a future project by saying
"apply the `<style-name>` style to `<site>`".

## One-line aesthetic summary

`<e.g.: Material dark surfaces, OpenWrt-cyan accent, three-tier weight,
slot-based button intents, 14% tonal sidebar-active>`

## Origin

- First implemented for: `<site / project>`
- Date finalized: `<YYYY-MM-DD>`
- Reference userscript: `<URL or path>`

## Palette

```css
:root {
    /* Surfaces */
    --t-bg:        #121417;
    --t-bg-1:      #1a1d22;
    --t-bg-2:      #21252b;
    --t-bg-3:      #2d3239;
    --t-bg-4:      #393f48;
    --t-bg-code:   #0c0e11;

    /* Text */
    --t-fg:        #e6e8eb;
    --t-fg-2:      #a4a9b0;
    --t-fg-3:      #6c7178;
    --t-fg-link:   #4ad0f4;

    /* Borders / shadow */
    --t-border:    #363b43;
    --t-border-2:  #444a54;
    --t-shadow:    rgba(0, 0, 0, 0.45);

    /* Accent */
    --t-accent:     #22c1f0;
    --t-accent-2:   #4ad0f4;
    --t-accent-dim: #155a72;
    --t-on-accent:  #062330;

    /* Status */
    --t-success:   #5ec979;
    --t-on-success:#0a1d10;
    --t-warning:   #f1c453;
    --t-on-warning:#2a1e00;
    --t-danger:    #e57373;
    --t-on-danger: #2a0d0d;
}
```

## Weight tiers

```css
--t-fw-body:   400;   /* body / ambient — default cascade */
--t-fw-medium: 500;   /* interactive: buttons, sidebar/tab active, h1–h3 */
--t-fw-bold:   600;   /* small-text emphasis: chips, pills, labels <13px */
```

## Transition

```css
--t-trans: 150ms ease;
```

## Tonal surfaces

```css
--t-accent-tonal-bg: color-mix(in srgb, var(--t-accent) 14%, transparent);
--t-accent-tonal-bd: color-mix(in srgb, var(--t-accent) 35%, transparent);
```

(Used for sidebar-active, alert-info, selected-row hover.)

## Slot patterns

Buttons:
```css
.btn { background: var(--btn-bg); color: var(--btn-fg);
       border: 1px solid var(--btn-bd);
       transition: background var(--t-trans), color var(--t-trans); }
.btn-primary { --btn-bg: var(--t-accent);  --btn-fg: var(--t-on-accent);  --btn-bd: var(--t-accent); }
.btn-success { --btn-bg: var(--t-success); --btn-fg: var(--t-on-success); --btn-bd: var(--t-success); }
.btn-danger  { --btn-bg: var(--t-danger);  --btn-fg: var(--t-on-danger);  --btn-bd: var(--t-danger); }
.btn-neutral { --btn-bg: var(--t-bg-2);    --btn-fg: var(--t-fg);         --btn-bd: var(--t-border-2); }
```

## Active sidebar / tab pattern

3px accent stripe + 14% tonal bg + medium weight + primary fg.

```css
.sidebar-item.active {
    background: var(--t-accent-tonal-bg);
    box-shadow: inset 3px 0 var(--t-accent);
    color: var(--t-fg);
    font-weight: var(--t-fw-medium);
}
```

## Focus ring

```css
:focus-visible {
    outline: 2px solid var(--t-border-2);
    outline-offset: 2px;
}
```

## Native widgets

```css
:root { color-scheme: dark; accent-color: var(--t-accent); }
::selection { background: var(--t-accent-dim); color: var(--t-fg); }
::-webkit-scrollbar { background: var(--t-bg-1); }
::-webkit-scrollbar-thumb { background: var(--t-border-2); border-radius: 6px; }
```

## Status semantics

- Bright fill + dark on-* text (passes WCAG AA at ≥7:1).
- Tonal versions for inline alerts (color-mix at 14%).

## Notes / gotchas

- `<any site-agnostic gotchas surfaced during implementation>`

## Tier-1 variable mapping (site-agnostic core)

Variables most frameworks expose (or should). When reusing, map upstream
to ours:

| Concept | Token |
|---|---|
| Page bg | `--t-bg` |
| Surface bg | `--t-bg-2` |
| Primary text | `--t-fg` |
| Brand accent | `--t-accent` |
| ... | ... |
