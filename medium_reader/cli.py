"""CLI entry point for medium-reader."""

import argparse
import logging
import sys
import webbrowser
from urllib.parse import urlparse

from .fetcher import fetch_article, FetchError
from .generator import generate_html
from .parser import parse_article, ParseError
from .storage import ensure_storage_directory, repair_library, save_article, write_index


def validate_url(url: str) -> bool:
    """True if the URL looks like a Medium article."""
    parsed = urlparse(url)
    return parsed.scheme in ('http', 'https') and (
        parsed.netloc in ('medium.com', 'www.medium.com') or parsed.netloc.endswith('.medium.com'))


def _open(path) -> None:
    try:
        webbrowser.open(path.resolve().as_uri())
    except Exception as e:  # noqa: BLE001
        print(f"Could not open the browser ({e}). Open it yourself: {path}", file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='medium-read',
        description='Fetch Medium articles and read them locally in a clean reader view.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            'Examples:\n'
            '  medium-read https://medium.com/@author/article-title\n'
            '  medium-read --offline https://medium.com/@author/article-title\n'
            '  medium-read --library\n'
            '  medium-read --repair'
        ),
    )
    parser.add_argument('url', nargs='?', help='URL of the Medium article to fetch')
    parser.add_argument('--no-open', action='store_true', help="don't open the result in the browser")
    parser.add_argument('--offline', action='store_true',
                        help='download images next to the article so it reads without a connection')
    parser.add_argument('--proxy', action='store_true',
                        help='skip medium.com and fetch through the freedium proxies straight away')
    parser.add_argument('--library', action='store_true', help='open the library of saved articles')
    parser.add_argument('--repair', action='store_true',
                        help='re-render all saved articles with the current reader (fixes old image links); '
                             'backs up the folder first')
    parser.add_argument('-y', '--yes', action='store_true', help="don't ask before fetching non-medium.com URLs")
    parser.add_argument('--debug', action='store_true', help='show detailed request and parsing logs')
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.WARNING,
        format='%(asctime)s %(name)s %(levelname)s: %(message)s' if args.debug else '%(levelname)s: %(message)s',
        datefmt='%H:%M:%S',
    )
    if args.debug:
        for noisy in ('urllib3', 'charset_normalizer'):
            logging.getLogger(noisy).setLevel(logging.INFO)

    if args.repair:
        run_repair(open_after=not args.no_open)
        return
    if args.library and not args.url:
        index = write_index()
        print(f"Library: {index}")
        if not args.no_open:
            _open(index)
        return
    if not args.url:
        build_parser().print_usage(sys.stderr)
        print("medium-read: error: give an article URL, --library or --repair", file=sys.stderr)
        sys.exit(2)

    url = args.url.strip()
    if not validate_url(url) and not args.yes:
        # Medium also serves publications on custom domains, so only warn.
        print(f"{url} isn't a medium.com URL.", file=sys.stderr)
        if sys.stdin.isatty():
            if input("Continue anyway? [y/N] ").strip().lower() != 'y':
                sys.exit(1)

    print(f"Fetching {url}")
    try:
        result = fetch_article(url, force_proxy=args.proxy)
    except FetchError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    if result.via != 'medium':
        print(f"  member-only article, read via {result.via}")

    try:
        article = parse_article(result.html, url=url, base_url=result.final_url)
    except ParseError as e:
        print(f"Error: {e}. Try again with --debug, or --proxy.", file=sys.stderr)
        sys.exit(1)

    page = generate_html(article)
    try:
        filepath = save_article(page, url, article.title, offline=args.offline)
        write_index(filepath.parent)
    except OSError as e:
        print(f"Error saving article: {e}", file=sys.stderr)
        sys.exit(1)

    details = ' · '.join(x for x in [
        article.author, f"{article.read_time} min read" if article.read_time else None,
        f"{article.image_count} image{'s' if article.image_count != 1 else ''}",
    ] if x)
    print(f"  {article.title}")
    print(f"  {details}")
    print(f"Saved to {filepath}")

    # Warn when the result looks incomplete instead of failing silently.
    if result.partial:
        print("Warning: only the member-only preview could be fetched; the proxies were unavailable.",
              file=sys.stderr)
    elif article.word_count < 300:
        print(f"Warning: the article text is short ({article.word_count} words); "
              "the page may not have been read correctly.", file=sys.stderr)

    if not args.no_open:
        _open(filepath)


def run_repair(open_after: bool = True) -> None:
    storage_dir = ensure_storage_directory()
    print(f"Re-rendering saved articles in {storage_dir} ...")
    results = repair_library(storage_dir)
    if results['backup']:
        print(f"  backup of the old files: {results['backup']}")
    print(f"  repaired {len(results['repaired'])} article(s)")
    for old, new in results['renamed']:
        print(f"  renamed {old} -> {new}")
    for name, error in results['failed']:
        print(f"  could not repair {name}: {error}", file=sys.stderr)
    index = storage_dir / 'index.html'
    print(f"Library: {index}")
    if open_after and index.exists():
        _open(index)


if __name__ == '__main__':
    main()
