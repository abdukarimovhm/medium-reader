"""Saving articles, the library index, offline images, and repairing old saves."""

import hashlib
import html as html_lib
import logging
import os
import re
import shutil
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

INDEX_FILENAME = 'index.html'
ASSETS_DIRNAME = 'assets'


def get_storage_directory() -> Path:
    """~/.medium-reader/articles/ (override with MEDIUM_READER_DIR)."""
    override = os.environ.get('MEDIUM_READER_DIR')
    if override:
        return Path(override).expanduser()
    return Path.home() / ".medium-reader" / "articles"


def ensure_storage_directory() -> Path:
    storage_dir = get_storage_directory()
    storage_dir.mkdir(parents=True, exist_ok=True)
    return storage_dir


# ---------------------------------------------------------------------------
# Filenames
# ---------------------------------------------------------------------------

def sanitize_filename(name: str, max_length: int = 100) -> str:
    """A readable, filesystem-safe file stem: words joined by hyphens."""
    name = unicodedata.normalize('NFC', name)
    name = name.replace('’', "'").replace('‘', "'").replace('“', '').replace('”', '')
    name = re.sub(r"[^\w'.,()&+-]+", '-', name, flags=re.UNICODE)
    name = re.sub(r'-{2,}', '-', name).strip('-. ')
    if len(name) > max_length:
        name = name[:max_length].rsplit('-', 1)[0] or name[:max_length]
    return name or 'article'


def generate_filename_from_url(url: str, title: Optional[str] = None) -> str:
    if title:
        base_name = sanitize_filename(title)
    else:
        parts = [p for p in urlparse(url).path.split('/') if p]
        base_name = sanitize_filename(re.sub(r'-[0-9a-f]{8,12}$', '', parts[-1])) if parts else 'article'
    return base_name + '.html'


def get_unique_filename(storage_dir: Path, base_filename: str) -> str:
    if not (storage_dir / base_filename).exists():
        return base_filename
    stem = base_filename[:-len('.html')]
    counter = 2
    while (storage_dir / f"{stem}-{counter}.html").exists():
        counter += 1
    return f"{stem}-{counter}.html"


# ---------------------------------------------------------------------------
# Reading metadata back from saved files
# ---------------------------------------------------------------------------

_META_TAG_RE = re.compile(r'<meta\b[^>]*>', re.I)
_ATTR_RE = re.compile(r'([\w:-]+)\s*=\s*"([^"]*)"')


def read_saved_metadata(path: Path) -> Dict[str, str]:
    """The mr:* <meta> tags written by generate_html (empty for old saves)."""
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            head = f.read(64 * 1024)
    except OSError:
        return {}
    head = head.split('</head>', 1)[0]
    found = {}
    # Attribute order varies: pages re-serialized by BeautifulSoup (--offline) put content first.
    for tag in _META_TAG_RE.findall(head):
        attrs = dict(_ATTR_RE.findall(tag))
        name = attrs.get('name', '')
        if name.startswith('mr:') and 'content' in attrs:
            found[name] = html_lib.unescape(attrs['content'])
    return found


def find_saved_article(storage_dir: Path, url: str) -> Optional[Path]:
    """The file already holding this article, matched by its original URL."""
    if not url:
        return None
    key = _url_key(url)
    for path in _article_files(storage_dir):
        saved_url = read_saved_metadata(path).get('mr:url')
        if saved_url and _url_key(saved_url) == key:
            return path
    return None


def _url_key(url: str) -> str:
    """Compare Medium URLs by their post id when they have one."""
    parsed = urlparse(url)
    match = re.search(r'[-/]([0-9a-f]{8,12})$', parsed.path.rstrip('/'))
    if match:
        return match.group(1)
    return (parsed.netloc.lower().removeprefix('www.') + parsed.path.rstrip('/')).lower()


def _article_files(storage_dir: Path) -> List[Path]:
    return sorted(p for p in storage_dir.glob('*.html') if p.name != INDEX_FILENAME)


# ---------------------------------------------------------------------------
# Saving
# ---------------------------------------------------------------------------

def save_article(html_content: str, url: str, title: Optional[str] = None,
                 offline: bool = False) -> Path:
    """Save an article page, replacing an earlier save of the same URL.

    With offline=True, images are downloaded next to the page so it reads
    without a network connection.
    """
    storage_dir = ensure_storage_directory()
    existing = find_saved_article(storage_dir, url)
    if existing is not None:
        filepath = existing
    else:
        filepath = storage_dir / get_unique_filename(storage_dir, generate_filename_from_url(url, title))

    if offline:
        html_content = localize_images(html_content, storage_dir, filepath.stem)

    filepath.write_text(html_content, encoding='utf-8')
    return filepath


