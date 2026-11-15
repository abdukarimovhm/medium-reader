"""Styles and scripts for the reader page and the library page.

Reader preferences (theme, font, text size, line spacing, width) are kept in
localStorage under "mr-prefs" and applied before first paint by BOOT_JS, so
every saved article opens the way the reader last left it.
"""

# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------

BASE_CSS = r"""
:root {
  --bg: #fbfaf7; --fg: #262421; --muted: #6b665e; --faint: #a19b91; --rule: #e7e3dc;
  --link: #1f5f8b; --accent: #2f7d32; --mark: #fbefb3; --code-bg: #f2efe9; --card: #ffffff;
  --sel: rgba(47, 125, 50, .16); --shadow: 0 1px 2px rgba(0,0,0,.04), 0 8px 24px rgba(0,0,0,.06);
  --img-filter: none;
  --serif: Charter, "Bitstream Charter", "Iowan Old Style", "Sitka Text", Cambria, Georgia, serif;
  --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue", Roboto, sans-serif;
  --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
  --body-font: var(--serif);
  --text-size: 20px; --leading: 1.72; --measure: 680px;
  color-scheme: light;
}
:root[data-theme="sepia"] {
  --bg: #f4ecd8; --fg: #433422; --muted: #75644f; --faint: #a8977f; --rule: #e3d6bc;
  --link: #8a4f1d; --accent: #9a6b2f; --mark: #f0dc9c; --code-bg: #ebe0c8; --card: #f9f3e5;
  --sel: rgba(154, 107, 47, .2);
}
:root[data-theme="dark"] {
  --bg: #18181a; --fg: #d9d7d2; --muted: #9c9890; --faint: #6d6a64; --rule: #2d2c2a;
  --link: #9cc4e8; --accent: #6cbf6a; --mark: #574a17; --code-bg: #222224; --card: #1f1f21;
  --sel: rgba(108, 191, 106, .22); --shadow: 0 8px 24px rgba(0,0,0,.4); --img-filter: brightness(.9);
  color-scheme: dark;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme]) {
    --bg: #18181a; --fg: #d9d7d2; --muted: #9c9890; --faint: #6d6a64; --rule: #2d2c2a;
    --link: #9cc4e8; --accent: #6cbf6a; --mark: #574a17; --code-bg: #222224; --card: #1f1f21;
    --sel: rgba(108, 191, 106, .22); --shadow: 0 8px 24px rgba(0,0,0,.4); --img-filter: brightness(.9);
    color-scheme: dark;
  }
}
:root[data-font="sans"] { --body-font: var(--sans); }
:root[data-leading="tight"] { --leading: 1.55; }
:root[data-leading="loose"] { --leading: 1.9; }
:root[data-width="narrow"] { --measure: 600px; }
:root[data-width="wide"] { --measure: 780px; }

* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; scroll-padding-top: 24px; }
@media (prefers-reduced-motion: no-preference) { html { scroll-behavior: smooth; } }
body { margin: 0; background: var(--bg); color: var(--fg); font-family: var(--sans);
       -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; text-rendering: optimizeLegibility;
       transition: background-color .2s, color .2s; }
::selection { background: var(--sel); }
a { color: var(--link); }
button { font: inherit; color: inherit; }
"""

# Applied in <head> before first paint: preferences, and image-error tracking
# (attached this early so errors from images that fail before the main
# script runs are still caught).
BOOT_JS = (
    "(function(){var r=document.documentElement,p={};"
    "try{p=JSON.parse(localStorage.getItem('mr-prefs')||'{}')||{};"
    "if(!p.theme&&localStorage.getItem('mr-theme'))p.theme=localStorage.getItem('mr-theme');"
    "if(!p.size&&localStorage.getItem('mr-size'))p.size=+localStorage.getItem('mr-size');}catch(e){}"
    "if(p.theme&&p.theme!=='auto')r.setAttribute('data-theme',p.theme);"
    "if(p.font==='sans')r.setAttribute('data-font','sans');"
    "if(p.leading&&p.leading!=='normal')r.setAttribute('data-leading',p.leading);"
    "if(p.width&&p.width!=='normal')r.setAttribute('data-width',p.width);"
    "if(p.size)r.style.setProperty('--text-size',p.size+'px');"
    "document.addEventListener('error',function(e){var t=e.target;"
    "if(!t||t.tagName!=='IMG'||!t.closest)return;var f=t.closest('figure');"
    "if(!f||f.classList.contains('img-broken'))return;f.classList.add('img-broken');"
    "var a=document.createElement('a');a.className='img-fallback';a.href=t.currentSrc||t.src;a.target='_blank';"
    "a.rel='noopener';a.textContent='Image didn\\u2019t load \\u2014 open it \\u2197';t.parentNode.insertBefore(a,t);},true);"
    "})();"
)

