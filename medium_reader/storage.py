"""Storage management for saving articles locally."""

import os
import re
from pathlib import Path
from urllib.parse import urlparse


def get_storage_directory():
    """Get the storage directory for articles.
    
    Returns:
        Path: Path to the articles storage directory (~/.medium-reader/articles/)
    """
    home_dir = Path.home()
    storage_dir = home_dir / ".medium-reader" / "articles"
    return storage_dir


def ensure_storage_directory():
    """Create the storage directory if it doesn't exist.
    
    Returns:
        Path: Path to the articles storage directory
    """
    storage_dir = get_storage_directory()
    storage_dir.mkdir(parents=True, exist_ok=True)
    return storage_dir


def sanitize_filename(filename):
    """Sanitize a string to be used as a filename.
    
    Args:
        filename: String to sanitize
        
    Returns:
        str: Sanitized filename safe for filesystem
    """
    # Remove or replace invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '-', filename)
    # Remove leading/trailing spaces and dots
    filename = filename.strip(' .')
    # Replace multiple spaces/hyphens with single hyphen
    filename = re.sub(r'[\s-]+', '-', filename)
    # Limit length
    if len(filename) > 200:
        filename = filename[:200]
    return filename


def generate_filename_from_url(url, title=None):
    """Generate a filename from a URL and optional title.
    
    Args:
        url: Medium article URL
        title: Optional article title
        
    Returns:
        str: Safe filename for the article
    """
    if title:
        base_name = sanitize_filename(title)
    else:
        # Extract from URL
        parsed = urlparse(url)
        path_parts = [p for p in parsed.path.split('/') if p]
        if path_parts:
            base_name = sanitize_filename(path_parts[-1])
        else:
            base_name = "article"
    
    # Ensure .html extension
    if not base_name.endswith('.html'):
        base_name += '.html'
    
    return base_name


def get_unique_filename(storage_dir, base_filename):
    """Get a unique filename if the file already exists.
    
    Args:
        storage_dir: Directory where the file will be saved
        base_filename: Base filename
        
    Returns:
        str: Unique filename (may be the same as base_filename if it doesn't exist)
    """
    filepath = storage_dir / base_filename
    
    if not filepath.exists():
        return base_filename
    
    # If file exists, append a number
    name_without_ext = base_filename.rsplit('.html', 1)[0]
    counter = 1
    
    while True:
        new_filename = f"{name_without_ext}-{counter}.html"
        new_filepath = storage_dir / new_filename
        if not new_filepath.exists():
            return new_filename
        counter += 1


def save_article(html_content, url, title=None):
    """Save an article HTML file to the storage directory.
    
    Args:
        html_content: HTML content of the article
        url: Original article URL
        title: Optional article title
        
    Returns:
        Path: Path to the saved file
    """
    storage_dir = ensure_storage_directory()
    base_filename = generate_filename_from_url(url, title)
    filename = get_unique_filename(storage_dir, base_filename)
    filepath = storage_dir / filename
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    return filepath

