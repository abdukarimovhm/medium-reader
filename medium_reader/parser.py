"""HTML parsing and content extraction for Medium articles.

Three page shapes are supported:

* medium        - medium.com itself (free articles)
* freedium      - freedium-mirror.cfd: a Svelte/Tailwind page with an
                  <article> holding a cover <figure>, a <header>, a table of
                  contents <section> and the text in div.prose
* freedium-old  - the older freedium.cfd layout: text in a div styled
                  with a Georgia font (or div.main-content)

Whatever the source, the article text goes through `clean_body`, which turns
it into plain, portable HTML: absolute image URLs, real <figure>s with
captions, no framework classes or inline styles, no UI chrome.
"""

import json
import math
import re
from typing import Optional, Dict, Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Comment, Doctype, NavigableString, Tag


class ParseError(Exception):
    """Exception raised when article parsing fails."""


class ArticleData:
    """Container for parsed article data."""

    def __init__(self):
        self.title: Optional[str] = None
        self.subtitle: Optional[str] = None
        self.author: Optional[str] = None
        self.author_avatar: Optional[str] = None
        self.publication_date: Optional[str] = None
        self.read_time: Optional[int] = None      # minutes
        self.body: Optional[str] = None           # cleaned HTML
        self.description: Optional[str] = None
        self.image: Optional[str] = None          # cover image URL
        self.image_caption: Optional[str] = None  # cover caption HTML
        self.url: Optional[str] = None            # original Medium URL
        self.source: Optional[str] = None         # which page shape we parsed

    @property
    def word_count(self) -> int:
        if not self.body:
            return 0
        return len(BeautifulSoup(self.body, 'lxml').get_text(' ').split())

    @property
    def image_count(self) -> int:
        return self.body.count('<img') if self.body else 0


# ---------------------------------------------------------------------------
# Image URLs
# ---------------------------------------------------------------------------

MEDIUM_CDN = 'https://miro.medium.com/v2/resize:fit:{width}/{image_id}'

# Medium image ids look like "1*vJX99Ni1MlN8ip2rJ-tfcQ.png" or "0*abc123".
_IMAGE_ID = r'(?P<id>[01]\*[A-Za-z0-9_\-]+(?:\.[A-Za-z0-9]+)?)'
_MEDIUM_IMAGE_PATTERNS = [
    # freedium-mirror: /img/medium/700/<id>
    re.compile(r'/img/medium/\d+/' + _IMAGE_ID),
    # miro: /v2/resize:fit:700/format:webp/<id>, /max/700/<id>, /<id>
    re.compile(r'miro\.medium\.com/(?:v2/)?(?:[a-z]+:[^/]+/|max/\d+/)*' + _IMAGE_ID),
    # cdn-images-1.medium.com/max/800/<id>
    re.compile(r'cdn-images-\d\.medium\.com/(?:max/\d+/)?' + _IMAGE_ID),
]


def medium_image_id(url: str) -> Optional[str]:
    """Return the Medium image id in an image URL or path, if any."""
    if not url:
        return None
    for pattern in _MEDIUM_IMAGE_PATTERNS:
        match = pattern.search(url)
        if match:
            return match.group('id')
    return None


def medium_image_url(image_id: str, width: int = 1400) -> str:
    """Public CDN URL for a Medium image at a given width."""
    return MEDIUM_CDN.format(width=width, image_id=image_id)


def resolve_image_url(src: Optional[str], base_url: Optional[str] = None, width: int = 1400) -> Optional[str]:
    """Turn any image reference into an absolute URL a saved page can load.

    Medium images (including freedium-mirror's relative /img/medium/... paths,
    which break when the page is opened from file://) are mapped to Medium's
    public CDN. Other relative paths are resolved against the page URL.
    """
    if not src:
        return None
    src = src.strip()
    if src.startswith('data:'):
        return src
    image_id = medium_image_id(src)
    if image_id:
        return medium_image_url(image_id, width)
    if src.startswith('//'):
        return 'https:' + src
    if src.startswith(('http://', 'https://')):
        return src
    if base_url:
        return urljoin(base_url, src)
    if not src.startswith('/'):
        return src  # already-local path such as assets/<article>/1.png
    return None


