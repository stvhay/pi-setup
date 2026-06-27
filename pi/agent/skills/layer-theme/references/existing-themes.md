# Existing themes — reverse-engineering reference

Before writing anything original, check whether a mature community theme
already exists for the target site. Even when you don't reuse the code, the
*design choices* — palette, weight tiers, focus styles — are useful learning
data.

## Where to look

### Userstyles.world (Stylus userstyles, the modern home)

`https://userstyles.world` — search by site domain. Output is CSS-only
(Stylus / xStyle), no JS. Filter by:
- Most installs
- Recently updated (anything older than ~2 years probably broke)

### Greasy Fork (userscripts, includes themes)

`https://greasyfork.org/en/scripts?q=<site-domain>+dark` — userscripts that
ship CSS via `GM_addStyle`. Many "dark mode" entries here. License usually
visible on the script page.

### GitHub topic search

`https://github.com/topics/userstyle` and `https://github.com/topics/dark-mode`,
plus `<site-name>-dark` repo names. Often higher-quality than userstyles.world
because they're under version control with PRs and issues.

### catppuccin / nord / gruvbox port projects

Three palette communities maintain ports across hundreds of apps:
- `https://github.com/catppuccin/catppuccin` — directory of all ports
- `https://github.com/nordtheme/nord` and individual `nord-<app>` repos
- `https://github.com/morhetz/gruvbox-contrib`

If your target is in one of these directories, *use the port as a palette
reference* even if you're delivering a different visual style.

### Stylus/Stylish marketplace mirrors (legacy)

`userstyles.org` is the old home; many themes there are abandoned. Check
the install count and last-updated date before trusting them.

## What to extract from a community theme

Don't copy verbatim — but read with these questions in mind:

1. **What palette do they use?** Often community themes converge on one of
   ~10 well-known palettes (Material Dark, Dracula, Nord, Catppuccin,
   Gruvbox, Tokyo Night, One Dark, GitHub Dark, Solarized Dark). If two
   independent themes for your target use the same palette, that's a
   strong signal.
2. **Which CSS variables do they re-map?** If three themes for the same
   site re-map the same 8 vars, those 8 vars are the public API. Save you
   30 minutes of grep.
3. **Which selectors do they hit at Tier 2?** Each one is a hardcoded
   literal in the upstream cascade — your override list bootstrap.
4. **What papercuts do they fix?** Compare to the `design-principles.md`
   checklist. If three themes all bold the column titles, the upstream
   light theme is wrong about column titles.
5. **What do they leave broken?** Look for issues filed against the theme.
   "Hover tooltip clipped" → stacking-context trap. "Status pills illegible"
   → contrast on filled bg.

## Sites with strong existing theme ecosystems

If your target is one of these, *always* check before starting:

| Target | Where |
|---|---|
| GitHub | userstyles.world / `darkreader` exception lists / GitHub's own dark themes |
| YouTube | Greasy Fork (search "youtube dark") |
| Reddit (old / new / sh) | `RES`, `Reddit Enhancement Suite`, plus userstyles |
| Twitter / X | Greasy Fork |
| Stack Overflow | Stack Apps |
| Discord (web) | BetterDiscord themes (CSS), even though we're not theming the desktop app |
| Grafana | `github.com/grafana/grafana` already ships dark; for *light*-mode polish look for community themes |
| phpMyAdmin | userstyles.world; also bundled themes in the `themes/` directory of phpmyadmin source |
| Jenkins | "dark-theme" plugin (built-in) — exemplary CSS to study |
| Jellyfin / Sonarr / Radarr / -arr stack | Active theming community on Reddit r/jellyfin, custom CSS files |
| OpenWrt LuCI | This skill's `themes/luci-dark-material.md` (first finalized) |

## Sites that resist external theming

When the user wants a theme for one of these, set expectations:

- **Tailwind utility-only sites** — no var API, every rule needs `!important`.
- **Heavily Shadow-DOM-walled apps** (some Lit-based components, web-components-heavy)
  — `:host` selectors require `::part()` or theme-attribute hooks the app must expose.
- **Apps that reload CSS on route change** (some SPAs) — your overrides
  may need a MutationObserver to re-apply.
- **Sites behind aggressive CSP** — if `<style>` injection is blocked,
  Tampermonkey's `GM_addStyle` may fail silently. Test early.

In all of these cases, also check Dark Reader's exception lists — they
cover the ones where naive CSS overrides don't work.

## Citing inspiration

If a community theme materially informed yours (palette, structural
choices), cite it in the userscript header:

```js
// @description  Dark theme for Acme. Palette inspired by acme-dracula
//               (https://userstyles.world/style/12345/acme-dracula by @user, MIT).
```

Match license. If they're MIT and your project is Apache-2.0, that's
compatible (Apache is more permissive in spirit, and MIT can be folded in
with attribution). If they're GPL, your script becomes GPL too — confirm
this is acceptable to the user before proceeding.