# ---------------------------------------------------------------------------
# Offline images
# ---------------------------------------------------------------------------

def _download(url: str, dest: Path, timeout: int = 30) -> bool:
    from .fetcher import get_session
    try:
        response = get_session().get(url, timeout=timeout, headers={'Accept': 'image/avif,image/webp,image/*,*/*;q=0.8'})
        response.raise_for_status()
    except Exception as e:  # noqa: BLE001 - any failure just means "keep the remote URL"
        logger.warning("Could not download %s: %s", url, e)
        return False
    dest.write_bytes(response.content)
    return True


def _extension_for(url: str) -> str:
    ext = os.path.splitext(urlparse(url).path)[1].lower()
    return ext if ext in ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.avif') else '.jpg'


def localize_images(page_html: str, storage_dir: Path, stem: str) -> str:
    """Download every remote image in a page into assets/<stem>/ and point to it."""
    soup = BeautifulSoup(page_html, 'lxml')
    images = [img for img in soup.find_all('img') if (img.get('src') or '').startswith('http')]
    if not images:
        return page_html
    assets = storage_dir / ASSETS_DIRNAME / stem
    assets.mkdir(parents=True, exist_ok=True)

    urls = []
    for img in images:
        if img['src'] not in urls:
            urls.append(img['src'])
    # Name files after their URL so a re-save never reuses a file for a different image.
    targets = {u: assets / f"{hashlib.sha1(u.encode('utf-8')).hexdigest()[:12]}{_extension_for(u)}" for u in urls}

    with ThreadPoolExecutor(max_workers=8) as pool:
        ok = dict(zip(urls, pool.map(lambda u: targets[u].exists() or _download(u, targets[u]), urls)))

    rel = f"{ASSETS_DIRNAME}/{stem}/"
    for img in images:
        url = img['src']
        if ok.get(url):
            local = rel + targets[url].name
            img['src'] = local
            img['data-full'] = local
    downloaded = sum(1 for v in ok.values() if v)
    logger.info("Saved %d of %d images to %s", downloaded, len(urls), assets)
    for meta in soup.find_all('meta', attrs={'name': 'mr:cover'}):
        cover = meta.get('content')
        if cover in targets and ok.get(cover):
            meta['content'] = rel + targets[cover].name
    return str(soup)


# ---------------------------------------------------------------------------
# Library index
# ---------------------------------------------------------------------------

def library_entries(storage_dir: Path) -> List[dict]:
    entries = []
    for path in _article_files(storage_dir):
        meta = read_saved_metadata(path)
        title = None
        cover = meta.get('mr:cover')
        try:
            head = path.read_text(encoding='utf-8', errors='replace')[:200_000]
        except OSError:
            continue
        match = re.search(r'<title>(.*?)</title>', head, re.S)
        if match:
            title = html_lib.unescape(match.group(1)).strip()
        if not cover and meta.get('mr:version'):
            img = re.search(r'<img[^>]+src="(https?://[^"]+)"', head)
            cover = html_lib.unescape(img.group(1)) if img else None
        saved = meta.get('mr:saved') or datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec='seconds')
        entries.append({
            'file': path.name,
            'title': title or path.stem.replace('-', ' '),
            'author': meta.get('mr:author'),
            'subtitle': meta.get('mr:subtitle'),
            'date': meta.get('mr:date'),
            'read_time': meta.get('mr:read-time'),
            'cover': cover,
            'saved': saved,
        })
    entries.sort(key=lambda e: e['saved'], reverse=True)
    return entries


def write_index(storage_dir: Optional[Path] = None) -> Path:
    from .generator import generate_index
    storage_dir = storage_dir or ensure_storage_directory()
    path = storage_dir / INDEX_FILENAME
    path.write_text(generate_index(library_entries(storage_dir)), encoding='utf-8')
    return path


# ---------------------------------------------------------------------------
# Repairing pages saved by older versions
# ---------------------------------------------------------------------------

_MOJIBAKE_RE = re.compile(r'[\xc2-\xf4][\x80-\xbf]+')


def fix_mojibake(text: str) -> str:
    """Undo UTF-8 text that was decoded as Latin-1 (e.g. 'Donâ\\x80\\x99t' -> "Don't")."""
    def repair(match):
        chunk = match.group(0)
        try:
            return chunk.encode('latin-1').decode('utf-8')
        except UnicodeError:
            return chunk
    return _MOJIBAKE_RE.sub(repair, text)


