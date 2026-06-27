---
name: design-principles
description: Use when implementing GUI interfaces - dashboards, admin interfaces, SaaS products, web applications requiring professional polish
---

# Design Principles

Enforce precise, crafted design for enterprise software, SaaS dashboards, admin interfaces, and web applications. Every interface is polished and designed for its specific context.

## Design Direction (Required First Step)

**Commit to a design direction before writing code.** Consider:

- **What does this product do?** Finance tools need different energy than creative tools.
- **Who uses it?** Power users want density; occasional users want guidance.
- **What's the emotional job?** Trust? Efficiency? Delight? Focus?

### Personality Options

**Precision & Density** — Tight spacing, monochrome, information-forward. For power users. Think Linear, Raycast.

**Warmth & Approachability** — Generous spacing, soft shadows, friendly colors. Think Notion, Coda.

**Sophistication & Trust** — Cool tones, layered depth, financial gravitas. Think Stripe, Mercury.

**Boldness & Clarity** — High contrast, dramatic negative space, confident typography. Think Vercel.

**Utility & Function** — Muted palette, functional density, clear hierarchy. Think GitHub.

**Data & Analysis** — Chart-optimized, technical but accessible. For analytics and BI.

**Brutalist & Raw** — Exposed structure, monospaced type, stark contrast, no decoration. Think Craigslist-meets-architecture. For tools that wear their engineering proudly.

**Retro-Futuristic** — Neon accents on dark surfaces, geometric shapes, synthwave palette. For creative tools, entertainment, gaming contexts.

**Maximalist & Expressive** — Rich gradients, layered textures, bold color combinations, elaborate animations. For marketing, landing pages, consumer products where delight matters.

**Editorial & Typographic** — Typography-driven, generous whitespace, magazine-like layouts. Distinctive display fonts paired with refined body text. For content-heavy products, publications.

**Organic & Natural** — Soft edges, muted earth tones, hand-drawn feel, flowing layouts. For wellness, sustainability, community-focused products.

Pick one or blend two. Commit.

### Color Foundation

**Match foundation to product context:**
- Warm foundations (creams, warm grays) — approachable, human
- Cool foundations (slate, blue-gray) — professional, serious
- Pure neutrals (true grays, black/white) — minimal, technical
- Tinted foundations — distinctive, branded

**Light vs dark:** Dark feels technical, focused, premium. Light feels open, approachable.

**Accent color:** Pick ONE. Blue for trust. Green for growth. Orange for energy. Violet for creativity.

### Layout Approach

- **Dense grids** for information-heavy interfaces
- **Generous spacing** for focused tasks
- **Sidebar navigation** for multi-section apps
- **Top navigation** for simpler tools
- **Split panels** for list-detail patterns

### Typography

Choose typography that serves the design direction. Avoid defaulting to any font without intention.

- **System fonts** — fast, native feel (utility-focused directions)
- **Geometric sans** (Geist, Inter) — modern, technical (appropriate for Precision, Utility, Data directions)
- **Humanist sans** (SF Pro, Satoshi) — warmer, approachable (Warmth, Organic directions)
- **Monospace influence** — technical, data-heavy (Precision, Brutalist, Data directions)
- **Distinctive display fonts** — characterful, memorable (Editorial, Maximalist, Retro-Futuristic directions). Pair with refined body fonts for contrast.

> **Anti-pattern:** Using the same font (Inter, Roboto, Arial) across every project regardless of direction. Typography is the single strongest aesthetic signal — choose it intentionally.

## Core Craft Principles

Apply regardless of design direction.

### 4px Grid

All spacing uses 4px base:
- `4px` - micro (icon gaps)
- `8px` - tight (within components)
- `12px` - standard (related elements)
- `16px` - comfortable (section padding)
- `24px` - generous (between sections)
- `32px` - major separation

### Symmetrical Padding

TLBR must match. Exception: when content naturally creates visual balance.

```css
/* Good */
padding: 16px;
padding: 12px 16px; /* Only when horizontal needs more room */

/* Bad */
padding: 24px 16px 12px 16px;
```

### Border Radius

Stick to 4px grid. Sharper = technical, rounder = friendly.
- Sharp: 4px, 6px, 8px
- Soft: 8px, 12px
- Minimal: 2px, 4px, 6px

Don't mix systems.

### Depth Strategy

Match depth approach to design direction:

**Borders-only (flat)** — Clean, technical, dense. Linear, Raycast style. Intentional restraint, not laziness.

**Subtle single shadows** — Soft lift. `0 1px 3px rgba(0,0,0,0.08)` is often enough.

**Layered shadows** — Rich, premium. Stripe/Mercury style. Best for cards as physical objects.

**Surface color shifts** — Background tints establish hierarchy without shadows.

Choose ONE approach. Mixing flat borders with heavy shadows creates inconsistency.

```css
/* Borders-only */
border: 0.5px solid rgba(0, 0, 0, 0.08);

/* Single shadow */
box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);

/* Layered shadow */
box-shadow:
  0 0 0 0.5px rgba(0, 0, 0, 0.05),
  0 1px 2px rgba(0, 0, 0, 0.04),
  0 2px 4px rgba(0, 0, 0, 0.03),
  0 4px 8px rgba(0, 0, 0, 0.02);
```

### Card Layouts

Card layouts should vary by content. Metric cards ≠ plan cards ≠ settings cards. Design internal structure for specific content, but keep surface treatment consistent: same border weight, shadow depth, corner radius, padding scale, typography.