# ---------------------------------------------------------------------------
# Reader page
# ---------------------------------------------------------------------------

ARTICLE_CSS = r"""
/* Top bar: hides while reading down, comes back when scrolling up */
.progress { position: fixed; top: 0; left: 0; height: 3px; width: 0; background: var(--accent); z-index: 40;
            transition: width .1s linear; }
.topbar { position: sticky; top: 0; z-index: 30; background: color-mix(in srgb, var(--bg) 88%, transparent);
          backdrop-filter: saturate(1.5) blur(10px); -webkit-backdrop-filter: saturate(1.5) blur(10px);
          border-bottom: 1px solid transparent; transition: transform .28s ease, border-color .2s; }
.topbar.scrolled { border-bottom-color: var(--rule); }
.topbar.away { transform: translateY(-100%); }
.topbar-inner { max-width: 1320px; margin: 0 auto; padding: 10px 16px; display: grid;
                grid-template-columns: 1fr auto 1fr; align-items: center; font-size: 14px; }
.topbar a.home { color: var(--muted); text-decoration: none; justify-self: start; padding: 4px 0; }
.topbar a.home:hover { color: var(--fg); }
.time-left { color: var(--faint); font-size: 13px; font-variant-numeric: tabular-nums; }
.aa { justify-self: end; background: none; border: 1px solid var(--rule); border-radius: 999px; color: var(--muted);
      padding: 3px 13px; cursor: pointer; font-family: var(--serif); font-size: 16px; line-height: 1.4; }
.aa:hover, .aa[aria-expanded="true"] { color: var(--fg); border-color: var(--faint); }

/* Reading settings */
.settings { position: fixed; top: 56px; right: max(16px, calc((100vw - 1320px) / 2 + 16px)); z-index: 45;
            width: min(320px, calc(100vw - 32px)); background: var(--card); color: var(--fg);
            border: 1px solid var(--rule); border-radius: 14px; box-shadow: var(--shadow); padding: 14px 16px 16px;
            font-size: 13px; }
.settings[hidden] { display: none; }
.settings .row { margin-top: 12px; }
.settings .row:first-child { margin-top: 0; }
.settings .label { font-size: 11px; font-weight: 600; letter-spacing: .08em; text-transform: uppercase;
                   color: var(--faint); margin-bottom: 6px; }
.seg { display: flex; border: 1px solid var(--rule); border-radius: 10px; overflow: hidden; }
.seg button { flex: 1; background: none; border: 0; border-left: 1px solid var(--rule); padding: 8px 4px;
              cursor: pointer; color: var(--muted); display: flex; align-items: center; justify-content: center; gap: 6px; }
.seg button:first-child { border-left: 0; }
.seg button:hover { color: var(--fg); }
.seg button[aria-pressed="true"] { background: var(--code-bg); color: var(--fg); font-weight: 600; }
.seg output { flex: 1.2; display: flex; align-items: center; justify-content: center; border-left: 1px solid var(--rule);
              font-variant-numeric: tabular-nums; color: var(--fg); }
.seg output + button { border-left: 1px solid var(--rule); }
.sw { width: 14px; height: 14px; border-radius: 50%; border: 1px solid rgba(128,128,128,.35); flex: none; }
.sw-auto { background: linear-gradient(135deg, #fbfaf7 50%, #18181a 50%); }
.sw-light { background: #fbfaf7; } .sw-sepia { background: #f4ecd8; } .sw-dark { background: #18181a; }
.seg .serif { font-family: var(--serif); font-size: 15px; } .seg .sans { font-family: var(--sans); font-size: 14px; }
.settings .reset { margin-top: 12px; background: none; border: 0; color: var(--faint); cursor: pointer; padding: 0;
                   font-size: 12px; text-decoration: underline; text-underline-offset: 2px; }

/* Page grid: contents | text | (space) */
.page { max-width: 1320px; margin: 0 auto; padding: 0 16px; display: grid;
        grid-template-columns: minmax(0, 1fr) minmax(0, var(--measure)) minmax(0, 1fr); column-gap: 72px; }
.page > * { grid-column: 2; min-width: 0; }

/* Header */
.article-header { padding: 48px 0 0; }
.article-title { font-family: var(--sans); font-size: 44px; line-height: 1.12; letter-spacing: -0.022em;
                 font-weight: 750; margin: 0 0 14px; text-wrap: balance; }
.article-subtitle { font-family: var(--sans); font-size: 21px; line-height: 1.4; color: var(--muted);
                    font-weight: 400; margin: 0 0 30px; text-wrap: pretty; }
.byline { display: flex; align-items: center; gap: 12px; font-size: 14.5px; color: var(--muted); line-height: 1.45;
          padding: 14px 0; border-top: 1px solid var(--rule); border-bottom: 1px solid var(--rule); }
.byline img { width: 42px; height: 42px; border-radius: 50%; object-fit: cover; flex: none; filter: var(--img-filter); }
.byline .who { color: var(--fg); font-weight: 600; }
.byline .original { margin-left: auto; color: var(--muted); font-size: 13.5px; white-space: nowrap; text-decoration: none;
                    border: 1px solid var(--rule); border-radius: 999px; padding: 4px 12px; }
.byline .original:hover { color: var(--fg); border-color: var(--faint); }

.cover { margin: 36px 0 0; }

/* Table of contents */
.toc { font-family: var(--sans); font-size: 13.5px; line-height: 1.4; }
.toc ol { list-style: none; margin: 0; padding: 0; }
.toc li.sub a { padding-left: 22px; font-size: 13px; }
.toc a { display: block; padding: 5px 10px; color: var(--muted); text-decoration: none; border-left: 2px solid var(--rule);
         transition: color .15s, border-color .15s; }
.toc a:hover { color: var(--fg); }
.toc a.active { color: var(--fg); border-left-color: var(--accent); font-weight: 600; }
details.toc-inline { margin: 24px 0 0; border: 1px solid var(--rule); border-radius: 12px; padding: 2px 10px; }
details.toc-inline summary { cursor: pointer; padding: 10px 4px; color: var(--muted); font-size: 14px; font-weight: 600;
                             list-style: none; display: flex; justify-content: space-between; }
details.toc-inline summary::-webkit-details-marker { display: none; }
details.toc-inline summary::after { content: "+"; color: var(--faint); font-weight: 400; }
details.toc-inline[open] summary::after { content: "\2212"; }
details.toc-inline ol { padding-bottom: 10px; }
aside.toc-side { display: none; }
@media (min-width: 1260px) {
  details.toc-inline { display: none; }
  aside.toc-side { display: block; grid-column: 1; grid-row: 1 / span 20; justify-self: end; width: 200px; }
  aside.toc-side nav { position: sticky; top: 72px; max-height: calc(100vh - 100px); overflow: auto; padding-top: 52px;
                       opacity: .75; transition: opacity .2s; }
  aside.toc-side nav:hover { opacity: 1; }
  aside.toc-side .label { font-size: 11px; text-transform: uppercase; letter-spacing: .08em; color: var(--faint);
                          padding: 0 12px 10px; font-weight: 600; }
}
@media (min-width: 1260px) and (max-width: 1359px) {
  :root[data-width="wide"] details.toc-inline { display: block; }
  :root[data-width="wide"] aside.toc-side { display: none; }
}

/* Body text */
.article-body { font-family: var(--body-font); font-size: var(--text-size); line-height: var(--leading);
                padding: 36px 0 16px; overflow-wrap: break-word; font-kerning: normal;
                font-feature-settings: "kern", "liga"; hanging-punctuation: first allow-end; }
:root[data-font="sans"] .article-body { letter-spacing: -0.006em; }
.article-body p { margin: 0 0 1.3em; text-wrap: pretty; }
.article-body h2, .article-body h3, .article-body h4, .article-body h5, .article-body h6 {
  font-family: var(--sans); line-height: 1.25; letter-spacing: -0.015em; margin: 2.1em 0 .55em; text-wrap: balance;
  scroll-margin-top: 24px; }
.article-body h2 { font-size: 1.42em; font-weight: 720; }
.article-body h3 { font-size: 1.14em; font-weight: 680; }
.article-body h4, .article-body h5, .article-body h6 { font-size: 1em; font-weight: 650; }
.article-body > :first-child { margin-top: 0; }
.article-body a { color: inherit; text-decoration: underline; text-decoration-color: color-mix(in srgb, var(--fg) 30%, transparent);
                  text-underline-offset: 3px; text-decoration-thickness: 1px; transition: text-decoration-color .15s; }
.article-body a:hover { text-decoration-color: var(--accent); }
.article-body strong, .article-body b { font-weight: 700; }
.article-body mark { background: var(--mark); color: inherit; padding: .05em .15em; border-radius: 2px; }
.article-body ul, .article-body ol { margin: 0 0 1.3em; padding-left: 1.4em; }
.article-body li { margin: 0 0 .45em; padding-left: .25em; }
.article-body li::marker { color: var(--muted); }
.article-body li > p { margin-bottom: .45em; }
.article-body blockquote { margin: 1.6em 0; padding: .1em 0 .1em 1.2em; border-left: 3px solid var(--accent);
                           font-style: italic; color: color-mix(in srgb, var(--fg) 85%, var(--bg)); }
.article-body blockquote p:last-child { margin-bottom: 0; }
.article-body hr { border: 0; text-align: center; margin: 2.4em 0; height: auto; }
.article-body hr::before { content: "\2022\2003\2022\2003\2022"; color: var(--faint); letter-spacing: .4em; }
.article-body code { font-family: var(--mono); font-size: .82em; background: var(--code-bg); padding: .14em .38em;
                     border-radius: 5px; }
.article-body pre { font-family: var(--mono); font-size: 14.5px; line-height: 1.6; background: var(--code-bg);
                    border: 1px solid var(--rule); padding: 18px 22px; border-radius: 10px; overflow-x: auto;
                    margin: 1.6em 0; tab-size: 4; letter-spacing: 0; }
.article-body pre code { background: none; padding: 0; font-size: inherit; border-radius: 0; }
.article-body table { border-collapse: collapse; width: 100%; font-family: var(--sans); font-size: 15px;
                      margin: 1.6em 0; display: block; overflow-x: auto; }
.article-body th, .article-body td { border-bottom: 1px solid var(--rule); padding: 8px 12px; text-align: left; }
.article-body th { font-weight: 600; }
.article-body iframe { display: block; width: 100%; min-height: 360px; border: 0; border-radius: 10px; background: var(--code-bg); }
.article-body .embed-link { font-family: var(--sans); font-size: 13px; margin: 6px 0 1.6em; }

/* Figures */
figure { margin: 2.2em 0; }
figure img { display: block; max-width: 100%; height: auto; margin: 0 auto; border-radius: 6px; cursor: zoom-in;
             filter: var(--img-filter); }
figcaption { font-family: var(--sans); font-size: 14px; line-height: 1.5; color: var(--muted); text-align: center;
             margin: 12px auto 0; max-width: 90%; text-wrap: balance; }
figcaption a { color: inherit; }
@media (min-width: 1000px) {
  figure.bleed { margin-left: -56px; margin-right: -56px; }
}
figure.img-broken img { display: none; }
.img-fallback { display: block; padding: 36px 16px; text-align: center; font-family: var(--sans); font-size: 14px;
                color: var(--muted); border: 1px dashed var(--rule); border-radius: 8px; text-decoration: none; }
.img-fallback:hover { color: var(--fg); border-color: var(--faint); }

/* Footer */
.article-footer { border-top: 1px solid var(--rule); margin: 32px 0 96px; padding-top: 22px; font-size: 13.5px;
                  color: var(--faint); line-height: 1.7; }
.article-footer a { color: var(--muted); }
.end-mark { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 14px;
            font-size: 14px; color: var(--muted); }
.end-mark a { color: var(--fg); text-decoration: none; font-weight: 600; }

/* Resume reading */
.toast { position: fixed; left: 50%; bottom: 24px; transform: translate(-50%, 20px); opacity: 0; z-index: 46;
         background: var(--card); color: var(--fg); border: 1px solid var(--rule); border-radius: 999px;
         box-shadow: var(--shadow); padding: 6px 6px 6px 18px; max-width: calc(100vw - 24px); display: flex; align-items: center; gap: 10px;
         font-size: 14px; transition: opacity .25s, transform .25s; pointer-events: none; white-space: nowrap; }
.toast.show { opacity: 1; transform: translate(-50%, 0); pointer-events: auto; }
.toast button { border: 0; border-radius: 999px; padding: 6px 14px; cursor: pointer; background: var(--fg); color: var(--bg);
                font-weight: 600; font-size: 13px; }
.toast button.dismiss { background: none; color: var(--faint); padding: 6px 10px; font-weight: 400; font-size: 16px; }

/* Image viewer */
.lightbox { position: fixed; inset: 0; z-index: 50; background: rgba(10,10,10,.92); display: none;
            align-items: center; justify-content: center; padding: 24px; cursor: zoom-out; }
.lightbox.open { display: flex; }
.lightbox img { max-width: 100%; max-height: 100%; object-fit: contain; border-radius: 4px; }

@media (max-width: 720px) {
  :root { --text-size: 18px; }
  .page { column-gap: 0; }
  .article-header { padding-top: 28px; }
  .article-title { font-size: 31px; }
  .article-subtitle { font-size: 18.5px; margin-bottom: 22px; }
  .byline { flex-wrap: wrap; }
  .byline .original { margin-left: 0; }
  .article-body p { hyphens: auto; -webkit-hyphens: auto; }
  .article-body pre { margin-left: -16px; margin-right: -16px; border-radius: 0; border-left: 0; border-right: 0; }
  figure { margin-left: -16px; margin-right: -16px; }
  figure img { border-radius: 0; }
  figcaption { padding: 0 16px; }
  .settings { top: 52px; }
}
@media print {
  .topbar, .progress, .settings, .toast, .toc-inline, .toc-side, .lightbox, .embed-link, .end-mark { display: none !important; }
  :root { --bg: #fff; --fg: #000; --img-filter: none; }
  .page { display: block; max-width: none; }
  .article-body { font-size: 11.5pt; line-height: 1.55; }
  .article-body a::after { content: " (" attr(href) ")"; font-size: .8em; color: #555; }
  figure, pre, blockquote { break-inside: avoid; }
}
"""

