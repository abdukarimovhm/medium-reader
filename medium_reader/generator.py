"""HTML generation: the reading page for one article, and the library index."""

import html
from datetime import datetime
from typing import Iterable, List, Optional

from bs4 import BeautifulSoup

from .parser import ArticleData
from .theme import (ARTICLE_CSS, ARTICLE_JS, BASE_CSS, BOOT_JS, INDEX_CSS, INDEX_JS,
                    SETTINGS_HTML)

GENERATOR_VERSION = '3'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def esc(value: Optional[str]) -> str:
    return html.escape(value or '', quote=True)


def format_date(date_string: Optional[str]) -> str:
    """Format ISO or 'November 11, 2026' / 'Nov 11, 2017' dates for display."""
    if not date_string:
        return ''
    value = date_string.strip()
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).strftime('%b %-d, %Y')
    except ValueError:
        pass
    for fmt in ('%B %d, %Y', '%b %d, %Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(value, fmt).strftime('%b %-d, %Y')
        except ValueError:
            continue
    return value


def parse_date(date_string: Optional[str]) -> Optional[datetime]:
    """Best-effort parse of the date formats we store, for sorting."""
    if not date_string:
        return None
    value = date_string.strip()
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).replace(tzinfo=None)
    except ValueError:
        pass
    for fmt in ('%B %d, %Y', '%b %d, %Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _source_label(source: Optional[str], url: Optional[str]) -> str:
    return {'medium': 'Medium', 'freedium': 'freedium-mirror.cfd', 'freedium-old': 'freedium.cfd'}.get(source or '', 'Medium')


def build_toc(body_html: str) -> List[dict]:
    """Headings for the table of contents: [{id, text, level}]."""
    soup = BeautifulSoup(body_html or '', 'lxml')
    heads = []
    for h in soup.find_all(['h2', 'h3']):
        if h.get('id') and h.get_text(strip=True):
            heads.append({'id': h['id'], 'text': h.get_text(' ', strip=True), 'level': int(h.name[1])})
    return heads


def _toc_list(heads: List[dict]) -> str:
    top = min(h['level'] for h in heads)
    items = []
    for h in heads:
        cls = ' class="sub"' if h['level'] > top else ''
        items.append(f'<li{cls}><a href="#{esc(h["id"])}">{esc(h["text"])}</a></li>')
    return '<ol>' + ''.join(items) + '</ol>'


def _prepare_body(body_html: str) -> str:
    """Final touches on the cleaned body for display."""
    soup = BeautifulSoup(body_html or '', 'lxml')
    for i, img in enumerate(soup.find_all('img')):
        if not img.get('src'):
            img.decompose()
            continue
        if not img.get('data-full'):
            img['data-full'] = img['src']
        img['loading'] = 'eager' if i < 2 else 'lazy'
        img['decoding'] = 'async'
        # Large charts and photos get a little more room than the text column.
        try:
            declared = int(img.get('width') or 0)
        except ValueError:
            declared = 0
        figure = img.find_parent('figure')
        if figure is not None and declared >= 1100:
            figure['class'] = 'bleed'
    root = soup.body or soup
    return root.decode_contents()


# ---------------------------------------------------------------------------
# Article page
# ---------------------------------------------------------------------------

def generate_html(article: ArticleData, saved_at: Optional[datetime] = None) -> str:
    """Generate the reading page for one article."""
    saved_at = saved_at or datetime.now()
    title = article.title or 'Article'
    body_html = _prepare_body(article.body or '')
    date_display = format_date(article.publication_date)
    read_time = article.read_time

    # Byline
    byline_bits = []
    if article.author_avatar:
        byline_bits.append(f'<img src="{esc(article.author_avatar)}" alt="" loading="lazy">')
    who = f'<span class="who">{esc(article.author)}</span>' if article.author else ''
    details = ' · '.join(x for x in [date_display, f'{read_time} min read' if read_time else ''] if x)
    byline_bits.append(f'<div>{who}{"<br>" if who and details else ""}{esc(details)}</div>')
    if article.url:
        byline_bits.append(f'<a class="original" href="{esc(article.url)}" target="_blank" rel="noopener">Read on Medium ↗</a>')
    byline = f'<div class="byline">{"".join(byline_bits)}</div>' if (who or details or article.url) else ''

    subtitle = f'<p class="article-subtitle">{esc(article.subtitle)}</p>' if article.subtitle else ''

    cover = ''
    if article.image:
        caption = f'<figcaption>{article.image_caption}</figcaption>' if article.image_caption else ''
        cover = (f'<figure class="cover"><img src="{esc(article.image)}" data-full="{esc(article.image)}" alt="" '
                 f'loading="eager">{caption}</figure>')

    heads = build_toc(body_html)
    toc_inline = toc_side = ''
    if len(heads) >= 3:
        toc = _toc_list(heads)
        toc_inline = f'<details class="toc toc-inline"><summary>Contents</summary>{toc}</details>'
        toc_side = f'<aside class="toc toc-side"><nav aria-label="Contents"><div class="label">Contents</div>{toc}</nav></aside>'

    footer_bits = []
    if article.url:
        footer_bits.append(f'Original: <a href="{esc(article.url)}" target="_blank" rel="noopener">{esc(article.url)}</a>')
    footer_bits.append(f'Saved {saved_at.strftime("%b %-d, %Y")} via {esc(_source_label(article.source, article.url))} with medium-reader.')

    end_note = 'You’ve reached the end.'
    meta = {
        'mr:version': GENERATOR_VERSION,
        'mr:url': article.url,
        'mr:author': article.author,
        'mr:date': article.publication_date,
        'mr:read-time': str(read_time) if read_time else None,
        'mr:cover': article.image or _first_image(body_html),
        'mr:subtitle': article.subtitle,
        'mr:source': article.source,
        'mr:saved': saved_at.isoformat(timespec='seconds'),
    }
    meta_tags = '\n'.join(f'<meta name="{k}" content="{esc(v)}">' for k, v in meta.items() if v)
    description = article.subtitle or article.description

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
{f'<meta name="description" content="{esc(description)}">' if description else ''}
{meta_tags}
<script>{BOOT_JS}</script>
<style>{BASE_CSS}{ARTICLE_CSS}</style>
</head>
<body>
<div class="progress" id="progress"></div>
<div class="topbar" id="topbar"><div class="topbar-inner">
  <a class="home" href="index.html">← Library</a>
  <span class="time-left" id="time-left"></span>
  <button class="aa" id="aa" type="button" aria-label="Reading settings" aria-expanded="false" aria-controls="settings">Aa</button>
</div></div>
{SETTINGS_HTML}
<main class="page">
  {toc_side}
  <header class="article-header">
    <h1 class="article-title">{esc(title)}</h1>
    {subtitle}
    {byline}
    {toc_inline}
  </header>
  {cover}
  <article class="article-body" id="article-body"{f' data-read-time="{read_time}"' if read_time else ''}>
{body_html}
  </article>
  <footer class="article-footer">
    <div class="end-mark"><span>{esc(end_note)}</span><a href="index.html">Back to library →</a></div>
    {'<br>'.join(footer_bits)}
  </footer>
</main>

<script>{ARTICLE_JS}</script>
</body>
</html>
"""


def _first_image(body_html: str) -> Optional[str]:
    img = BeautifulSoup(body_html or '', 'lxml').find('img')
    return img.get('src') if img is not None else None


# ---------------------------------------------------------------------------
# Library index
# ---------------------------------------------------------------------------

def generate_index(entries: Iterable[dict]) -> str:
    """Library page. Each entry: file, title, author, subtitle, date, read_time, cover, saved."""
    entries = list(entries)
    cards = []
    for e in entries:
        meta = ' · '.join(x for x in [e.get('author'), format_date(e.get('date')),
                                      f"{e['read_time']} min" if e.get('read_time') else None] if x)
        search = ' '.join(x for x in [e.get('title'), e.get('author'), e.get('subtitle')] if x).lower()
        thumb = f' style="background-image:url(&quot;{esc(e["cover"])}&quot;)"' if e.get('cover') else ''
        subtitle = f'<p>{esc(e["subtitle"])}</p>' if e.get('subtitle') else ''
        cards.append(
            f'<a class="card" href="{esc(_href(e["file"]))}" data-search="{esc(search)}">'
            f'<div class="thumb"{thumb}></div><div class="info"><h2>{esc(e.get("title"))}</h2>{subtitle}'
            f'<div class="meta">{esc(meta)}</div></div></a>')
    grid = f'<div class="grid">{"".join(cards)}</div>' if cards else '<p class="empty">No saved articles yet.</p>'
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Reading Library</title>
<script>{BOOT_JS}</script>
<style>{BASE_CSS}{INDEX_CSS}</style>
</head>
<body>
<div class="wrap">
  <div class="lib-head"><div><h1>Reading Library</h1>
  <p class="count"><span id="shown">{len(entries)}</span> of {len(entries)} saved articles</p></div>
  <button class="theme" id="theme-btn" type="button">Theme: Auto</button></div>
  <div class="tools"><input id="q" type="search" placeholder="Search titles and authors" autocomplete="off"></div>
  {grid}
</div>
<script>{INDEX_JS}</script>
</body>
</html>
"""


def _href(filename: str) -> str:
    from urllib.parse import quote
    return quote(filename)
