// ==UserScript==
// @name         {{NAME}}
// @namespace    {{NAMESPACE}}
// @version      0.1.0
// @description  {{DESCRIPTION}}
// @author       {{AUTHOR}}
// @license      {{LICENSE}}
// @homepageURL  {{HOMEPAGE_URL}}
// @supportURL   {{SUPPORT_URL}}
// @updateURL    {{UPDATE_URL}}
// @downloadURL  {{DOWNLOAD_URL}}
// @match        http://*/path/here
// @match        https://*/path/here
// @run-at       document-start
// @grant        GM_addStyle
// ==/UserScript==

(function () {
    'use strict';

    /*
     * ============================================================
     * ARCHITECTURE — two-tier override
     *
     *   Tier 1: Override the upstream public CSS-variable API.
     *           Re-mapping these re-tones the majority of the UI.
     *
     *   Tier 2: Repaint the upstream stylesheet's HARDCODED color
     *           literals — the parts that bypass its own var system.
     *
     *   Tier 3: Honor the framework's themeable class contract
     *           (button/alert/input intents) using Tier-1 tokens.
     *
     * Edit only the :root token block below to retune the palette.
     * Everything downstream is derived.
     * ============================================================
     */

    const css = `

:root {
    /* --- Surfaces (5 elevation tiers + code) --- */
    --t-bg:        #121417;
    --t-bg-1:      #1a1d22;
    --t-bg-2:      #21252b;
    --t-bg-3:      #2d3239;
    --t-bg-4:      #393f48;
    --t-bg-code:   #0c0e11;

    /* --- Text --- */
    --t-fg:        #e6e8eb;
    --t-fg-2:      #a4a9b0;
    --t-fg-3:      #6c7178;
    --t-fg-link:   #4ad0f4;

    /* --- Borders / shadow --- */
    --t-border:    #363b43;
    --t-border-2:  #444a54;
    --t-shadow:    rgba(0, 0, 0, 0.45);

    /* --- Accent --- */
    --t-accent:     #22c1f0;
    --t-accent-2:   #4ad0f4;
    --t-accent-dim: #155a72;
    --t-on-accent:  #062330;

    /* --- Status --- */
    --t-success:   #5ec979;  --t-success-hi:#4eb869;  --t-on-success:#0a1d10;
    --t-warning:   #f1c453;  --t-warning-hi:#e8b440;  --t-on-warning:#2a1e00;
    --t-danger:    #e57373;  --t-danger-hi: #d96565;  --t-on-danger: #2a0d0d;

    /* --- Tonal (tracks accent if customized) --- */
    --t-accent-tonal-bg: color-mix(in srgb, var(--t-accent) 14%, transparent);
    --t-accent-tonal-bd: color-mix(in srgb, var(--t-accent) 35%, transparent);

    /* --- Weight tiers --- */
    --t-fw-body:   400;
    --t-fw-medium: 500;
    --t-fw-bold:   600;

    /* --- Transition --- */
    --t-trans: 150ms ease;
}

/* ============================================================
   TIER 1 — Override the upstream public-API color variables.
   List the upstream framework's --vars here, mapped to --t-*.
   ============================================================ */
:root {
    /* --upstream-bg-color: var(--t-bg); */
    /* ... fill in based on Phase 3 study ... */
}

/* ============================================================
   TIER 2 — Repaint hardcoded color literals.
   Group selectors semantically: page bg, surfaces, borders,
   text greys, table striping, code blocks.
   ============================================================ */
html, body { background-color: var(--t-bg) !important; color: var(--t-fg); }

/* ... add Tier-2 selectors based on Phase 3 study ... */

/* ============================================================
   TIER 3 — Class-taxonomy intent semantics.
   Use the slot pattern: each intent class sets --btn-bg/fg/bd.
   ============================================================ */

/* ... add Tier-3 button / alert / input rules ... */

/* ============================================================
   FOCUS RINGS, NATIVE WIDGETS, MEDIA QUERIES
   ============================================================ */
:focus-visible { outline: 2px solid var(--t-border-2); outline-offset: 2px; }
:root { color-scheme: dark; accent-color: var(--t-accent); }
::selection { background: var(--t-accent-dim); color: var(--t-fg); }
::-webkit-scrollbar { background: var(--t-bg-1); }
::-webkit-scrollbar-thumb { background: var(--t-border-2); border-radius: 6px; }

`;

    // --------------------------------------------------------------
    // Inject. GM_addStyle is provided by Tampermonkey/Greasemonkey;
    // we declared it in the header so the manager exposes it.
    // --------------------------------------------------------------
    if (typeof GM_addStyle === 'function') {
        GM_addStyle(css);
    } else {
        // Fallback for raw <script> use:
        const s = document.createElement('style');
        s.textContent = css;
        (document.head || document.documentElement).appendChild(s);
    }

    // --------------------------------------------------------------
    // Optional JS: semantic-attribute tagger.
    //
    // Use this when the framework collapses multiple action intents
    // under a single class — e.g. every button is `.btn-primary` and
    // CSS attribute selectors can't reach button text. Walk every
    // button, lift its text into data-action, then style from that.
    // Comment out if not needed.
    // --------------------------------------------------------------
    /*
    const BTN_SEL = 'button, .btn, input[type="submit"], input[type="button"]';
    function tag(btn) {
        if (btn.dataset.action) return;
        const raw = (btn.value || btn.textContent || '').trim().toLowerCase();
        if (raw) btn.dataset.action = raw.replace(/\s+/g, ' ').replace(/[…\.]+$/, '');
    }
    function tagAll(root) { (root || document).querySelectorAll(BTN_SEL).forEach(tag); }
    function start() {
        tagAll();
        new MutationObserver(muts => {
            for (const m of muts) {
                for (const n of m.addedNodes) {
                    if (n.nodeType !== 1) continue;
                    if (n.matches && n.matches(BTN_SEL)) tag(n);
                    if (n.querySelectorAll) tagAll(n);
                }
                if (m.type === 'characterData') {
                    let p = m.target.parentElement;
                    while (p && !p.matches(BTN_SEL)) p = p.parentElement;
                    if (p) { delete p.dataset.action; tag(p); }
                }
            }
        }).observe(document.documentElement,
                   { childList: true, subtree: true, characterData: true });
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', start, { once: true });
    } else {
        start();
    }
    */
})();
