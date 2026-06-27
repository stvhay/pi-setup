# Critique — `<site-name>` theme

Phase 3 design brief. Produced *before* writing CSS. The user reviews this
and signs off; then implementation is mechanical.

## Upstream framework

- Project: `<repo / framework name>`
- Vendored at: `theme-vendor/` (commit / version `<ref>`)
- License: `<Apache-2.0 / MIT / GPL>`

## Tier 1 — Public CSS-variable API

Found `<N>` `--*` custom properties in `<file>`:

| Variable | Default | Re-map to |
|---|---|---|
| `--upstream-bg-color` | `#fff` | `var(--t-bg)` |
| ... | ... | ... |

## Tier 2 — Hardcoded color literals

Categories of selectors that need direct overrides (each row = one
semantic group of literal colors that the upstream stylesheet bakes in
without going through the var system):

| Group | Selectors | Upstream color | Replace with |
|---|---|---|---|
| Page bg | `html`, `body`, `.main` | `#fff` | `var(--t-bg)` |
| Card surface | `.card`, `.panel` | `#f6f6f6` | `var(--t-bg-2)` |
| Table stripe | `tr:nth-child(even)` | `#f0f0f0` | `var(--t-bg-3)` |
| Code block | `pre`, `code` | `#eee` | `var(--t-bg-code)` |
| Border | `.card`, `input`, `table` | `#ccc`/`#ddd` | `var(--t-border)` |
| Text grey | various | `#404040`–`#999` | `var(--t-fg)`/`--t-fg-2` |

## Tier 3 — Class taxonomy

Button intents:
- `.btn-primary` → `--t-accent` fill
- `.btn-success` → `--t-success` fill
- `.btn-danger` → `--t-danger` fill
- `.btn-neutral` / default → `--t-bg-2` fill, `--t-border-2` border

Alert variants:
- `.alert-info` → tonal accent surface
- `.alert-success` → `--t-success` fill, `--t-on-success` text
- ...

Input states:
- normal → `--t-bg-2` fill, `--t-border` outline
- `:focus-visible` → 2px `--t-border-2` outline, offset 2px
- `:disabled` → `--t-bg-1` fill, `--t-fg-3` text

## Elevation tiers

Mapping of upstream surfaces to our 5 tiers:

| Surface | Upstream | Our tier |
|---|---|---|
| Page bg | `body` | `--t-bg` |
| Header / sidebar / footer | `<header>`, `nav.sidebar` | `--t-bg-1` |
| Card / panel / modal | `.card`, `.panel`, `.modal` | `--t-bg-2` |
| Hover row, dropdown | `tr:hover`, `.dropdown-menu` | `--t-bg-3` |
| Selected / focused row | `tr.selected` | `--t-bg-4` |
| Code | `pre`, `code` | `--t-bg-code` |

## Papercuts (light-mode bugs we'll fix while we're here)

Things broken in upstream regardless of dark-mode:

1. `<describe>`
2. `<describe>`
3. `<describe>`

## Stacking-context risks

Elements that contain positioned descendants (tooltip, dropdown). If we
need to apply a visual effect (desaturation, etc.), use `color-mix` not
`filter`:

- `.zone-badge` contains `.tooltip` — no `filter`, `transform`, `opacity`,
  `will-change`, `mix-blend-mode`, `mask`, `clip-path`, `isolation`.
- ...

## Things we are explicitly NOT changing

(Set scope clearly so the reviewer knows what's out of bounds.)

- `<list>`

---

**Reviewer:** sign off below to authorize implementation.

- [ ] Tier 1 variable map looks right
- [ ] Tier 2 selector groups complete
- [ ] Tier 3 intents complete
- [ ] Papercut list complete
- [ ] Scope is right
