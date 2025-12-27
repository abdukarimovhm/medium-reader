"""HTML/JSON parsing and content extraction from Medium articles."""

import json
import re
from typing import Optional, Dict, Any
from bs4 import BeautifulSoup


class ParseError(Exception):
    """Exception raised when article parsing fails."""
    pass


class ArticleData:
    """Container for parsed article data."""
    
    def __init__(self):
        self.title: Optional[str] = None
        self.author: Optional[str] = None
        self.publication_date: Optional[str] = None
        self.body: Optional[str] = None
        self.description: Optional[str] = None
        self.image: Optional[str] = None


def extract_json_ld(html: str) -> list:
    """Extract JSON-LD structured data from HTML.
    
    Args:
        html: HTML content
        
    Returns:
        list: List of parsed JSON-LD objects
    """
    soup = BeautifulSoup(html, 'lxml')
    json_ld_data = []
    
    scripts = soup.find_all('script', type='application/ld+json')
    for script in scripts:
        try:
            data = json.loads(script.string)
            if isinstance(data, list):
                json_ld_data.extend(data)
            else:
                json_ld_data.append(data)
        except (json.JSONDecodeError, AttributeError):
            continue
    
    return json_ld_data


def extract_article_from_json_ld(json_ld_data: list) -> Optional[Dict[str, Any]]:
    """Extract article data from JSON-LD structured data.
    
    Args:
        json_ld_data: List of JSON-LD objects
        
    Returns:
        dict: Article data if found, None otherwise
    """
    for data in json_ld_data:
        if isinstance(data, dict):
            if data.get('@type') in ['Article', 'BlogPosting']:
                return data
            if 'article' in data.get('@type', '').lower():
                return data
    return None


def extract_article_from_meta_tags(html: str) -> Dict[str, Optional[str]]:
    """Extract article metadata from meta tags.
    
    Args:
        html: HTML content
        
    Returns:
        dict: Dictionary with title, author, description, etc.
    """
    soup = BeautifulSoup(html, 'lxml')
    meta_data = {}
    
    # Extract title - try Open Graph first
    og_title = soup.find('meta', property='og:title')
    if og_title and og_title.get('content'):
        title = og_title['content'].strip()
        if title and title.lower() != 'medium':
            meta_data['title'] = title
    
    # Try Twitter card title
    if not meta_data.get('title'):
        twitter_title = soup.find('meta', {'name': 'twitter:title'})
        if twitter_title and twitter_title.get('content'):
            title = twitter_title['content'].strip()
            if title and title.lower() != 'medium':
                meta_data['title'] = title
    
    # Try h1 with article-related attributes
    if not meta_data.get('title'):
        h1_tags = soup.find_all('h1')
        for h1 in h1_tags:
            text = h1.get_text().strip()
            if (text and len(text) > 5 and text.lower() != 'medium' and
                (h1.get('data-testid') or 'postTitle' in str(h1.get('class', [])))):
                meta_data['title'] = text
                break
    
    # Fallback to title tag
    if not meta_data.get('title'):
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text().strip()
            if title and title.lower() != 'medium' and len(title) > 5:
                meta_data['title'] = title
    
    # Extract author
    author_tag = soup.find('meta', {'name': 'author'})
    if author_tag and author_tag.get('content'):
        meta_data['author'] = author_tag['content']
    
    author_link = soup.find('link', rel='author')
    if author_link and author_link.get('title'):
        meta_data['author'] = author_link['title']
    
    # Extract description
    desc_tag = soup.find('meta', property='og:description')
    if desc_tag and desc_tag.get('content'):
        meta_data['description'] = desc_tag['content']
    
    # Extract image
    img_tag = soup.find('meta', property='og:image')
    if img_tag and img_tag.get('content'):
        meta_data['image'] = img_tag['content']
    
    return meta_data


def _is_ui_element(elem) -> bool:
    """Check if an element is a UI element that should be removed.
    
    Args:
        elem: BeautifulSoup element
        
    Returns:
        bool: True if element is UI-related
    """
    if not hasattr(elem, 'get_text'):
        return False
    
    text = elem.get_text().strip().lower()
    ui_keywords = ['sign in', 'sign up', 'clap', 'bookmark', 'share', 'follow', 
                   'member-only', 'responses', 'min read']
    
    if any(keyword in text for keyword in ui_keywords):
        return True
    
    # Check href for UI links
    if elem.name == 'a':
        href = elem.get('href', '').lower()
        if any(keyword in href for keyword in ['/m/signin', 'bookmark', 'clap']):
            return True
    
    return False