SETTINGS_HTML = """
<div class="settings" id="settings" role="dialog" aria-label="Reading settings" hidden>
  <div class="row"><div class="label">Theme</div><div class="seg" data-pref="theme">
    <button type="button" data-value="auto"><span class="sw sw-auto"></span>Auto</button>
    <button type="button" data-value="light"><span class="sw sw-light"></span>Light</button>
    <button type="button" data-value="sepia"><span class="sw sw-sepia"></span>Sepia</button>
    <button type="button" data-value="dark"><span class="sw sw-dark"></span>Dark</button>
  </div></div>
  <div class="row"><div class="label">Font</div><div class="seg" data-pref="font">
    <button type="button" data-value="serif"><span class="serif">Serif</span></button>
    <button type="button" data-value="sans"><span class="sans">Sans</span></button>
  </div></div>
  <div class="row"><div class="label">Text size</div><div class="seg">
    <button type="button" id="smaller" aria-label="Smaller text"><span class="serif">A</span>−</button>
    <output id="size-out">20</output>
    <button type="button" id="larger" aria-label="Larger text"><span class="serif" style="font-size:18px">A</span>+</button>
  </div></div>
  <div class="row"><div class="label">Line spacing</div><div class="seg" data-pref="leading">
    <button type="button" data-value="tight">Tight</button>
    <button type="button" data-value="normal">Normal</button>
    <button type="button" data-value="loose">Loose</button>
  </div></div>
  <div class="row"><div class="label">Width</div><div class="seg" data-pref="width">
    <button type="button" data-value="narrow">Narrow</button>
    <button type="button" data-value="normal">Normal</button>
    <button type="button" data-value="wide">Wide</button>
  </div></div>
  <button type="button" class="reset" id="reset-prefs">Reset to defaults</button>
</div>
<div class="toast" id="resume" role="status"><span id="resume-text">Continue reading?</span>
  <button type="button" id="resume-go">Resume</button><button type="button" class="dismiss" id="resume-x" aria-label="Dismiss">×</button></div>
<div class="lightbox" id="lightbox" role="dialog" aria-label="Image viewer"><img alt=""></div>
"""

