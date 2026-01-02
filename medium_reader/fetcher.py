"""Article fetching logic for Medium articles."""

import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)


# Browser-like headers to avoid bot detection
# Updated to more recent Chrome version and realistic headers
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br, zstd',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Sec-Ch-Ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    'Sec-Ch-Ua-Mobile': '?0',
    'Sec-Ch-Ua-Platform': '"macOS"',
    'Cache-Control': 'max-age=0',
    'DNT': '1',
}


# Global session for cookie persistence
_session: Optional[requests.Session] = None


def get_session() -> requests.Session:
    """Get or create a persistent session for cookie handling.
    
    Returns:
        requests.Session: Session object with persistent cookies
    """
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update(DEFAULT_HEADERS)
    return _session


def get_headers_with_referrer(url: str) -> dict:
    """Get headers with appropriate referrer for the request.
    
    Args:
        url: Target URL
        
    Returns:
        dict: Headers dictionary with referrer
    """
    headers = DEFAULT_HEADERS.copy()
    
    # Add referrer - if it's a Medium article, referrer should be medium.com
    if 'medium.com' in url:
        headers['Referer'] = 'https://medium.com/'
        headers['Sec-Fetch-Site'] = 'same-origin'
    else:
        headers['Referer'] = 'https://www.google.com/'
        headers['Sec-Fetch-Site'] = 'cross-site'
    
    return headers


class FetchError(Exception):
    """Exception raised when article fetching fails."""
    pass


def _is_member_only_article(html: str) -> bool:
    """Check if the article is a member-only article.
    
    Args:
        html: HTML content of the article
        
    Returns:
        bool: True if article appears to be member-only
    """
    import re
    from bs4 import BeautifulSoup
    
    # Check for member-only indicators in HTML
    member_indicators = [
        r'member-only',
        r'member only',
        r'isMarkedPaywallOnly',
        r'isLockedPreviewOnly',
        r'paywall',
        r'locked.*preview',
    ]
    
    html_lower = html.lower()
    for indicator in member_indicators:
        if re.search(indicator, html_lower, re.I):
            return True
    
    # Check if content seems truncated (very short postBody)
    soup = BeautifulSoup(html, 'lxml')
    post_body = soup.find('div', {'data-testid': 'postBody'})
    if post_body:
        text_length = len(post_body.get_text())
        # If postBody is very short (< 2000 chars), might be truncated
        if text_length < 2000:
            # Check if it ends with ellipsis or seems cut off
            text = post_body.get_text()
            if text.endswith('...') or '...' in text[-100:]:
                return True
            # Also check if it seems incomplete (ends mid-sentence)
            if text and not text[-1] in '.!?':
                # Might be cut off
                return True
    
    # If no postBody found at all, might be member-only
    if not post_body:
        # Check if there's very little content overall
        body = soup.find('body')
        if body:
            body_text = body.get_text()
            # If body has less than 3000 chars of text, might be truncated
            if len(body_text) < 3000:
                # Check for member-only indicators in visible text
                if re.search(r'member.*only|paywall|locked', body_text, re.I):
                    return True
    
    return False