def _clean_content_element(elem) -> bool:
    """Clean a content element by removing UI elements.
    
    Args:
        elem: BeautifulSoup element to clean
        
    Returns:
        bool: True if element should be kept, False if removed
    """
    if not elem:
        return False
    
    # Remove UI elements
    for ui_elem in list(elem.find_all(['script', 'style', 'nav', 'button'])):
        if ui_elem:
            ui_elem.decompose()
    
    # Clean UI links
    for link in list(elem.find_all('a')):
        if link and _is_ui_element(link):
            link.replace_with(link.get_text())
    
    # Remove empty styling divs/spans
    for empty_elem in list(elem.find_all(['div', 'span'])):
        if not empty_elem:
            continue
        try:
            text = empty_elem.get_text().strip()
            if not text and not empty_elem.find(['img', 'figure', 'pre', 'code']):
                classes = empty_elem.get('class')
                if classes:
                    class_str = ' '.join(classes) if isinstance(classes, list) else str(classes)
                    if any(ui_class in class_str.lower() for ui_class in 
                           ['button', 'icon', 'tooltip', 'menu', 'nav']):
                        empty_elem.decompose()
        except (AttributeError, TypeError):
            continue
    
    # Remove nested html/body tags
    for nested in list(elem.find_all(['html', 'body'])):
        if nested:
            nested.unwrap()
    
    return True


def extract_article_body(html: str) -> Optional[str]:
    """Extract article body content from HTML.
    
    Uses the postBody div which contains the complete article in correct order.
    
    Args:
        html: HTML content
        
    Returns:
        str: Article body HTML or None if not found
    """
    soup = BeautifulSoup(html, 'lxml')
    
    # Method 1: Extract from postBody (most reliable - preserves order)
    post_body = soup.find('div', {'data-testid': 'postBody'})
    if post_body:
        # Check if postBody contains an article tag
        article_tag = post_body.find('article')
        source = article_tag if article_tag else post_body
        
        # Create a clean copy
        source_copy = BeautifulSoup(str(source), 'lxml').find(source.name)
        if source_copy:
            _clean_content_element(source_copy)
            
            # Return if we have substantial content
            if len(source_copy.get_text()) > 500:
                return str(source_copy)
        
        # Fallback: return postBody if it has content
        if len(post_body.get_text()) > 500:
            return str(post_body)
    
    # Method 2: Extract from JSON-LD articleBody (fallback)
    json_ld_data = extract_json_ld(html)
    article_data = extract_article_from_json_ld(json_ld_data)
    if article_data and 'articleBody' in article_data:
        body = article_data['articleBody']
        if body and len(body) > 200:
            return body
    
    # Method 3: Extract from article tag (last resort)
    article = soup.find('article')
    if article and len(article.get_text()) > 500:
        article_copy = BeautifulSoup(str(article), 'lxml').find('article')
        if article_copy:
            _clean_content_element(article_copy)
            return str(article_copy)
    
    return None


def parse_article(html: str, url: Optional[str] = None) -> ArticleData:
    """Parse a Medium article from HTML.
    
    Args:
        html: HTML content of the article
        url: Optional URL of the article (used for fallback title)
        
    Returns:
        ArticleData: Parsed article data
        
    Raises:
        ParseError: If the article cannot be parsed
    """
    article = ArticleData()
    soup = BeautifulSoup(html, 'lxml')
    
    # Extract JSON-LD data first (most reliable)
    json_ld_data = extract_json_ld(html)
    article_json = extract_article_from_json_ld(json_ld_data)
    
    if article_json:
        article.title = article_json.get('headline')
        article.description = article_json.get('description')
        
        # Extract author
        if 'author' in article_json:
            author = article_json['author']
            if isinstance(author, dict):
                article.author = author.get('name')
            elif isinstance(author, list) and len(author) > 0:
                article.author = author[0].get('name') if isinstance(author[0], dict) else str(author[0])
            else:
                article.author = str(author)
        
        # Extract date
        date_published = article_json.get('datePublished') or article_json.get('dateCreated')
        if date_published:
            article.publication_date = date_published
        
        # Extract image
        if 'image' in article_json:
            image = article_json['image']
            if isinstance(image, list) and len(image) > 0:
                article.image = image[0] if isinstance(image[0], str) else image[0].get('url')
            elif isinstance(image, str):
                article.image = image
            elif isinstance(image, dict):
                article.image = image.get('url')
        
        # Extract body from JSON-LD (but prefer HTML extraction)
        article.body = article_json.get('articleBody')
    
    # Fallback to meta tags
    meta_data = extract_article_from_meta_tags(html)
    if not article.title and meta_data.get('title'):
        article.title = meta_data['title']
    if not article.author and meta_data.get('author'):
        article.author = meta_data['author']
    if not article.description and meta_data.get('description'):
        article.description = meta_data['description']
    if not article.image and meta_data.get('image'):
        article.image = meta_data['image']
    
    # Additional fallback for title - try h1 tags
    if not article.title:
        h1_tags = soup.find_all('h1')
        for h1 in h1_tags:
            text = h1.get_text().strip()
            if (text and len(text) > 5 and 
                text.lower() not in ['medium', 'home', 'about', 'sign in', 'sign up']):
                article.title = text
                break
    
    # Extract body HTML (prefer HTML over JSON-LD for better structure)
    if not article.body:
        article.body = extract_article_body(html)
    
    # Validate we have body
    if not article.body:
        raise ParseError("Could not extract article body")
    
    # Use fallback title if we couldn't extract one
    if not article.title:
        if url:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            path_parts = [p for p in parsed.path.split('/') if p]
            if path_parts:
                article.title = path_parts[-1].replace('-', ' ').title()
            else:
                article.title = "Medium Article"
        else:
            article.title = "Medium Article"
    
    return article