def _largest_from_srcset(srcset: str) -> Optional[str]:
    """Pick the widest candidate from a srcset attribute."""
    best, best_w = None, -1
    for candidate in srcset.split(','):
        parts = candidate.strip().split()
        if not parts:
            continue
        width = 0
        if len(parts) > 1 and parts[1].endswith('w'):
            try:
                width = int(parts[1][:-1])
            except ValueError:
                pass
        if width > best_w:
            best, best_w = parts[0], width
    return best


def _image_source(img: Tag) -> Optional[str]:
    """Best available source for an <img>, looking at its <picture> too.

    Medium's own <img> tags inside <picture> often have no src at all; the
    URLs live only in the sibling <source srcset=...> elements.
    """
    for attr in ('data-zoom-src', 'src', 'data-src'):
        if img.get(attr):
            return img[attr]
    if img.get('srcset'):
        return _largest_from_srcset(img['srcset'])
    picture = img.find_parent('picture')
    if picture:
        for source in picture.find_all('source'):
            if source.get('srcset'):
                return _largest_from_srcset(source['srcset'])
    return None


# ---------------------------------------------------------------------------
# Body cleaning
# ---------------------------------------------------------------------------

# Attributes kept on each tag; everything else (class, style, data-*, on*) goes.
_ALLOWED_ATTRS = {
    'a': {'href', 'title', 'target', 'rel'},
    'img': {'src', 'alt', 'width', 'height'},
    'iframe': {'src', 'width', 'height', 'title', 'loading', 'allowfullscreen'},
    'ol': {'start'},
    'td': {'colspan', 'rowspan'},
    'th': {'colspan', 'rowspan'},
    'code': set(),
    'pre': set(),
}
_KEEP_ID = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}

_REMOVE_TAGS = ['script', 'style', 'noscript', 'nav', 'button', 'svg', 'form', 'head', 'title',
                'input', 'select', 'textarea', 'link', 'meta', 'template']
_UNWRAP_TAGS = ['div', 'span', 'section', 'article', 'header', 'footer', 'main',
                'aside', 'html', 'body', 'font', 'center']
_HEADINGS = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']

# Bits of Medium's reading UI that end up inside the article markup.
_MEDIUM_UI_TESTIDS = {
    'storyTitle', 'authorPhoto', 'authorName', 'storyPublishDate', 'storyReadTime',
    'headerClapButton', 'headerBookmarkButton', 'headerSocialShareButton',
    'audioPlayButton', 'publicationName', 'publicationPhoto', 'footerClapButton',
}
_UI_TEXT = {
    'press enter or click to view image in full size', 'listen', 'share',
    'member-only story', 'follow', 'go to the original', '< go to the original',
}


def _remove_comments(root: Tag) -> None:
    for node in root.find_all(string=lambda s: isinstance(s, (Comment, Doctype))):
        node.extract()


def _caption_from_attribute(img: Tag) -> Optional[str]:
    """freedium-mirror stores captions as escaped HTML in data-caption."""
    caption = img.get('data-caption')
    if not caption:
        return None
    caption_soup = BeautifulSoup(caption, 'lxml')
    for svg in caption_soup.find_all('svg'):
        svg.decompose()
    body = caption_soup.body or caption_soup
    return body.decode_contents().strip() or None