ARTICLE_JS = r"""
(function () {
  var root = document.documentElement;
  var DEFAULTS = { theme: 'auto', font: 'serif', size: 0, leading: 'normal', width: 'normal' };
  function load(key) { try { return localStorage.getItem(key); } catch (e) { return null; } }
  function save(key, value) { try { localStorage.setItem(key, value); } catch (e) {} }
  var prefs = {};
  try { prefs = JSON.parse(load('mr-prefs') || '{}') || {}; } catch (e) { prefs = {}; }
  if (!prefs.theme && load('mr-theme')) prefs.theme = load('mr-theme');
  if (!prefs.size && load('mr-size')) prefs.size = +load('mr-size');
  Object.keys(DEFAULTS).forEach(function (k) { if (prefs[k] === undefined || prefs[k] === null) prefs[k] = DEFAULTS[k]; });

  // ---- Reading settings -------------------------------------------------
  var panel = document.getElementById('settings');
  var aa = document.getElementById('aa');
  var sizeOut = document.getElementById('size-out');
  function setAttr(name, value, neutral) { if (!value || value === neutral) root.removeAttribute(name); else root.setAttribute(name, value); }
  function defaultSize() { return window.matchMedia('(max-width: 720px)').matches ? 18 : 20; }
  function apply() {
    setAttr('data-theme', prefs.theme, 'auto');
    setAttr('data-font', prefs.font, 'serif');
    setAttr('data-leading', prefs.leading, 'normal');
    setAttr('data-width', prefs.width, 'normal');
    if (prefs.size) root.style.setProperty('--text-size', prefs.size + 'px'); else root.style.removeProperty('--text-size');
    sizeOut.textContent = prefs.size || defaultSize();
    panel.querySelectorAll('.seg[data-pref]').forEach(function (seg) {
      seg.querySelectorAll('button').forEach(function (b) {
        b.setAttribute('aria-pressed', String(b.getAttribute('data-value') === String(prefs[seg.getAttribute('data-pref')])));
      });
    });
    measure();
  }
  function store() { save('mr-prefs', JSON.stringify(prefs)); }
  panel.querySelectorAll('.seg[data-pref]').forEach(function (seg) {
    seg.addEventListener('click', function (e) {
      var b = e.target.closest('button'); if (!b) return;
      prefs[seg.getAttribute('data-pref')] = b.getAttribute('data-value'); apply(); store();
    });
  });
  function bump(d) { prefs.size = Math.min(28, Math.max(14, (prefs.size || defaultSize()) + d)); apply(); store(); }
  document.getElementById('smaller').addEventListener('click', function () { bump(-1); });
  document.getElementById('larger').addEventListener('click', function () { bump(1); });
  document.getElementById('reset-prefs').addEventListener('click', function () {
    Object.keys(DEFAULTS).forEach(function (k) { prefs[k] = DEFAULTS[k]; }); apply(); store();
  });
  function openPanel(open) { panel.hidden = !open; aa.setAttribute('aria-expanded', String(open)); }
  aa.addEventListener('click', function (e) { e.stopPropagation(); openPanel(panel.hidden); });
  document.addEventListener('click', function (e) { if (!panel.hidden && !panel.contains(e.target)) openPanel(false); });

  // ---- Progress, time left, top bar ------------------------------------
  var bar = document.getElementById('progress');
  var topbar = document.getElementById('topbar');
  var timeLeft = document.getElementById('time-left');
  var body = document.getElementById('article-body');
  var words = (body.textContent || '').split(/\s+/).filter(Boolean).length;
  var images = body.querySelectorAll('img').length;
  var stated = parseFloat(body.getAttribute('data-read-time') || '');
  var totalMinutes = stated > 0 ? stated : (words / 265) + images * 12 / 60;
  var bodyTop = 0, bodyHeight = 1;
  function measure() {
    var rect = body.getBoundingClientRect();
    bodyTop = rect.top + window.scrollY;
    bodyHeight = Math.max(1, rect.height - window.innerHeight * 0.5);
  }
  function fraction() { return Math.min(1, Math.max(0, (window.scrollY - bodyTop + window.innerHeight * 0.25) / bodyHeight)); }
  var lastY = window.scrollY, ticking = false, dir = 0, anchor = lastY;
  function onScroll(fromUser) {
    ticking = false;
    var y = window.scrollY, f = fraction();
    bar.style.width = (f * 100).toFixed(2) + '%';
    var left = Math.ceil(totalMinutes * (1 - f));
    timeLeft.textContent = f >= 0.985 ? 'Finished' : (y < 40 ? Math.max(1, Math.ceil(totalMinutes)) + ' min read' : left + ' min left');
    topbar.classList.toggle('scrolled', y > 8);
    // Hide after ~60px of reading downward; show again after ~30px upward.
    if (y !== lastY) {
      var d = y > lastY ? 1 : -1;
      if (d !== dir) { dir = d; anchor = lastY; }
      if (y < 160 || !panel.hidden || (dir < 0 && anchor - y > 30)) topbar.classList.remove('away');
      else if (dir > 0 && y - anchor > 60) topbar.classList.add('away');
    }
    lastY = y;
    highlight();
    // Only real scrolling moves the bookmark; opening the page at the top must not erase it.
    if (fromUser === true && !(offerPending && y < 100)) rememberPosition(f);
  }
  document.addEventListener('scroll', function () { if (!ticking) { ticking = true; requestAnimationFrame(function () { onScroll(true); }); } }, { passive: true });
  window.addEventListener('resize', function () { measure(); onScroll(); });
  window.addEventListener('load', function () { measure(); onScroll(); });

  // ---- Contents highlight ------------------------------------------------
  var tocLinks = Array.prototype.slice.call(document.querySelectorAll('aside.toc-side a'));
  var heads = tocLinks.map(function (a) { return document.getElementById(decodeURIComponent(a.getAttribute('href').slice(1))); });
  function highlight() {
    if (!tocLinks.length) return;
    var current = -1;
    for (var i = 0; i < heads.length; i++) { if (heads[i] && heads[i].getBoundingClientRect().top < 140) current = i; }
    tocLinks.forEach(function (a, i) { a.classList.toggle('active', i === current); });
  }
  document.querySelectorAll('details.toc-inline a').forEach(function (a) {
    a.addEventListener('click', function () { a.closest('details').open = false; });
  });

  // ---- Remember where the reader stopped ---------------------------------
  var posKey = 'mr-pos:' + decodeURIComponent(location.pathname);
  var offerPending = false;
  var saveTimer = null;
  function rememberPosition(f) {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(function () { save(posKey, JSON.stringify({ f: +f.toFixed(4), t: Date.now() })); }, 400);
  }
  var toast = document.getElementById('resume');
  var saved = null;
  try { saved = JSON.parse(load(posKey) || 'null'); } catch (e) {}
  if (saved && saved.f > 0.04 && saved.f < 0.97 && window.scrollY < 100) {
    document.getElementById('resume-text').textContent = 'You stopped ' + Math.round(saved.f * 100) + '% in';
    offerPending = true;
    setTimeout(function () { toast.classList.add('show'); }, 400);
    var hideTimer = setTimeout(function () { toast.classList.remove('show'); }, 12000);
    document.getElementById('resume-go').addEventListener('click', function () {
      clearTimeout(hideTimer); toast.classList.remove('show'); offerPending = false; measure();
      window.scrollTo({ top: Math.max(0, bodyTop + saved.f * bodyHeight - window.innerHeight * 0.25), behavior: 'instant' });
      onScroll(false);
    });
    document.getElementById('resume-x').addEventListener('click', function () { clearTimeout(hideTimer); toast.classList.remove('show'); offerPending = false; });
  }

  // ---- Images: let big ones breathe, zoom on click -----------------------
  function sizeFigure(img) {
    var fig = img.closest('figure'); if (!fig) return;
    var declared = parseInt(img.getAttribute('width') || '0', 10);
    if (img.naturalWidth >= 1100 && (!declared || declared >= 680)) fig.classList.add('bleed');
  }
  document.querySelectorAll('.article-body figure img, figure.cover img').forEach(function (img) {
    if (img.complete && img.naturalWidth) sizeFigure(img);
    img.addEventListener('load', function () { sizeFigure(img); measure(); });
  });
  var box = document.getElementById('lightbox');
  var boxImg = box.querySelector('img');
  function closeBox() { box.classList.remove('open'); boxImg.removeAttribute('src'); }
  document.addEventListener('click', function (e) {
    var img = e.target.closest && e.target.closest('figure img');
    if (img && !e.target.closest('a')) { boxImg.src = img.getAttribute('data-full') || img.currentSrc || img.src; boxImg.alt = img.alt; box.classList.add('open'); }
    else if (e.target.closest && e.target.closest('#lightbox')) closeBox();
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') { closeBox(); openPanel(false); }
  });

  apply();
  measure();
  onScroll();
})();
"""

