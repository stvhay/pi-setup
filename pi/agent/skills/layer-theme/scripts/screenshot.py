#!/usr/bin/env python3
"""
Screenshot harness for layer-theme.

For each fixture under fixtures/, render it twice — once unstyled (light)
and once with the userscript injected (dark) — and save PNGs to
screenshots/{light,dark}/.

Pre-flight: parses the userscript with V8 and aborts if syntax is broken.
This catches stray backticks inside CSS template literals, which would
otherwise produce a screenshot identical to the unstyled baseline and
falsely reassure the caller that the rules don't match.

Usage:
    .venv/bin/python scripts/screenshot.py [fixture-glob]

    # screenshot every fixture
    python scripts/screenshot.py

    # screenshot a single fixture
    python scripts/screenshot.py fixtures/login.html

Configuration: edit PAGES below, or define a fixtures.toml with viewport
overrides. Default viewport is 1440x900 desktop + 414x896 mobile pair.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = ROOT / "fixtures"
USERSCRIPT_CANDIDATES = list(ROOT.glob("*.user.js"))
LIGHT_DIR = ROOT / "screenshots" / "light"
DARK_DIR = ROOT / "screenshots" / "dark"

DEFAULT_DESKTOP = (1440, 900)
DEFAULT_MOBILE = (414, 896)


def discover_pages(arg: str | None) -> list[tuple[Path, str, int, int]]:
    """Return list of (fixture_path, label, w, h)."""
    if arg:
        fixtures = [Path(arg).resolve()]
    else:
        fixtures = sorted(FIXTURES_DIR.glob("*.html"))
        fixtures = [f for f in fixtures if not f.name.startswith("_")]
    out = []
    for f in fixtures:
        out.append((f, f.stem, *DEFAULT_DESKTOP))
        out.append((f, f"{f.stem}-mobile", *DEFAULT_MOBILE))
    return out


def find_userscript() -> Path:
    if not USERSCRIPT_CANDIDATES:
        sys.exit("no *.user.js found in project root")
    if len(USERSCRIPT_CANDIDATES) > 1:
        sys.exit(f"multiple userscripts: {USERSCRIPT_CANDIDATES}; specify one")
    return USERSCRIPT_CANDIDATES[0]


def extract_userscript_body(text: str) -> str:
    """Strip the metadata block; return the executable IIFE / module body."""
    return re.sub(
        r"^// ==UserScript==.*?// ==/UserScript==\n",
        "",
        text,
        count=1,
        flags=re.S,
    )


# Capture-override CSS we layer on top of everything to make full_page
# screenshots actually capture full page height. Many themes use
# `html { overflow-y: hidden }` and a scrolling .main container, which
# makes Playwright's full_page mode capture only the viewport.
CAPTURE_OVERRIDE = """
html, body { overflow: visible !important; height: auto !important; }
.main, [data-app-root] { position: static !important; top: 0 !important;
                          height: auto !important; overflow: visible !important; }