def _normalize_images(root: Tag, soup: BeautifulSoup, base_url: Optional[str]) -> None:
    """Give every image an absolute src and put it in a <figure>."""
    for img in list(root.find_all('img')):
        src = resolve_image_url(_image_source(img), base_url)
        if not src:
            img.decompose()
            continue
        caption_html = _caption_from_attribute(img)
        img['src'] = src
        if img.get('alt', '').strip().lower() in ('none', 'image', 'img'):
            img['alt'] = ''

        # The element that stands for this image in the text flow.
        holder = img.find_parent('picture') or img
        figure = img.find_parent('figure')
        if figure is None:
            figure = soup.new_tag('figure')
            # A lone image inside a <p> or <a>: replace that wrapper instead.
            outer = holder
            while (outer.parent is not None and outer.parent is not root
                   and outer.parent.name in ('p', 'a', 'div', 'span')
                   and len(outer.parent.get_text(strip=True)) == 0
                   and len(outer.parent.find_all('img')) == 1):
                outer = outer.parent
            outer.replace_with(figure)
            figure.append(img.extract())
        elif holder is not img:
            holder.replace_with(img.extract())

        if caption_html and not figure.find('figcaption'):
            figcaption = soup.new_tag('figcaption')
            figcaption.append(BeautifulSoup(caption_html, 'html.parser'))
            figure.append(figcaption)

    # <picture>/<source> leftovers are no longer needed.
    for tag in root.find_all(['picture', 'source']):
        tag.unwrap() if tag.name == 'picture' else tag.decompose()


def _remove_ui(root: Tag) -> None:
    for tag in root.find_all(_REMOVE_TAGS):
        tag.decompose()
    for tag in root.find_all(attrs={'data-testid': True}):
        if tag.get('data-testid') in _MEDIUM_UI_TESTIDS and not tag.decomposed:
            tag.decompose()
    for tag in root.find_all(class_='speechify-ignore'):
        if not tag.decomposed:
            tag.decompose()
    for tag in root.find_all(['a', 'p', 'span', 'div']):
        if tag.decomposed:
            continue
        text = tag.get_text(' ', strip=True).lower()
        if text in _UI_TEXT:
            tag.decompose()
            continue
        href = tag.get('href', '') if tag.name == 'a' else ''
        if '#bypass' in href or '/m/signin' in href:
            tag.decompose()


def _strip_attributes(root: Tag) -> None:
    for tag in root.find_all(True):
        allowed = _ALLOWED_ATTRS.get(tag.name, set())
        keep_id = tag.name in _KEEP_ID
        if tag.name == 'p' and tag.get('class') in ('embed-link', ['embed-link']):
            continue
        for attr in list(tag.attrs):
            if attr in allowed or (keep_id and attr == 'id'):
                continue
            # Code language hints are useful for future highlighting.
            if tag.name in ('pre', 'code') and attr == 'class':
                langs = [c for c in tag.get('class', []) if c.startswith('language-')]
                if langs:
                    tag['class'] = langs
                    continue
            del tag[attr]


def _fix_links(root: Tag, base_url: Optional[str]) -> None:
    for a in root.find_all('a'):
        href = a.get('href')
        if not href:
            a.unwrap()
            continue
        if href.startswith('#'):
            continue
        if base_url and not href.startswith(('http://', 'https://', 'mailto:')):
            a['href'] = urljoin(base_url, href)
        a['target'] = '_blank'
        a['rel'] = 'noopener'


def _fix_iframes(root: Tag, soup: BeautifulSoup, base_url: Optional[str]) -> None:
    for iframe in root.find_all('iframe'):
        src = iframe.get('src')
        if src and base_url and not src.startswith(('http://', 'https://')):
            src = urljoin('https://medium.com/', src) if src.startswith('/media/') else urljoin(base_url, src)
        if not src or not src.startswith('http'):
            iframe.decompose()
            continue
        iframe['src'] = src
        iframe['loading'] = 'lazy'
        following = iframe.find_next_sibling()
        if following is not None and following.name == 'p' and following.get('class') in ('embed-link', ['embed-link']):
            continue
        # Embeds often refuse to load from a local file; leave a way out.
        link = soup.new_tag('a', href=src, target='_blank', rel='noopener')
        link.string = 'Open embedded content'
        note = soup.new_tag('p')
        note['class'] = 'embed-link'
        note.append(link)
        iframe.insert_after(note)