### Isolated Controls

UI controls deserve container treatment. Never use native form elements for styled UI—native `<select>`, `<input type="date">` render OS-native controls that cannot be styled.

Build custom components:
- Custom select: trigger button + positioned dropdown
- Custom date picker: input + calendar popover
- Custom checkbox/radio: styled div with state management

**Custom select triggers must use `display: inline-flex` with `white-space: nowrap`** to keep text and chevron on same row.

### Typography Hierarchy

- Headlines: 600 weight, -0.02em letter-spacing
- Body: 400-500 weight, standard tracking
- Labels: 500 weight, slight positive tracking for uppercase
- Scale: 11px, 12px, 13px, 14px (base), 16px, 18px, 24px, 32px

### Spatial Composition

Layout should serve the design direction, not default to predictable patterns.

- **Structured grids** — For enterprise, data, utility directions. Predictable, scannable.
- **Asymmetric layouts** — For editorial, maximalist directions. Break grid with intentional elements.
- **Dramatic negative space** — For boldness, sophistication. Let key elements breathe.
- **Layered depth** — For maximalist, retro-futuristic. Overlapping elements, z-axis composition.

> **Anti-pattern:** Every page using the same centered-content-with-sidebar layout regardless of what the product does or who uses it.

### Monospace for Data

Numbers, IDs, codes, timestamps in monospace. Use `tabular-nums` for columnar alignment.

### Iconography

Use **Phosphor Icons** (`@phosphor-icons/react`). Icons clarify, not decorate—if removing loses no meaning, remove it.

### Animation

Scale animation to the design direction.

**Restrained directions** (Precision, Utility, Sophistication):
- 150ms for micro-interactions, 200-250ms for larger transitions
- Easing: `cubic-bezier(0.25, 1, 0.5, 1)`
- No spring/bouncy effects

**Expressive directions** (Maximalist, Retro-Futuristic, Boldness):
- Orchestrated page loads with staggered reveals
- Scroll-triggered animations for storytelling
- Hover states that surprise and delight
- Use `animation-delay` for choreographed sequences

> **Anti-pattern:** Adding elaborate animations to a data-dense dashboard, or using zero animation on a marketing landing page. Match motion to direction.

### Backgrounds & Atmosphere

For expressive directions, backgrounds create atmosphere:

- **Gradient meshes** — Rich, flowing color (Maximalist, Retro-Futuristic)
- **Noise textures & grain** — Tactile, organic feel (Editorial, Organic, Brutalist)
- **Geometric patterns** — Structural, rhythmic (Retro-Futuristic, Boldness)
- **Layered transparencies** — Depth without heaviness (Sophistication, Maximalist)

For restrained directions, backgrounds should be invisible — flat colors or subtle tints that establish hierarchy without drawing attention.

### Contrast Hierarchy

Four levels: foreground → secondary → muted → faint. Use all four consistently.

### Color for Meaning Only

Gray builds structure. Color only for status, action, error, success. No decorative color.

## Navigation Context

Include grounding elements:
- Navigation (sidebar or top nav)
- Location indicator (breadcrumbs, page title, active state)
- User context (who's logged in, workspace/org)

Consider same background for sidebar and main content (Linear, Supabase style) with subtle border for separation.

## Dark Mode

- **Borders over shadows** — Shadows less visible on dark backgrounds
- **Adjust semantic colors** — Desaturate status colors for dark backgrounds
- **Same hierarchy, inverted values**

## Intentionality Over Defaults

The enemy of good design is not any specific technique — it's context-unaware defaults. Every interface should feel designed for its specific product, users, and purpose.

**Signs of lazy defaults (avoid these):**
- Using the same font, color scheme, and layout across unrelated projects
- Trendy color schemes (purple gradients, etc.) applied without connection to product identity
- Rounded cards with drop shadows because that's what the template had
- Choosing colors, fonts, or layouts without considering the design direction

**The test:** Could this design belong to a completely different product and still look the same? If yes, it needs more intentionality.

> No two interfaces should look the same unless they're part of the same product. Vary themes, fonts, aesthetics. Commit to a direction and execute it with precision.

## Anti-Patterns

### The Real Enemy: Inconsistency and Laziness

- Mixing depth strategies (flat borders on some cards, heavy shadows on others)
- Spacing that doesn't follow the grid
- Typography hierarchy that changes between pages
- Color used inconsistently (decorative in one place, semantic in another)
- Asymmetric padding without visual justification
- Choosing defaults instead of making design decisions

### Context-Dependent (Not Categorically Wrong)

These techniques are appropriate in some directions and wrong in others:

| Technique | Appropriate | Inappropriate |
|-----------|------------|---------------|
| Decorative gradients | Maximalist, Retro-Futuristic | Precision, Utility |
| Bold color for atmosphere | Editorial, Organic, Maximalist | Data, Utility (reserve for meaning) |
| Large border radius (16px+) | Warmth, Organic | Precision, Brutalist |
| Elaborate animations | Maximalist, Retro-Futuristic | Precision, Data, Utility |
| Dramatic drop shadows | Sophistication (layered), Maximalist | Utility, Brutalist (flat) |
| Decorative textures/grain | Editorial, Organic, Brutalist | Precision, Data |

### Always Question

- "Did I commit to a design direction or default?"
- "Does this direction fit context and users?"
- "Is my depth strategy consistent?"
- "Are all elements on the grid?"
- "Would this design look identical for a completely different product?"