# ---------------------------------------------------------------------------
# Library page
# ---------------------------------------------------------------------------

INDEX_CSS = r"""
.wrap { max-width: 1120px; margin: 0 auto; padding: 48px 16px 96px; }
.lib-head { display: flex; align-items: end; justify-content: space-between; gap: 16px; margin-bottom: 22px; flex-wrap: wrap; }
h1 { font-size: 36px; letter-spacing: -0.025em; margin: 0 0 4px; font-weight: 750; }
.count { color: var(--muted); margin: 0; font-size: 15px; }
.tools { display: flex; gap: 10px; margin-bottom: 30px; }
.tools input { flex: 1; min-width: 0; font: inherit; font-size: 15px; padding: 11px 16px; border-radius: 12px;
               border: 1px solid var(--rule); background: var(--card); color: var(--fg); outline: none; }
.tools input:focus { border-color: var(--faint); }
.theme { background: none; border: 1px solid var(--rule); border-radius: 999px; color: var(--muted); padding: 5px 14px;
         cursor: pointer; font-size: 13px; }
.theme:hover { color: var(--fg); border-color: var(--faint); }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(290px, 1fr)); gap: 24px; }
.card { position: relative; display: flex; flex-direction: column; background: var(--card); border: 1px solid var(--rule);
        border-radius: 14px; overflow: hidden; text-decoration: none; color: inherit; box-shadow: var(--shadow);
        transition: transform .15s ease, border-color .15s; }
.card:hover { transform: translateY(-3px); border-color: var(--faint); }
.thumb { aspect-ratio: 16 / 9; background: var(--code-bg) center / cover no-repeat; filter: var(--img-filter); }
.card .info { padding: 15px 18px 18px; display: flex; flex-direction: column; gap: 7px; }
.card h2 { font-size: 17px; line-height: 1.32; margin: 0; letter-spacing: -0.012em; font-weight: 680; text-wrap: balance; }
.card p { font-family: var(--serif); font-size: 15px; line-height: 1.45; color: var(--muted); margin: 0;
          display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.card .meta { font-size: 13px; color: var(--faint); }
.card .read { position: absolute; left: 0; top: 0; height: 3px; background: var(--accent); }
.card .badge { position: absolute; right: 10px; top: 10px; font-size: 11.5px; font-weight: 600; padding: 3px 9px;
               border-radius: 999px; background: color-mix(in srgb, var(--card) 88%, transparent); color: var(--fg);
               backdrop-filter: blur(6px); -webkit-backdrop-filter: blur(6px); }
.empty { color: var(--muted); }
"""