def _unwrap_layout(root: Tag) -> None:
    # Unwrap innermost first so nothing is skipped.
    for tag in reversed(root.find_all(_UNWRAP_TAGS)):
        tag.unwrap()


def _remove_empty(root: Tag) -> None:
    for tag in reversed(root.find_all(['p', 'figure', 'figcaption', 'a', 'strong', 'em', 'b', 'i', 'li', 'blockquote'])):
        if tag.decomposed:
            continue
        if tag.find(['img', 'iframe', 'br', 'hr', 'code']) is not None:
            continue
        if not tag.get_text(strip=True):
            tag.decompose()


def _normalize_headings(root: Tag) -> None:
    """Shift headings so the top level used in the body is <h2>.

    freedium renders an article's own h1/h2 as h3/h4; Medium uses h1/h2.
    The page title is the only <h1>.
    """
    levels = sorted({int(h.name[1]) for h in root.find_all(_HEADINGS)})
    if not levels:
        return
    shift = levels[0] - 2
    if shift == 0:
        return
    for h in root.find_all(_HEADINGS):
        h.name = f'h{min(6, max(2, int(h.name[1]) - shift))}'


def _newlines_to_breaks(root: Tag, soup: BeautifulSoup) -> None:
    """freedium-mirror keeps Medium's soft line breaks as '\\n' in text."""
    for block in root.find_all(['p', 'li', 'blockquote', 'figcaption']):
        if block.find_parent('pre'):
            continue
        for text in list(block.find_all(string=True)):
            if '\n' not in text or isinstance(text, Comment):
                continue
            stripped = text.strip('\n')
            if '\n' not in stripped:
                continue
            parts = stripped.split('\n')
            new_nodes = []
            for i, part in enumerate(parts):
                if i:
                    new_nodes.append(soup.new_tag('br'))
                new_nodes.append(NavigableString(part))
            for node in new_nodes:
                text.insert_before(node)
            text.extract()


def _assign_heading_ids(root: Tag) -> None:
    used = set()
    for h in root.find_all(_HEADINGS):
        hid = h.get('id')
        if not hid or hid in used or re.fullmatch(r'[0-9a-f]{4}', hid):
            slug = re.sub(r'[^\w]+', '-', h.get_text(' ', strip=True).lower()).strip('-')[:60] or 'section'
            hid, n = slug, 2
            while hid in used:
                hid, n = f'{slug}-{n}', n + 1
            h['id'] = hid
        used.add(hid)


def clean_body(content, base_url: Optional[str] = None, soft_breaks: bool = False) -> str:
    """Turn a chunk of article HTML into clean, portable HTML.

    Args:
        content: HTML string or a BeautifulSoup Tag holding the article text
        base_url: URL the HTML came from, for resolving relative links
        soft_breaks: Convert '\\n' inside paragraphs into <br> (freedium-mirror)
    """
    html = str(content)
    soup = BeautifulSoup(f'<div id="mr-root">{html}</div>', 'lxml')
    root = soup.find('div', id='mr-root')

    _remove_comments(root)
    _remove_ui(root)
    _normalize_images(root, soup, base_url)
    _fix_iframes(root, soup, base_url)
    _fix_links(root, base_url)
    if soft_breaks:
        _newlines_to_breaks(root, soup)
    _strip_attributes(root)
    _unwrap_layout(root)
    _remove_empty(root)
    _normalize_headings(root)
    _assign_heading_ids(root)

    return root.decode_contents().strip()


def html_to_text(html: Optional[str]) -> str:
    if not html:
        return ''
    return BeautifulSoup(html, 'lxml').get_text(' ', strip=True)


def estimate_read_time(body_html: str) -> int:
    """Minutes to read, the way Medium counts it (265 wpm + 12s per image)."""
    soup = BeautifulSoup(body_html or '', 'lxml')
    words = len(soup.get_text(' ').split())
    images = len(soup.find_all('img'))
    seconds = words / 265 * 60 + images * 12
    return max(1, math.ceil(seconds / 60))


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