def fetch_article(url: str, timeout: int = 30, use_freedium: bool = False, use_freedium_mirror: bool = False, debug: bool = False) -> str:
    """Fetch the HTML content of a Medium article.
    
    Uses a persistent session to maintain cookies and improve success rate.
    For member-only articles, can use freedium.cfd proxy with fallback to freedium-mirror.cfd.
    
    Args:
        url: URL of the Medium article
        timeout: Request timeout in seconds
        use_freedium: If True, use freedium.cfd proxy (for member-only articles)
        use_freedium_mirror: If True, use freedium-mirror.cfd proxy (fallback)
        debug: If True, enable debug logging
        
    Returns:
        str: HTML content of the article
        
    Raises:
        FetchError: If the article cannot be fetched
    """
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    session = get_session()
    
    # Use freedium proxy if requested (primary or mirror)
    if use_freedium or use_freedium_mirror:
        if use_freedium_mirror:
            freedium_url = f"https://freedium-mirror.cfd/{url}"
            freedium_service = "freedium-mirror.cfd"
        else:
            freedium_url = f"https://freedium.cfd/{url}"
            freedium_service = "freedium.cfd"
        headers = get_headers_with_referrer(freedium_url)
        logger.debug(f"Using freedium proxy ({freedium_service}): {freedium_url}")
    else:
        headers = get_headers_with_referrer(url)
        freedium_url = None
        freedium_service = None
        logger.debug(f"Fetching directly from: {url}")
    
    logger.debug(f"Request headers: {headers}")
    logger.debug(f"Timeout: {timeout} seconds")
    
    try:
        # First, visit the Medium homepage to establish session and cookies
        # (only if not using freedium)
        if not use_freedium and not use_freedium_mirror:
            try:
                logger.debug("Visiting Medium homepage to establish session...")
                homepage_response = session.get('https://medium.com/', headers=headers, timeout=timeout)
                logger.debug(f"Homepage response status: {homepage_response.status_code}")
                logger.debug(f"Session cookies: {dict(session.cookies)}")
            except Exception as e:
                # If homepage visit fails, continue anyway
                logger.warning(f"Failed to visit homepage (continuing anyway): {e}")
                pass
        
        # Fetch the article (or from freedium proxy)
        target_url = freedium_url if freedium_url else url
        logger.debug(f"Fetching article from: {target_url}")
        
        response = session.get(
            target_url,
            headers=headers,
            timeout=timeout,
            allow_redirects=True
        )
        
        logger.debug(f"Response status code: {response.status_code}")
        logger.debug(f"Response headers: {dict(response.headers)}")
        logger.debug(f"Final URL after redirects: {response.url}")
        logger.debug(f"Response content length: {len(response.content)} bytes")
        
        response.raise_for_status()
        html = response.text
        
        logger.debug(f"HTML content length: {len(html)} characters")
        
        # If we didn't use freedium, check if article is member-only
        # If so, retry with freedium
        if not use_freedium and not use_freedium_mirror and _is_member_only_article(html):
            logger.info("Article appears to be member-only, retrying with freedium proxy...")
            # Retry with freedium proxy
            return fetch_article(url, timeout, use_freedium=True, debug=debug)
        
        return html
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
        # If we're using freedium.cfd and get a connection/timeout error, try the mirror
        if use_freedium and not use_freedium_mirror:
            logger.warning(f"Connection error with freedium.cfd: {e}")
            logger.info("Falling back to freedium-mirror.cfd...")
            return fetch_article(url, timeout, use_freedium=False, use_freedium_mirror=True, debug=debug)
        
        # If we already tried the mirror or it's not a freedium request, raise the error
        if isinstance(e, requests.exceptions.Timeout):
            logger.error(f"Request timed out after {timeout} seconds")
            logger.debug(f"Timeout exception: {e}", exc_info=True)
            raise FetchError(f"Request timed out while fetching {url}")
        else:
            logger.error(f"Connection error: {e}")
            logger.debug(f"Connection error details: {type(e).__name__}: {e}", exc_info=True)
            raise FetchError(f"Connection error while fetching {url}")
    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code if e.response else 'unknown'
        logger.error(f"HTTP error {status_code}")
        if e.response:
            logger.debug(f"Response headers: {dict(e.response.headers)}")
            logger.debug(f"Response content (first 500 chars): {e.response.text[:500]}")
        logger.debug(f"HTTP error details: {e}", exc_info=True)
        raise FetchError(f"HTTP error {status_code} while fetching {url}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Request exception: {e}")
        logger.debug(f"Request exception details: {type(e).__name__}: {e}", exc_info=True)
        raise FetchError(f"Error fetching {url}: {str(e)}")

