#!/usr/bin/env python3
"""
Element-level WCAG AA contrast check.

For each fixture, render it with the userscript injected, walk every
text-bearing element, read its computed `color` and the *effective*
background (walking up through transparent ancestors until we hit an
opaque one), and report any pair under WCAG AA (4.5:1 for normal text,
3:1 for ≥18px or ≥14px-bold large text).

This catches the failure mode where a button is "dark grey on dark page"
— passing the page-level check while failing on itself.

Usage:
    .venv/bin/python scripts/contrast.py [fixture-glob]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = ROOT / "fixtures"
USERSCRIPT_CANDIDATES = list(ROOT.glob("*.user.js"))


def extract_body(text: str) -> str:
    return re.sub(
        r"^// ==UserScript==.*?// ==/UserScript==\n",
        "",
        text,
        count=1,
        flags=re.S,
    )


# JS that runs in the page: walks the DOM, computes effective bg (climbing
# through transparent ancestors), measures contrast, returns failures.
PROBE = r"""
(() => {
  function parseRGB(s) {
    const m = s.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const parts = m[1].split(',').map(x => parseFloat(x.trim()));
    return { r: parts[0], g: parts[1], b: parts[2], a: parts.length === 4 ? parts[3] : 1 };
  }
  function rel(c) {
    c /= 255;
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  }
  function lum({ r, g, b }) {
    return 0.2126 * rel(r) + 0.7152 * rel(g) + 0.0722 * rel(b);
  }
  function ratio(a, b) {
    const la = lum(a), lb = lum(b);
    const [hi, lo] = la >= lb ? [la, lb] : [lb, la];
    return (hi + 0.05) / (lo + 0.05);
  }
  function effectiveBg(el) {
    while (el) {
      const cs = getComputedStyle(el);
      const bg = parseRGB(cs.backgroundColor);
      if (bg && bg.a > 0.5) return bg;
      // also check background-image — gradient backgrounds bypass us
      if (cs.backgroundImage && cs.backgroundImage !== 'none') {
        return null; // can't reason about gradients here, skip
      }
      el = el.parentElement;
    }
    return { r: 255, g: 255, b: 255, a: 1 }; // fallback to UA white
  }
  const fails = [];
  const all = document.querySelectorAll('*');
  for (const el of all) {
    // Only check elements that themselves render text
    let hasText = false;
    for (const node of el.childNodes) {
      if (node.nodeType === 3 && node.nodeValue.trim()) { hasText = true; break; }
    }
    if (!hasText) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none') continue;
    if (parseFloat(cs.opacity) < 0.5) continue;
    const fg = parseRGB(cs.color);
    const bg = effectiveBg(el);
    if (!fg || !bg) continue;
    const r = ratio(fg, bg);
    const sizePx = parseFloat(cs.fontSize);
    const weight = parseInt(cs.fontWeight, 10) || 400;
    const isLarge = sizePx >= 18 || (sizePx >= 14 && weight >= 700);
    const threshold = isLarge ? 3.0 : 4.5;
    if (r < threshold) {
      const text = (el.innerText || '').trim().slice(0, 60);
      fails.push({
        tag: el.tagName.toLowerCase(),
        cls: (el.className || '').toString().slice(0, 60),
        text,
        ratio: r.toFixed(2),
        threshold,
        size: sizePx,
        weight,
        fg: cs.color,
        bg: `rgb(${bg.r},${bg.g},${bg.b})`,
      });
    }
  }
  return fails;
})()
"""


def main() -> None:
    if not USERSCRIPT_CANDIDATES:
        sys.exit("no *.user.js found")
    src = USERSCRIPT_CANDIDATES[0].read_text()
    body = extract_body(src)
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    fixtures = (
        [Path(arg).resolve()]
        if arg
        else [f for f in sorted(FIXTURES_DIR.glob("*.html")) if not f.name.startswith("_")]
    )

    total_fail = 0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for fixture in fixtures:
            ctx = browser.new_context(viewport={"width": 1440, "height": 900})
            page = ctx.new_page()
            page.add_init_script(f"""
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
            """)
            page.goto(fixture.as_uri(), wait_until="domcontentloaded")
            page.wait_for_timeout(250)
            fails = page.evaluate(PROBE)
            ctx.close()
            if fails:
                print(f"\n{fixture.name}: {len(fails)} contrast failures")
                for f in fails:
                    print(
                        f"  {f['ratio']}:1 (need {f['threshold']:.1f}:1) "
                        f"<{f['tag']}.{f['cls']}> "
                        f"{f['size']:.0f}px/{f['weight']}  "
                        f"{f['fg']} on {f['bg']}  "
                        f"text={f['text']!r}"
                    )
                total_fail += len(fails)
            else:
                print(f"{fixture.name}: OK")
        browser.close()

    if total_fail:
        sys.exit(f"\n{total_fail} contrast failures across {len(fixtures)} fixtures")
    print(f"\nAll {len(fixtures)} fixtures pass WCAG AA.")


if __name__ == "__main__":
    main()