def extract_json_ld(html: str) -> list:
    """Extract JSON-LD structured data from HTML."""
    soup = BeautifulSoup(html, 'lxml')
    json_ld_data = []
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string)
        except (json.JSONDecodeError, TypeError):
            continue
        json_ld_data.extend(data if isinstance(data, list) else [data])
    return json_ld_data


def extract_article_from_json_ld(json_ld_data: list) -> Optional[Dict[str, Any]]:
    """Return the Article/BlogPosting object from JSON-LD, if any."""
    for data in json_ld_data:
        if isinstance(data, dict):
            kind = data.get('@type', '')
            kind = ' '.join(kind) if isinstance(kind, list) else str(kind)
            if 'article' in kind.lower() or 'blogposting' in kind.lower():
                return data
    return None


def _strip_site_suffix(title: str) -> str:
    title = re.sub(r'\s*[-|]\s*(Freedium|Medium)\s*$', '', title, flags=re.I)
    # "Title | by Author | in Publication | Medium"
    title = re.split(r'\s+\|\s+by\s+', title, maxsplit=1)[0]
    return title.strip()


def extract_article_from_meta_tags(html: str) -> Dict[str, Optional[str]]:
    """Article metadata from <meta> tags and <title>."""
    soup = BeautifulSoup(html, 'lxml')
    meta: Dict[str, Optional[str]] = {}

    def content(**attrs) -> Optional[str]:
        tag = soup.find('meta', attrs=attrs)
        value = tag.get('content', '').strip() if tag else ''
        return value or None

    title = content(property='og:title') or content(name='twitter:title')
    if not title and soup.title:
        title = soup.title.get_text().strip()
    if title and title.lower() not in ('medium', 'freedium'):
        meta['title'] = _strip_site_suffix(title)

    meta['author'] = content(name='author')
    author_link = soup.find('link', rel='author')
    if author_link and author_link.get('title'):
        meta['author'] = author_link['title']
    meta['description'] = content(property='og:description') or content(name='description')
    meta['image'] = content(property='og:image')
    meta['date'] = content(property='article:published_time')
    return meta


def _apply_json_ld(article: ArticleData, data: Dict[str, Any]) -> None:
    article.title = article.title or data.get('headline')
    article.description = article.description or data.get('description')
    author = data.get('author')
    if isinstance(author, list) and author:
        author = author[0]
    if isinstance(author, dict):
        article.author = article.author or author.get('name')
    elif isinstance(author, str):
        article.author = article.author or author
    article.publication_date = article.publication_date or data.get('datePublished') or data.get('dateCreated')
    image = data.get('image')
    if isinstance(image, list) and image:
        image = image[0]
    if isinstance(image, dict):
        image = image.get('url')
    if isinstance(image, str):
        article.image = article.image or image


# ---------------------------------------------------------------------------
# Source-specific extraction
# ---------------------------------------------------------------------------

def detect_source(soup: BeautifulSoup) -> str:
    article = soup.find('article')
    if article is not None and article.find('div', class_='prose') is not None:
        return 'freedium'
    if soup.find('div', {'data-testid': 'postBody'}) or soup.find(class_='pw-post-body-paragraph'):
        return 'medium'
    if soup.find('div', style=lambda s: s and 'Georgia' in s) or soup.find('div', class_='main-content'):
        return 'freedium-old'
    return 'medium'