"""


def syntax_check(page, source: str) -> None:
    """Validate the userscript with V8 via `new Function(src)`. Throws
    SyntaxError on bad syntax without executing the body, catching every
    failure mode (stray backticks, unmatched parens, typos, etc.)."""
    body = extract_userscript_body(source)
    result = page.evaluate(
        "(s) => { try { new Function(s); return 'OK'; } "
        "catch (e) { return 'ERR: ' + e.message; } }",
        body,
    )
    if result != "OK":
        sys.exit(f"userscript syntax check failed: {result}")
    print(f"  ✓ syntax check passed ({len(body)} chars)")


def apply_state(page, state: dict) -> None:
    """Apply one declared interactive state to the page.

    A state is a dict with one of these keys, plus an optional `name`
    used in the output filename:
      {"hover":   "<selector>"}     # hover-pseudo
      {"focus":   "<selector>"}     # focus-pseudo
      {"click":   "<selector>"}     # click (open dropdown / details / modal)
      {"viewport": {"width": N, "height": N}}
      {"media":   [{"name": "prefers-contrast", "value": "more"}, ...]}
                                    # CSS media features

    Multiple state types can combine in one entry — a hover at mobile
    viewport, for example.
    """
    if "viewport" in state:
        v = state["viewport"]
        page.set_viewport_size({"width": v["width"], "height": v["height"]})
    if "media" in state:
        page.emulate_media(features=state["media"])
    if "click" in state:
        page.click(state["click"])
    if "focus" in state:
        page.focus(state["focus"])
    if "hover" in state:
        page.hover(state["hover"])
    page.wait_for_timeout(150)


def discover_states(page) -> list[dict]:
    """Read the fixture's declared interactive states.

    Convention: a fixture may include a JSON block:

        <script id="layer-theme-states" type="application/json">
        [
          {"name": "hover-primary", "hover": ".btn-primary"},
          {"name": "focus-username", "focus": "#username"},
          {"name": "details-open",   "click": "details > summary"},
          {"name": "high-contrast",  "media": [{"name":"prefers-contrast","value":"more"}]}
        ]
        </script>

    If absent, the static screenshot is the only render.
    """
    return page.evaluate("""
        () => {
            const tag = document.getElementById('layer-theme-states');
            if (!tag) return [];
            try { return JSON.parse(tag.textContent); }
            catch (e) { return []; }
        }
    """)


def make_init_script(body: str | None) -> str:
    """Build the init script that runs at document_start: GM_addStyle
    polyfill (if dark), the userscript body (if dark), and the
    capture-override CSS so full_page screenshots capture full height."""
    if body is None:
        return f"""
            window.addEventListener('DOMContentLoaded', () => {{
                const s = document.createElement('style');
                s.textContent = {CAPTURE_OVERRIDE!r};
                document.head.appendChild(s);
            }});
        """
    return f"""
        window.GM_addStyle = function(css) {{
            const s = document.createElement('style');
            s.textContent = css;
            if (document.documentElement) {{
                (document.head || document.documentElement).appendChild(s);
            }} else {{
                document.addEventListener('readystatechange', () => {{
                    (document.head || document.documentElement).appendChild(s);
                }}, {{ once: true }});
            }}
            return s;
        }};
        {body}
        document.addEventListener('DOMContentLoaded', () => {{
            const s = document.createElement('style');
            s.textContent = {CAPTURE_OVERRIDE!r};
            document.head.appendChild(s);
        }});
    """


def render(browser, fixture: Path, label: str, w: int, h: int,
           body: str | None) -> list[Path]:
    """Render fixture in static + every declared interactive state.

    Returns the list of PNGs produced (>=1: the static base, plus one
    per declared state).
    """
    ctx = browser.new_context(viewport={"width": w, "height": h})
    page = ctx.new_page()
    page.add_init_script(make_init_script(body))
    page.goto(fixture.as_uri(), wait_until="domcontentloaded")
    page.wait_for_timeout(250)  # let MutationObservers settle

    out_dir = LIGHT_DIR if body is None else DARK_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    outs: list[Path] = []

    base = out_dir / f"{label}.png"
    page.screenshot(path=str(base), full_page=True)
    outs.append(base)

    states = discover_states(page)
    for state in states:
        sname = state.get("name") or "state"
        # Re-load the fixture cleanly between states so they don't
        # compose unintentionally (a focus state then a hover state on
        # different elements would leave the focus active).
        page = ctx.new_page()
        page.add_init_script(make_init_script(body))
        page.goto(fixture.as_uri(), wait_until="domcontentloaded")
        page.wait_for_timeout(250)
        try:
            apply_state(page, state)
        except Exception as e:
            print(f"  ! state {sname!r} on {label}: {e}")
            continue
        out = out_dir / f"{label}--{sname}.png"
        page.screenshot(path=str(out), full_page=True)
        outs.append(out)

    ctx.close()
    return outs


def main() -> None:
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    pages = discover_pages(arg)
    userscript = find_userscript()
    src = userscript.read_text()
    body = extract_userscript_body(src)

    print(f"userscript: {userscript.name}")
    print(f"fixtures:   {len({p[0] for p in pages})} files, {len(pages)} viewports")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        check_page = browser.new_page()
        syntax_check(check_page, src)
        check_page.close()

        for fixture, label, w, h in pages:
            for body_arg, kind in [(None, "light"), (body, "dark ")]:
                outs = render(browser, fixture, label, w, h, body_arg)
                for o in outs:
                    print(f"  {kind} {label:30s} -> {o.relative_to(ROOT)}")

        browser.close()


if __name__ == "__main__":
    main()
