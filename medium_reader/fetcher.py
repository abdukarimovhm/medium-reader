"""Article fetching logic for Medium articles."""

import requests
from typing import Optional


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


def fetch_article(url: str, timeout: int = 30) -> str:
    """Fetch the HTML content of a Medium article.
    
    Uses a persistent session to maintain cookies and improve success rate.
    
    Args:
        url: URL of the Medium article
        timeout: Request timeout in seconds
        
    Returns:
        str: HTML content of the article
        
    Raises:
        FetchError: If the article cannot be fetched
    """
    session = get_session()
    headers = get_headers_with_referrer(url)
    
    try:
        # First, visit the Medium homepage to establish session and cookies
        # This helps make subsequent requests look more legitimate
        try:
            session.get('https://medium.com/', headers=headers, timeout=timeout)
        except Exception:
            # If homepage visit fails, continue anyway
            pass
        
        # Now fetch the actual article
        response = session.get(
            url,
            headers=headers,
            timeout=timeout,
            allow_redirects=True
        )
        response.raise_for_status()
        return response.text
    except requests.exceptions.Timeout:
        raise FetchError(f"Request timed out while fetching {url}")
    except requests.exceptions.ConnectionError:
        raise FetchError(f"Connection error while fetching {url}")
    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code if e.response else 'unknown'
        raise FetchError(f"HTTP error {status_code} while fetching {url}")
    except requests.exceptions.RequestException as e:
        raise FetchError(f"Error fetching {url}: {str(e)}")