def _extract_freedium(soup: BeautifulSoup, article: ArticleData, base_url: Optional[str]) -> Optional[str]:
    """freedium-mirror.cfd layout (also matches its pages saved by older versions)."""
    root = soup.find('article')
    if root is None:
        return None
    header = root.find('header')
    if header is not None:
        h1 = header.find('h1')
        if h1:
            article.title = h1.get_text(' ', strip=True)
        for p in header.find_all('p'):
            text = p.get_text(' ', strip=True)
            classes = ' '.join(p.get('class', []))
            if re.fullmatch(r'By\s+.+', text):
                article.author = text[3:].strip()
            elif re.fullmatch(r'\d+\s+min read', text):
                article.read_time = int(text.split()[0])
            elif 'text-xl' in classes and p.find_previous_sibling('h1') is not None:
                article.subtitle = text
            elif re.fullmatch(r'[A-Z][a-z]+ \d{1,2}, \d{4}', text):
                article.publication_date = text
        avatar = header.find('img')
        if avatar:
            article.author_avatar = resolve_image_url(_image_source(avatar), base_url, width=96)

    # Cover: a <figure> directly inside the article, before the header.
    cover = root.find('figure', recursive=False)
    if cover is not None and cover.find('img'):
        img = cover.find('img')
        article.image = resolve_image_url(_image_source(img), base_url)
        figcaption = cover.find('figcaption')
        caption_html = clean_body(figcaption.decode_contents(), base_url) if figcaption else _caption_from_attribute(img)
        article.image_caption = caption_html or None

    prose = root.find('div', class_='prose')
    if prose is None:
        return None
    return clean_body(prose, base_url, soft_breaks=True)


def _extract_freedium_old(soup: BeautifulSoup, article: ArticleData, base_url: Optional[str]) -> Optional[str]:
    """Older freedium.cfd layout: a Georgia-styled wrapper holding a header
    (cover, title, subtitle, author card) and the text in div.main-content."""
    main = soup.find('div', class_='main-content')
    wrapper = None
    if main is not None:
        wrapper = main.find_parent('div', style=lambda s: s and 'Georgia' in s)
    if wrapper is None:
        serif_divs = soup.find_all('div', style=lambda s: s and 'Georgia' in s)
        wrapper = max(serif_divs, key=lambda d: len(d.get_text()), default=None)

    if wrapper is not None:
        h1 = wrapper.find('h1')
        if h1 and (main is None or not h1.find_parent(class_='main-content')):
            article.title = h1.get_text(' ', strip=True)
            h2 = h1.find_next_sibling('h2')
            if h2:
                article.subtitle = h2.get_text(' ', strip=True)
        cover = wrapper.find('img', alt='Preview image')
        if cover is not None:
            article.image = resolve_image_url(_image_source(cover), base_url)
        avatar = wrapper.find('img', class_='rounded-full')
        if avatar is not None:
            article.author_avatar = resolve_image_url(_image_source(avatar), base_url, width=96)
            if avatar.get('alt'):
                article.author = avatar['alt'].strip()
        for span in wrapper.find_all('span'):
            text = span.get_text(' ', strip=True)
            match = re.fullmatch(r'~?(\d+)\s+min read', text)
            if match:
                article.read_time = int(match.group(1))
            match = re.match(r'([A-Z][a-z]+ \d{1,2}, \d{4})', text)
            if match:
                article.publication_date = match.group(1)

    body_el = main if main is not None and len(main.get_text()) > 500 else wrapper
    if body_el is None or len(body_el.get_text()) < 500:
        return None
    return clean_body(body_el, base_url)


