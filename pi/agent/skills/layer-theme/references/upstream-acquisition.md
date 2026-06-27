# Upstream acquisition

How to get the source, the rendered HTML, and the assets you need to theme a
site you don't own. Read once at the start of Phase 2.

## Three acquisition modes, in order of preference

### Mode A — Public source (best)

The site is open-source and the theme lives in a repo you can clone.

Examples: OpenWrt LuCI (`github.com/openwrt/luci`), Grafana
(`github.com/grafana/grafana`), phpMyAdmin, Mastodon admin, Forgejo,
Gitea, Nextcloud.

```bash
gh repo clone <owner>/<repo> /tmp/<repo>
# or shallow:
git clone --depth=1 https://github.com/<owner>/<repo> /tmp/<repo>
```

Locate the theme/CSS subtree. Common locations:
- `themes/<name>/htdocs/luci-static/<name>/css/`
- `public/build/_assets/`
- `frontend/src/styles/`
- `assets/css/`

Copy the compiled stylesheet and any logo / icon assets into your project's
`theme-vendor/`. Do **not** vendor source SCSS/LESS — vendor what the browser
actually loads, so your fixture renders the same selectors at the same
specificity as production.

Note the license. Your output's `@license` should match.

### Mode B — Live HTTP fetch

The site is reachable but the source is closed (or the CSS is built/minified
in a way that makes the source unhelpful).

```bash
# Identify the loaded stylesheets
curl -s https://example.com/some/page | \
  grep -oE '<link[^>]+rel="stylesheet"[^>]*>' | \
  grep -oE 'href="[^"]+"'

# Vendor each one
curl -s https://example.com/path/to/style.css -o theme-vendor/style.css

# Vendor a representative page as a fixture
curl -s https://example.com/some/page -o fixtures/some-page.html
# Then hand-rewrite the <link> hrefs in the fixture to relative paths
```

Run a Playwright session against the live site to capture the *resolved*
asset list (including dynamically-injected stylesheets):

```python
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    page = p.chromium.launch().new_page()
    page.goto("https://example.com/some/page")
    for s in page.evaluate("[...document.styleSheets].map(s => s.href).filter(Boolean)"):
        print(s)
```

### Mode C — Ask the user (when blocked)

Triggers:
- The site requires auth and you can't see logged-in pages.
- The site is on the user's private network (router admin, NAS, internal
  Grafana) and the agent can't reach it.
- The site is built behind aggressive anti-scraping (Cloudflare challenge,
  bot detection) and curl returns junk.
- The CSS is keyed by request and `curl` returns a different bundle than
  the browser does.

What to ask for, in priority order:

1. **A "Save Page As → Webpage, Complete" dump** of one or two
   representative pages. This gives you the exact HTML and every
   stylesheet the browser actually downloaded, all in a single folder.
2. **Failing that, devtools paste:** "open DevTools → Sources →
   right-click each .css under `(index)` → Save As, and zip them up". Plus
   the Elements panel "Edit as HTML" of the page wrapper.
3. **Failing that, screenshots only:** if the user can't extract source at
   all, take detailed light-mode screenshots and ask for the rendered
   computed styles of a few representative elements (button, header, card,
   table row, alert) via DevTools → Computed pane copy.

Phrase the ask concretely. **Bad:** "can you send me the HTML?" **Good:**

> I can't reach the site directly. Could you:
> 1. Open the page at `<URL>` in your browser
> 2. File → Save Page As → "Webpage, Complete" → save to a folder
> 3. Drop the resulting `.html` file *and* its `_files/` directory into
>    this project under `vendored-from-user/`
>
> This gives me the exact CSS the browser sees, including any auth-gated or
> dynamically-loaded styles.

If the site is large, ask for 5–8 specific page types: login, primary
overview/dashboard, a list view, a detail/edit form, a settings page, an
error/empty state, plus mobile if responsive.

## Vendor-directory hygiene

```
project/
├── theme-vendor/         # original CSS, untouched, do not edit
│   ├── cascade.css       # the main stylesheet
│   ├── custom.css        # the public theming API (if exposed)
│   ├── logo.svg
│   └── icons/
│       └── ...
├── fixtures/             # hand-built or saved HTML pages
│   ├── login.html
│   ├── _partials.js      # shared bits (header markup, etc.)
│   └── ...
└── theme-vendor.LICENSE  # copy of upstream license, with a note about origin
```

Rules:
- Don't edit `theme-vendor/`. If you patch upstream CSS in your fixture, the
  patch silently changes what production looks like.
- Track `theme-vendor/` in git. Reproducible visual diffs across machines
  require pinned upstream CSS.
- Note the upstream commit/version somewhere (`theme-vendor.VERSION` or a
  comment at the top of each vendored file).

## Identifying the framework

Before writing any CSS, identify what the site is built on. The variable API
and class taxonomy depend heavily on this:

| Hint in HTML/CSS | Likely framework |
|---|---|
| `cbi-*`, `cascade.css`, `data-page="admin-*"` | OpenWrt LuCI |
| `mat-*`, `mdc-*`, `--mdc-theme-*` | Material / Angular Material |
| `mui-*`, `MuiButton-*` | MUI (React) |
| `ant-*`, `--ant-primary-color` | Ant Design |
| `chakra-*` | Chakra UI |
| `ph-*`, `phpmyadmin` markers | phpMyAdmin |
| `grafana-app`, `panel-content` | Grafana |
| `bootstrap` markers (`btn`, `navbar`, `container-fluid`, `col-*`) | Bootstrap |
| `tailwind` (utility-class-only HTML) | Tailwind — much harder to theme externally; flag this to user |
| `--joy-*` | Joy UI |

If the framework is Tailwind utility-only, warn the user: there's often no
useful var API, and you'll be fighting `!important` on every rule. Sometimes
the right answer is a heavy preamble that re-defines the colors, sometimes
it's "this isn't a good candidate for external theming."
