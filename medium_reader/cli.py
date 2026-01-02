"""CLI entry point for medium-reader."""

import argparse
import logging
import sys
import webbrowser
from urllib.parse import urlparse

from .fetcher import fetch_article, FetchError
from .parser import parse_article, ParseError
from .generator import generate_html
from .storage import save_article


def validate_url(url: str) -> bool:
    """Validate that the URL is a Medium article URL.
    
    Args:
        url: URL to validate
        
    Returns:
        bool: True if URL appears to be a Medium URL
    """
    parsed = urlparse(url)
    medium_domains = ['medium.com', 'www.medium.com']
    return parsed.netloc in medium_domains or parsed.netloc.endswith('.medium.com')


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Fetch Medium articles and read them locally',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='Example: medium-read https://medium.com/@author/article-title'
    )
    parser.add_argument(
        'url',
        help='URL of the Medium article to fetch'
    )
    parser.add_argument(
        '--no-open',
        action='store_true',
        help='Do not open the article in browser after fetching'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging to show detailed connection and request information'
    )
    
    args = parser.parse_args()
    
    # Set up logging
    if args.debug:
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        logging.debug("Debug mode enabled")
    else:
        logging.basicConfig(
            level=logging.WARNING,
            format='%(levelname)s: %(message)s'
        )
    
    # Validate URL
    if not validate_url(args.url):
        print(f"Warning: {args.url} doesn't appear to be a Medium URL", file=sys.stderr)
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            sys.exit(1)
    
    # Fetch article
    print(f"Fetching article from {args.url}...")
    try:
        html = fetch_article(args.url, debug=args.debug)
    except FetchError as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.debug:
            logging.exception("Full error traceback:")
        sys.exit(1)
    
    # Parse article
    print("Parsing article content...")
    try:
        article = parse_article(html, args.url)
    except ParseError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Generate HTML
    print("Generating HTML file...")
    article_html = generate_html(article)
    
    # Save article
    print("Saving article...")
    try:
        filepath = save_article(article_html, args.url, article.title)
        print(f"Article saved to: {filepath}")
    except Exception as e:
        print(f"Error saving article: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Open in browser
    if not args.no_open:
        print("Opening article in browser...")
        try:
            webbrowser.open(f"file://{filepath}")
        except Exception as e:
            print(f"Warning: Could not open browser: {e}", file=sys.stderr)
            print(f"Please open manually: {filepath}")
    
    print("Done!")


if __name__ == '__main__':
    main()

