"""HTML file generation from parsed article content."""

from typing import Optional
from bs4 import BeautifulSoup
from .parser import ArticleData


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #fff;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }}
        
        .article-header {{
            margin-bottom: 40px;
            padding-bottom: 20px;
            border-bottom: 1px solid #e0e0e0;
        }}
        
        .article-title {{
            font-size: 2.5em;
            font-weight: 700;
            margin-bottom: 15px;
            color: #000;
            line-height: 1.2;
        }}
        
        .article-meta {{
            color: #666;
            font-size: 0.95em;
            margin-bottom: 20px;
        }}
        
        .article-author {{
            font-weight: 500;
            color: #333;
        }}
        
        .article-date {{
            margin-top: 5px;
            color: #999;
        }}
        
        .article-image {{
            width: 100%;
            max-width: 100%;
            height: auto;
            margin: 30px 0;
            border-radius: 4px;
        }}
        
        .article-description {{
            font-size: 1.2em;
            color: #666;
            font-style: italic;
            margin-bottom: 30px;
            line-height: 1.5;
        }}
        
        .article-body {{
            font-size: 1.1em;
            line-height: 1.8;
        }}
        
        .article-body p {{
            margin-bottom: 20px;
        }}
        
        .article-body h1,
        .article-body h2,
        .article-body h3,
        .article-body h4 {{
            margin-top: 40px;
            margin-bottom: 20px;
            font-weight: 700;
            line-height: 1.3;
        }}
        
        .article-body h1 {{
            font-size: 2em;
        }}
        
        .article-body h2 {{
            font-size: 1.75em;
        }}
        
        .article-body h3 {{
            font-size: 1.5em;
        }}
        
        .article-body h4 {{
            font-size: 1.25em;
        }}
        
        .article-body img {{
            max-width: 100%;
            height: auto;
            margin: 30px 0;
            border-radius: 4px;
        }}
        
        .article-body a {{
            color: #007bff;
            text-decoration: none;
        }}
        
        .article-body a:hover {{
            text-decoration: underline;
        }}
        
        .article-body blockquote {{
            border-left: 4px solid #ddd;
            padding-left: 20px;
            margin: 30px 0;
            color: #666;
            font-style: italic;
        }}
        
        .article-body code {{
            background-color: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
        }}
        
        .article-body pre {{
            background-color: #f4f4f4;
            padding: 20px;
            border-radius: 4px;
            overflow-x: auto;
            margin: 30px 0;
        }}
        
        .article-body pre code {{
            background-color: transparent;
            padding: 0;
        }}
        
        .article-body ul,
        .article-body ol {{
            margin: 20px 0;
            padding-left: 40px;
        }}
        
        .article-body li {{
            margin-bottom: 10px;
        }}
        
        @media (max-width: 768px) {{
            body {{
                padding: 15px;
            }}
            
            .article-title {{
                font-size: 2em;
            }}
            
            .article-body {{
                font-size: 1em;
            }}
        }}
    </style>
</head>
<body>
    <article>
        <header class="article-header">
            <h1 class="article-title">{title}</h1>
            <div class="article-meta">
                {meta}
            </div>
            {image}
            {description}
        </header>
        <div class="article-body">
            {body}
        </div>
    </article>
</body>
</html>"""


def format_date(date_string: Optional[str]) -> str:
    """Format a date string for display.
    
    Args:
        date_string: ISO date string or None
        
    Returns:
        str: Formatted date string
    """
    if not date_string:
        return ""
    
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        return dt.strftime('%B %d, %Y')
    except (ValueError, AttributeError):
        return date_string


def clean_html_body(body: str) -> str:
    """Clean and process the article body HTML.
    
    Args:
        body: Raw HTML body content
        
    Returns:
        str: Cleaned HTML body content
    """
    if not body:
        return ""
    
    # If body is plain text, wrap it in paragraphs
    if not body.strip().startswith('<'):
        paragraphs = [p.strip() for p in body.split('\n\n') if p.strip()]
        return '\n'.join(f'<p>{p}</p>' for p in paragraphs)
    
    # Parse and clean HTML
    soup = BeautifulSoup(body, 'lxml')
    
    # Remove nested html/body tags
    for nested in soup.find_all(['html', 'body']):
        nested.unwrap()
    
    # Remove script and style tags
    for script in soup(['script', 'style']):
        script.decompose()
    
    # Ensure images have proper attributes
    for img in soup.find_all('img'):
        if not img.get('src'):
            img.decompose()
        else:
            img['loading'] = 'lazy'
    
    # Return the content - if there's a single top-level div, return it
    # Otherwise return the whole soup content
    top_level = [elem for elem in soup.children if hasattr(elem, 'name') and elem.name]
    if len(top_level) == 1 and top_level[0].name == 'div':
        return str(top_level[0])
    
    return str(soup)


def generate_html(article: ArticleData) -> str:
    """Generate a clean HTML file from parsed article data.
    
    Args:
        article: ArticleData object with parsed content
        
    Returns:
        str: Complete HTML document
    """
    # Build meta information
    meta_parts = []
    if article.author:
        meta_parts.append(f'<span class="article-author">By {article.author}</span>')
    if article.publication_date:
        formatted_date = format_date(article.publication_date)
        if formatted_date:
            meta_parts.append(f'<div class="article-date">{formatted_date}</div>')
    
    meta = '\n                '.join(meta_parts) if meta_parts else ''
    
    # Build image HTML
    image_html = ''
    if article.image:
        image_html = f'<img src="{article.image}" alt="{article.title}" class="article-image">'
    
    # Build description HTML
    description_html = ''
    if article.description:
        description_html = f'<div class="article-description">{article.description}</div>'
    
    # Clean and process body
    body_html = clean_html_body(article.body)
    
    # Fill template
    html = HTML_TEMPLATE.format(
        title=article.title or 'Article',
        meta=meta,
        image=image_html,
        description=description_html,
        body=body_html
    )
    
    return html