def _old_header(soup: BeautifulSoup) -> dict:
    """Metadata from the header written by version 1 of the generator."""
    info = {}
    h1 = soup.find('h1', class_='article-title')
    if h1:
        info['title'] = h1.get_text(' ', strip=True)
    author = soup.find(class_='article-author')
    if author:
        info['author'] = re.sub(r'^By\s+', '', author.get_text(' ', strip=True))
    date = soup.find(class_='article-date')
    if date:
        info['date'] = date.get_text(strip=True)
    cover = soup.find('img', class_='article-image')
    if cover and cover.get('src'):
        info['image'] = cover['src']
    description = soup.find(class_='article-description')
    if description:
        info['description'] = description.get_text(' ', strip=True)
    return info


def rebuild_article(page_html: str):
    """Re-create ArticleData from a saved page of any version."""
    from .parser import ArticleData, parse_article, clean_body, resolve_image_url, ParseError, estimate_read_time

    soup = BeautifulSoup(page_html, 'lxml')
    meta = {m['name']: m.get('content') for m in soup.find_all('meta', attrs={'name': re.compile(r'^mr:')})}
    body_el = soup.find(id='article-body') or soup.find(class_='article-body')
    if body_el is None:
        raise ParseError("No article body in saved file")
    body_html = body_el.decode_contents()

    if meta.get('mr:version'):
        # Already in the current format: keep the cleaned body, re-render.
        article = ArticleData()
        article.body = clean_body(body_html)
        h1 = soup.find('h1', class_='article-title')
        article.title = h1.get_text(' ', strip=True) if h1 else None
        article.url = meta.get('mr:url')
        article.author = meta.get('mr:author')
        article.publication_date = meta.get('mr:date')
        article.subtitle = meta.get('mr:subtitle')
        article.source = meta.get('mr:source')
        rt = meta.get('mr:read-time')
        article.read_time = int(rt) if rt and rt.isdigit() else estimate_read_time(article.body)
        byline_img = soup.select_one('.byline img')
        article.author_avatar = byline_img.get('src') if byline_img else None
        cover = soup.select_one('figure.cover img')
        if cover is not None:
            article.image = cover.get('src')
            cap = soup.select_one('figure.cover figcaption')
            article.image_caption = cap.decode_contents() if cap else None
        return article, meta.get('mr:saved')

    # Version 1 page: the body still holds the source page's markup.
    old = _old_header(soup)
    article = parse_article(body_html)
    title = old.get('title') or article.title or ''
    match = re.match(r'^(.*?)\s+\|\s+by\s+(.+?)(?:\s+\|\s+in\s+.+)?$', title)
    if match:
        title, by = match.group(1), match.group(2)
        article.author = article.author or by
    article.title = title or article.title
    article.author = article.author or old.get('author')
    article.publication_date = article.publication_date or old.get('date')
    if not article.image and old.get('image'):
        article.image = resolve_image_url(old['image'])
    if not article.subtitle and old.get('description'):
        article.subtitle = old['description']
    return article, None


def repair_library(storage_dir: Optional[Path] = None, backup: bool = True) -> dict:
    """Re-render every saved article with the current parser and template.

    Fixes image paths and mojibake in pages saved by older versions. The
    folder is copied to ~/.medium-reader/backup-<timestamp>/ first.
    """
    from .generator import generate_html
    storage_dir = storage_dir or get_storage_directory()
    results = {'repaired': [], 'renamed': [], 'failed': [], 'backup': None}
    if not storage_dir.exists():
        return results

    if backup:
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        backup_dir = storage_dir.parent / f'backup-{stamp}'
        shutil.copytree(storage_dir, backup_dir)
        results['backup'] = backup_dir

    for path in _article_files(storage_dir):
        try:
            original = path.read_text(encoding='utf-8', errors='replace')
            # Only version-1 pages can contain mojibake; never touch already-correct text.
            if 'name="mr:version"' not in original:
                original = fix_mojibake(original)
            article, saved = rebuild_article(original)
            saved_at = datetime.fromisoformat(saved) if saved else datetime.fromtimestamp(path.stat().st_mtime)
            page = generate_html(article, saved_at=saved_at)
            path.write_text(page, encoding='utf-8')
            os.utime(path, (saved_at.timestamp(), saved_at.timestamp()))
            results['repaired'].append(path.name)

            fixed_name = fix_mojibake(path.name)
            if fixed_name != path.name and not (storage_dir / fixed_name).exists():
                path.rename(storage_dir / fixed_name)
                results['renamed'].append((path.name, fixed_name))
        except Exception as e:  # noqa: BLE001 - report and keep going
            logger.debug("Repair failed for %s", path, exc_info=True)
            results['failed'].append((path.name, f"{type(e).__name__}: {e}"))

    write_index(storage_dir)
    return results
