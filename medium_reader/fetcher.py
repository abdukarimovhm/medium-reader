"""Article fetching logic for Medium articles.

Fetch order:
  1. Medium directly. If the article is free, we are done.
  2. If it is member-only (or Medium blocks us), try each proxy in PROXIES
     in turn, moving on after any network error, bad status, or a page that
     does not look like a full article.
"""

import json
import logging
from dataclasses import dataclass
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


# Browser-like headers to avoid bot detection
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Sec-Ch-Ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    'Sec-Ch-Ua-Mobile': '?0',
    'Sec-Ch-Ua-Platform': '"macOS"',
    'DNT': '1',
}

# Proxies that serve the full text of member-only articles, tried in order.
PROXIES = [
    'https://freedium.cfd/',
    'https://freedium-mirror.cfd/',
]

# A page with less article text than this is treated as a truncated preview.
MIN_ARTICLE_CHARS = 2000


class FetchError(Exception):
    """Exception raised when article fetching fails."""


@dataclass
class FetchResult:
    """The fetched page and where it came from."""
    html: str
    final_url: str   # URL the HTML was served from; base for relative links
    via: str         # 'medium' or the proxy host
    partial: bool = False  # True if only a member-only preview could be fetched


_session: Optional[requests.Session] = None


def get_session() -> requests.Session:
    """Get or create a persistent session for cookie handling."""
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update(DEFAULT_HEADERS)
    return _session


def get_headers_with_referrer(url: str) -> dict:
    """Headers with a plausible Referer for the target URL."""
    headers = DEFAULT_HEADERS.copy()
    if 'medium.com' in url:
        headers['Referer'] = 'https://medium.com/'
        headers['Sec-Fetch-Site'] = 'same-origin'
    else:
        headers['Referer'] = 'https://www.google.com/'
        headers['Sec-Fetch-Site'] = 'cross-site'
    return headers


def decode_response(response: requests.Response) -> str:
    """Decode a response body, defaulting to UTF-8.

    `requests` falls back to ISO-8859-1 when the Content-Type header has no
    charset (freedium-mirror does this), which turns every non-ASCII character
    into mojibake (e.g. ' -> â). HTML pages are UTF-8 in practice, so use
    that unless the server named a charset explicitly.
    """
    content_type = response.headers.get('Content-Type', '').lower()
    if 'charset=' in content_type and response.encoding:
        try:
            return response.content.decode(response.encoding, errors='replace')
        except LookupError:
            pass
    return response.content.decode('utf-8', errors='replace')


def _article_text_length(soup: BeautifulSoup) -> int:
    """Rough length of the article text on a page."""
    container = (
        soup.find('div', {'data-testid': 'postBody'})
        or soup.find('div', class_='prose')
        or soup.find('div', class_='main-content')
        or soup.find('article')
    )
    if container is None:
        return 0
    return len(container.get_text(' ', strip=True))


def _is_member_only_article(html: str) -> bool:
    """True if a page from medium.com is only a member-only preview.

    Medium marks paywalled posts in their JSON-LD with
    `"isAccessibleForFree": false`. Searching the raw HTML for words like
    "paywall" does not work: those keys appear in the page data of every post.
    """
    soup = BeautifulSoup(html, 'lxml')
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string or '')
        except (json.JSONDecodeError, TypeError):
            continue
        for item in data if isinstance(data, list) else [data]:
            if isinstance(item, dict) and 'isAccessibleForFree' in item:
                value = item['isAccessibleForFree']
                if value is False or str(value).lower() == 'false':
                    return True
    # No explicit marker: treat a very short article as a truncated preview.
    return _article_text_length(soup) < MIN_ARTICLE_CHARS


def _get(url: str, timeout: int) -> requests.Response:
    session = get_session()
    logger.debug("GET %s", url)
    response = session.get(url, headers=get_headers_with_referrer(url),
                           timeout=timeout, allow_redirects=True)
    logger.debug("-> %s %s (%d bytes, Content-Type: %s)", response.status_code,
                 response.url, len(response.content), response.headers.get('Content-Type'))
    response.raise_for_status()
    return response


def _fetch_direct(url: str, timeout: int) -> Optional[FetchResult]:
    """Fetch from Medium. Returns None if blocked; partial=True if member-only."""
    try:
        response = _get(url, timeout)
    except requests.exceptions.RequestException as e:
        logger.info("Direct fetch failed (%s); trying proxies.", _describe(e))
        return None
    html = decode_response(response)
    partial = _is_member_only_article(html)
    if partial:
        logger.info("Article is member-only; trying proxies.")
    return FetchResult(html=html, final_url=response.url, via='medium', partial=partial)


def _fetch_via_proxy(proxy: str, url: str, timeout: int) -> Optional[FetchResult]:
    host = proxy.split('/')[2]
    try:
        response = _get(proxy + url, timeout)
    except requests.exceptions.RequestException as e:
        logger.info("%s failed: %s", host, _describe(e))
        return None
    html = decode_response(response)
    if _article_text_length(BeautifulSoup(html, 'lxml')) < 500:
        logger.info("%s returned a page without article text.", host)
        return None
    return FetchResult(html=html, final_url=response.url, via=host)


def _describe(e: Exception) -> str:
    if isinstance(e, requests.exceptions.HTTPError) and e.response is not None:
        return f"HTTP {e.response.status_code}"
    if isinstance(e, requests.exceptions.Timeout):
        return "timed out"
    if isinstance(e, requests.exceptions.SSLError):
        return "SSL error"
    if isinstance(e, requests.exceptions.ConnectionError):
        return "connection error"
    return f"{type(e).__name__}: {e}"


def fetch_article(url: str, timeout: int = 30, force_proxy: bool = False) -> FetchResult:
    """Fetch the HTML of a Medium article, falling back to proxies.

    Args:
        url: URL of the Medium article
        timeout: Request timeout in seconds for each attempt
        force_proxy: Skip the direct fetch and go straight to the proxies

    Raises:
        FetchError: If no source returned the article
    """
    direct = None
    if not force_proxy:
        direct = _fetch_direct(url, timeout)
        if direct and not direct.partial:
            return direct

    for proxy in PROXIES:
        result = _fetch_via_proxy(proxy, url, timeout)
        if result:
            logger.info("Fetched via %s", result.via)
            return result

    if direct:
        logger.warning("All proxies failed; saving the member-only preview from Medium.")
        return direct

    raise FetchError(
        f"Could not fetch the full article from Medium or any proxy ({', '.join(p.split('/')[2] for p in PROXIES)}). "
        "Run with --debug for details."
    )