def _extract_medium(soup: BeautifulSoup, article: ArticleData, base_url: Optional[str]) -> Optional[str]:
    read_time = soup.find(attrs={'data-testid': 'storyReadTime'})
    if read_time:
        match = re.search(r'(\d+)\s*min', read_time.get_text())
        if match:
            article.read_time = int(match.group(1))
    photo = soup.find(attrs={'data-testid': 'authorPhoto'})
    photo_img = photo if photo is not None and photo.name == 'img' else (photo.find('img') if photo else None)
    if photo_img is not None:
        article.author_avatar = resolve_image_url(_image_source(photo_img), base_url, width=96)
    published = soup.find(attrs={'data-testid': 'storyPublishDate'})
    if published and published.get_text(strip=True):
        # The date shown on the page; JSON-LD's datePublished can be a later re-index date.
        article.publication_date = published.get_text(strip=True)
    subtitle = soup.find(class_='pw-subtitle-paragraph')
    if subtitle:
        article.subtitle = subtitle.get_text(' ', strip=True)

    container = soup.find('div', {'data-testid': 'postBody'}) or soup.find('article')
    if container is None and soup.find(class_='pw-post-body-paragraph') is not None:
        container = soup.body  # a fragment of article paragraphs without a wrapper
    if container is None:
        return None
    container = BeautifulSoup(str(container), 'lxml').find(container.name)

    # Drop the byline block: the ancestor of the title that holds no body text.
    title = container.find(attrs={'data-testid': 'storyTitle'}) or container.find('h1', class_='pw-post-title')
    if title is not None:
        block = title
        while (block.parent is not None and block.parent is not container
               and block.parent.find(class_='pw-post-body-paragraph') is None
               and block.parent.find('figure') is None):
            block = block.parent
        block.decompose()
    for tag in container.find_all(class_='pw-subtitle-paragraph'):
        tag.decompose()

    return clean_body(container, base_url)


def parse_article(html: str, url: Optional[str] = None, base_url: Optional[str] = None) -> ArticleData:
    """Parse a Medium article from HTML.

    Args:
        html: HTML of the page
        url: Original Medium URL of the article
        base_url: URL the HTML was actually served from (a proxy, say);
                  used to resolve relative links. Defaults to `url`.

    Raises:
        ParseError: If no article text could be found
    """
    base_url = base_url or url
    soup = BeautifulSoup(html, 'lxml')
    article = ArticleData()
    article.url = url
    article.source = detect_source(soup)

    if article.source == 'freedium':
        body = _extract_freedium(soup, article, base_url)
    elif article.source == 'freedium-old':
        body = _extract_freedium_old(soup, article, base_url)
    else:
        body = _extract_medium(soup, article, base_url)

    # Metadata from JSON-LD and meta tags fills whatever is still missing.
    article_json = extract_article_from_json_ld(extract_json_ld(html))
    if article_json:
        _apply_json_ld(article, article_json)
        if not body and article_json.get('articleBody'):
            # Plain text only: no images or formatting. Last resort.
            paragraphs = [p.strip() for p in str(article_json['articleBody']).split('\n\n') if p.strip()]
            body = ''.join(f'<p>{BeautifulSoup(p, "html.parser").get_text()}</p>' for p in paragraphs)
    meta = extract_article_from_meta_tags(html)
    article.title = article.title or meta.get('title')
    article.author = article.author or meta.get('author')
    article.description = article.description or meta.get('description')
    article.publication_date = article.publication_date or meta.get('date')
    if not article.image and meta.get('image'):
        article.image = resolve_image_url(meta['image'], base_url)

    if not body or len(html_to_text(body)) < 200:
        raise ParseError("Could not extract the article text from the page")
    article.body = body

    # Don't repeat the cover image as the body's first figure.
    if article.image:
        cover_id = medium_image_id(article.image)
        first = BeautifulSoup(body, 'lxml').find('img')
        if cover_id and first is not None and medium_image_id(first.get('src', '')) == cover_id:
            article.image = None
            article.image_caption = None

    if not article.subtitle and article.description:
        description = article.description.strip()
        if description and not html_to_text(body).startswith(description[:60]):
            article.subtitle = description

    if not article.read_time:
        article.read_time = estimate_read_time(body)

    if not article.title:
        article.title = _title_from_url(url) or 'Medium Article'
    return article


def _title_from_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    from urllib.parse import urlparse
    parts = [p for p in urlparse(url).path.split('/') if p]
    if not parts:
        return None
    slug = re.sub(r'-[0-9a-f]{8,12}$', '', parts[-1])
    return slug.replace('-', ' ').strip().capitalize() or None