INDEX_JS = r"""
(function () {
  var root = document.documentElement, btn = document.getElementById('theme-btn');
  var themes = ['auto', 'light', 'sepia', 'dark'], labels = { auto: 'Auto', light: 'Light', sepia: 'Sepia', dark: 'Dark' };
  function load(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function save(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  var prefs = {};
  try { prefs = JSON.parse(load('mr-prefs') || '{}') || {}; } catch (e) {}
  prefs.theme = prefs.theme || load('mr-theme') || 'auto';
  function apply() {
    if (prefs.theme === 'auto') root.removeAttribute('data-theme'); else root.setAttribute('data-theme', prefs.theme);
    btn.textContent = 'Theme: ' + (labels[prefs.theme] || 'Auto');
  }
  apply();
  btn.addEventListener('click', function () {
    prefs.theme = themes[(themes.indexOf(prefs.theme) + 1) % themes.length]; apply(); save('mr-prefs', JSON.stringify(prefs));
  });

  // Reading progress saved by each article page
  document.querySelectorAll('.card').forEach(function (card) {
    var path = decodeURIComponent(new URL(card.getAttribute('href'), location.href).pathname);
    var pos = null;
    try { pos = JSON.parse(load('mr-pos:' + path) || 'null'); } catch (e) {}
    if (!pos || !(pos.f > 0.04)) return;
    var badge = document.createElement('span'); badge.className = 'badge';
    badge.textContent = pos.f >= 0.97 ? 'Read' : Math.round(pos.f * 100) + '% read';
    card.appendChild(badge);
    var bar = document.createElement('span'); bar.className = 'read'; bar.style.width = Math.round(Math.min(1, pos.f) * 100) + '%';
    card.appendChild(bar);
  });

  var input = document.getElementById('q'), cards = document.querySelectorAll('.card'), count = document.getElementById('shown');
  input.addEventListener('input', function () {
    var q = input.value.trim().toLowerCase(), n = 0;
    cards.forEach(function (c) { var hit = !q || c.getAttribute('data-search').indexOf(q) >= 0; c.style.display = hit ? '' : 'none'; if (hit) n++; });
    count.textContent = n;
  });
})();
"""
