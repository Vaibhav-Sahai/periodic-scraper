"""
Article scraper module - Handles the scraping of articles from configured sources
"""

import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin
from utils import logger
from typing import Dict, List, Any, Optional
import re
import json

TIMEOUT = 10 # in seconds

def get_article_urls(source_name: str, source_config: Dict[str, Any], 
                     max_pages: int = 5, request_delay: float = 1.0,
                     max_articles: int = None) -> List[str]:
    """
    Extract article URLs from a news source.
    
    Args:
        source_name: Name of the news source
        source_config: Configuration dictionary for the source
        max_pages: Maximum number of pages to scrape
        request_delay: Delay between requests in seconds
        max_articles: Maximum number of articles to extract
        
    Returns:
        List of article URLs
    """
    urls = []
    base_url = source_config['base_url']
    article_selector = source_config['article_selector']
    headers = source_config.get('headers', {'User-Agent': 'Mozilla/5.0'})
    
    # Get source-specific max articles limit or use the provided default
    source_max_articles = source_config.get('max_articles', max_articles)
    
    logger.info(f"Getting article URLs from {source_name} at {base_url}")
    if source_max_articles:
        logger.info(f"Limiting to maximum {source_max_articles} articles")
    
    try:
        # Get the initial page
        response = requests.get(base_url, headers=headers)
        response.raise_for_status()
        
        # Parse with BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all article links - support multiple selectors separated by commas
        all_links = []
        for selector in article_selector.split(','):
            selector = selector.strip()
            links = soup.select(selector)
            all_links.extend(links)
            
        if not all_links:
            logger.warning(f"No links found on {base_url} using selectors '{article_selector}'")
        else:
            logger.info(f"Found {len(all_links)} links on {base_url}")
            
            # Extract URLs
            for link in all_links:
                # Check if we've reached the maximum
                if source_max_articles and len(urls) >= source_max_articles:
                    logger.info(f"Reached maximum limit of {source_max_articles} article URLs")
                    break
                    
                href = link.get('href')
                if href:
                    # Skip internal page anchors, javascript links, etc.
                    if href.startswith('#') or href.startswith('javascript:'):
                        continue
                        
                    # Handle relative URLs
                    if not href.startswith(('http://', 'https://')):
                        full_url = urljoin(base_url, href)
                    else:
                        full_url = href
                    
                    # Special handling for CNN - check for date in URL
                    if source_name.lower() == 'cnn':
                        # CNN article URLs typically have a date pattern like /2025/02/25/
                        date_pattern = r'/\d{4}/\d{2}/\d{2}/'
                        if re.search(date_pattern, full_url):
                            urls.append(full_url)
                    # Special handling for NYTimes
                    elif source_name.lower().startswith('nytimes'):
                        if is_nytimes_article_url(full_url):
                            urls.append(full_url)
                    elif source_name.lower().startswith('bbc'):
                        if is_bbc_article_url(full_url):
                            urls.append(full_url)
                    elif 'guardian' in source_name.lower():
                        if is_guardian_article_url(full_url):
                            urls.append(full_url)
                    else:
                        # Default behavior for all other sources remains unchanged
                        urls.append(full_url)
                
                # Check again after potentially adding a URL
                if source_max_articles and len(urls) >= source_max_articles:
                    logger.info(f"Reached maximum limit of {source_max_articles} article URLs")
                    break
    
    except Exception as e:
        logger.error(f"Error getting article URLs from {source_name}: {e}")
    
    # Remove duplicates and limit to max_articles
    unique_urls = list(set(urls))
    if source_max_articles and len(unique_urls) > source_max_articles:
        unique_urls = unique_urls[:source_max_articles]
        
    logger.info(f"Found {len(unique_urls)} unique article URLs from {source_name}")
    
    return unique_urls

def get_date_from_url(url):
    """
    Extract date from URL for sources that include dates in URL paths.
    
    Args:
        url: The article URL
        
    Returns:
        Datetime object or None if date couldn't be extracted
    """
    # Common URL date patterns
    patterns = [
        # CNN, WaPo, etc: /2023/03/25/
        r'/(\d{4})/(\d{1,2})/(\d{1,2})/',
        
        # NYT style: /2023/03/25/world/
        r'/(\d{4})/(\d{1,2})/(\d{1,2})/\w+/',
        
        # URLs with date at the end: example-story-20230325
        r'-(\d{4})(\d{2})(\d{2})$',
        
        # Guardian style: /2023/mar/25/
        r'/(\d{4})/([a-z]{3})/(\d{1,2})/',
    ]
    
    month_abbr = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
    }
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            try:
                year, month, day = match.groups()
                
                # Convert month abbr to number if needed
                if month.isalpha():
                    month = month_abbr.get(month.lower(), 1)
                
                year = int(year)
                month = int(month)
                day = int(day)
                
                # Basic validation
                if 1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                    return datetime(year, month, day)
            except (ValueError, AttributeError):
                continue
    
    # BBC specific pattern with timestamp at end
    bbc_match = re.search(r'-(\d{8})$', url)
    if bbc_match:
        try:
            # BBC article IDs sometimes contain dates in format YYYYMMDD
            date_str = bbc_match.group(1)
            if len(date_str) == 8:
                year = int(date_str[:4])
                month = int(date_str[4:6])
                day = int(date_str[6:8])
                if 1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                    return datetime(year, month, day)
        except ValueError:
            pass
    
    return None

def extract_article_bs4(url: str, source_name: str, source_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    headers = source_config.get('headers', {'User-Agent': 'Mozilla/5.0'})
    
    try:
        response = requests.get(url, headers=headers, timeout=TIMEOUT)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract title using source-specific selector if available
        title = None
        title_selector = source_config.get('title_selector')
        if title_selector:
            title_element = soup.select_one(title_selector)
            if title_element:
                title = title_element.text.strip()
        
        # Fallback if no title found
        if not title:
            title_element = soup.find('h1') or soup.find('title')
            if title_element:
                title = title_element.text.strip()
        
        # Extract publication date
        pub_date = extract_date(soup, url)
        
        # If we couldn't extract a date, skip this article
        if not pub_date:
            logger.warning(f"Error: Could not extract date from {url}")
            return None
            
        # Extract author using source-specific selector if available
        authors = []
        author_selector = source_config.get('author_selector')
        if author_selector:
            author_elements = soup.select(author_selector)
            if author_elements:
                for author_elem in author_elements:
                    authors.append(author_elem.text.strip())
        
        # Fallback author extraction methods
        if not authors:
            author_elements = soup.select('a[rel="author"]') or soup.select('span[class*="author"]')
            if author_elements:
                for author_elem in author_elements:
                    authors.append(author_elem.text.strip())
        
            if not authors:
                # Try meta tags
                author_meta = soup.find('meta', {'name': 'author'})
                if author_meta and author_meta.get('content'):
                    authors.append(author_meta.get('content'))
        
        author = ', '.join(authors) if authors else 'Unknown'
        
        # Extract content using source-specific selector if available
        content = ""
        content_selector = source_config.get('content_selector')
        if content_selector:
            content_elements = soup.select(content_selector)
            if content_elements:
                content = '\n\n'.join([p.text.strip() for p in content_elements if p.text.strip()])
        
        # Fallback content extraction methods
        if not content:
            content_elements = soup.select('article p') or soup.select('div[class*="article"] p') or soup.select('div[class*="content"] p')
            content = '\n\n'.join([p.text.strip() for p in content_elements if p.text.strip()])
            
            # If still no content, try a more generic approach
            if not content:
                all_paragraphs = soup.find_all('p')
                # Filter out navigation, footer, etc.
                content_paragraphs = [
                    p for p in all_paragraphs 
                    if len(p.text.strip()) > 100  # Longer paragraphs are likely article content
                    and not p.find_parent(['nav', 'footer', 'header'])
                ]
                content = '\n\n'.join([p.text.strip() for p in content_paragraphs])
        
        # This is our generated metadata
        article_data = {
            'title': title if title else 'Unknown Title',
            'author': author,
            'content': content,
            'source': source_name,
            'url': url,
            'date': pub_date.strftime('%Y-%m-%d'),
        }
        
        return article_data
        
    except Exception as e:
        logger.error(f"Error extracting article {url}: {e}")
        return None

def extract_article(url: str, source_name: str, source_config: Dict[str, Any],
                   start_date: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
    """
    Extract content and metadata from an article URL.
    
    Args:
        url: URL of the article to scrape
        source_name: Name of the news source
        source_config: Configuration for the source
        start_date: Only include articles published after this date
        
    Returns:
        Dictionary containing article data or None if extraction failed
    """
    logger.info(f"Extracting article: {url}")
    
    article_data = extract_article_bs4(url, source_name, source_config)
    
    if article_data and start_date:
        # Skip articles older than start_date if provided
        article_date = datetime.strptime(article_data['date'], '%Y-%m-%d')
        if article_date < start_date:
            logger.info(f"Skipping article from {article_date}, before start date {start_date}")
            return None
    
    return article_data

def scrape_source(source_name: str, source_config: Dict[str, Any], 
                 settings: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Scrape articles from a specific news source.
    
    Args:
        source_name: Name of the news source
        source_config: Configuration dictionary for the source
        settings: Global settings dictionary
        
    Returns:
        List of scraped article dictionaries
    """
    logger.info(f"Starting scraping for source: {source_name}")
    
    request_delay = float(settings.get('request_delay', 1.0))
    start_date_str = settings.get('start_date')
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d") if start_date_str else None
    
    # Get max articles limit (either from source config or global settings)
    max_articles = source_config.get('max_articles', settings.get('max_articles_per_source'))
    
    urls = get_article_urls(
        source_name=source_name,
        source_config=source_config,
        request_delay=request_delay,
        max_articles=max_articles
    )
    
    # Extract articles
    articles = []
    for url in urls:
        article_data = extract_article(
            url=url,
            source_name=source_name,
            source_config=source_config,
            start_date=start_date
        )
        
        if article_data:
            articles.append(article_data)
            logger.info(f"Extracted article: {article_data['title']}")
            
            # if we've reached the maximum number of articles
            if max_articles and len(articles) >= max_articles:
                logger.info(f"Reached maximum limit of {max_articles} articles for {source_name}")
                break
        
        # do not bombard our source
        time.sleep(request_delay)
    
    logger.info(f"Completed scraping for {source_name}. Extracted {len(articles)} articles.")
    return articles

def is_nytimes_article_url(url):
    """
    Determines if a NYTimes URL is likely an article based on its pattern.
    
    Args:
        url: The URL to check
        
    Returns:
        Boolean indicating if the URL is likely an article
    """
    # Skip pagination and section links
    if '?page=' in url or url.endswith('/section/politics') or url.endswith('/section/world') or url.endswith('/section/business'):
        return False
        
    # Skip video pages
    if '/video/' in url:
        return False
    
    # Accept Spanish articles
    if '/es/' in url and '/espanol/' in url:
        return True
        
    # Articles usually have a date pattern in the URL
    date_pattern = r'/\d{4}/\d{2}/\d{2}/'
    return bool(re.search(date_pattern, url))

def is_bbc_article_url(url):
    """
    Determines if a BBC URL is likely an article based on its pattern.
    
    Args:
        url: The URL to check
        
    Returns:
        Boolean indicating if the URL is likely an article
    """
    # Skip pagination, categories, tags, etc.
    if '/topics/' in url or '/tags/' in url or '/live/' in url or '/programmes/' in url:
        return False
        
    # Skip video-only pages
    if '/av/' in url:
        return False
    
    # Accept articles with these patterns
    if '/news/articles/' in url or '/news/uk-' in url or '/news/world-' in url or '/news/business-' in url:
        return True
    
    # Many BBC articles have a numeric ID in the URL
    numeric_pattern = r'/news/[-a-z]+-\d+'
    return bool(re.search(numeric_pattern, url))

def is_guardian_article_url(url):
    """
    Determines if a Guardian URL is likely an article based on its pattern.
    
    Args:
        url: The URL to check
        
    Returns:
        Boolean indicating if the URL is likely an article
    """
    # Skip pagination, categories, tags, etc.
    if '/help/' in url or '/about/' in url or '/info/' in url or '/profile/' in url:
        return False
        
    # Skip section pages and other non-article pages
    if url.endswith('/world') or url.endswith('/politics') or url.endswith('/business'):
        return False
    
    # Skip search results
    if '/search?' in url:
        return False
    
    # Skip static assets, images, and non-article sections
    if '/static/' in url or '/images/' in url or '/media/' in url or '/video/' in url:
        return False
    
    # Skip newsletter sign-ups, subscriptions
    if '/sign-up/' in url or '/subscribe/' in url or '/newsletters/' in url:
        return False
    
    # Accept paths with date patterns (YYYY/mon/dd)
    date_pattern = r'/\d{4}/[a-z]{3}/\d{2}/'
    if re.search(date_pattern, url):
        return True
        
    # Accept article URLs that contain year/month/date in another format
    date_pattern_alt = r'/\d{4}/\d{2}/\d{2}/'
    if re.search(date_pattern_alt, url):
        return True
    
    # Most Guardian articles end with a descriptive slug
    segments = url.rstrip('/').split('/')
    if len(segments) > 4 and '-' in segments[-1]:
        return True
        
    return False

# EVERYTHING AFTER IS JUST TO EXTRACT DATE

def extract_date(soup, url):
    """
    Extract publication date using multiple strategies, ordered by reliability.
    
    Args:
        soup: BeautifulSoup object of the article page
        url: URL of the article (for URL-based date extraction fallback)
        
    Returns:
        datetime object or None if date couldn't be extracted
    """
    # Strategy 1: Try to get date from URL first
    url_date = get_date_from_url(url)
    if url_date:
        return url_date
    
    # Strategy 2: JSON-LD structured data (highly reliable when available)
    json_ld_date = extract_date_from_json_ld(soup)
    if json_ld_date:
        return json_ld_date
    
    # Strategy 3: Standard meta tags used by many news sites
    meta_tags = [
        {'property': 'article:published_time'},  # Open Graph
        {'property': 'article:modified_time'},   # Fallback to modified time
        {'name': 'pubdate'},                     # Common for older sites
        {'name': 'publishdate'},                 # Variation
        {'name': 'date'},                        # Generic
        {'name': 'published-date'},              # Used by some news sites
        {'itemprop': 'datePublished'},           # Schema.org markup
        {'itemprop': 'dateModified'},            # Schema.org modified date
        {'name': 'DC.date.issued'},              # Dublin Core
        {'name': 'DC.date.created'},             # Dublin Core
        {'name': 'DC.date'},                     # Dublin Core
        {'name': 'article.published'},           # Custom CMS
        {'name': 'article.created'},             # Custom CMS
        {'name': 'date_published'},              # Custom CMS
        {'property': 'og:published_time'},       # Open Graph variation
    ]
    
    for meta_attrs in meta_tags:
        meta_tag = soup.find('meta', meta_attrs)
        if meta_tag and meta_tag.get('content'):
            try:
                date_str = meta_tag.get('content')
                # Handle common ISO format with or without timezone
                if 'T' in date_str:
                    if date_str.endswith('Z'):
                        pub_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    else:
                        pub_date = datetime.fromisoformat(date_str)
                    return pub_date
                # Try other common formats
                for fmt in [
                    '%Y-%m-%d',
                    '%Y/%m/%d',
                    '%B %d, %Y',
                    '%d %B %Y',
                ]:
                    try:
                        pub_date = datetime.strptime(date_str, fmt)
                        return pub_date
                    except ValueError:
                        continue
            except Exception:
                pass
    
    # Strategy 4: Look for time elements
    time_elements = soup.find_all('time')
    for time_element in time_elements:
        # Try to find a datetime attribute
        datetime_str = time_element.get('datetime') or time_element.get('content')
        if datetime_str:
            try:
                # Try ISO format first
                if 'T' in datetime_str:
                    if datetime_str.endswith('Z'):
                        pub_date = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
                    else:
                        pub_date = datetime.fromisoformat(datetime_str)
                    return pub_date
                # Try common date formats
                for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%B %d, %Y', '%d %B %Y']:
                    try:
                        pub_date = datetime.strptime(datetime_str, fmt)
                        return pub_date
                    except ValueError:
                        continue
            except Exception:
                pass
    
    # Strategy 5: Look for elements with date-related classes
    date_classes = [
        'date', 'time', 'timestamp', 'article-date', 'article__date',
        'publication-date', 'byline-date', 'meta-date', 'story-date',
        'publish-date', 'post-date'
    ]
    
    for class_name in date_classes:
        elements = soup.select(f'[class*="{class_name}"]')
        for element in elements:
            date_text = element.get_text().strip()
            # Try common date formats in text
            for fmt in ['%Y-%m-%d', '%B %d, %Y', '%d %B %Y', '%m/%d/%Y', '%d/%m/%Y']:
                try:
                    pub_date = datetime.strptime(date_text, fmt)
                    return pub_date
                except ValueError:
                    continue
    
    # No date found
    return None

def extract_date_from_json_ld(soup):
    """
    Extract date from JSON-LD structured data.
    
    Args:
        soup: BeautifulSoup object
        
    Returns:
        datetime object or None
    """
    # Look for JSON-LD script tags
    script_tags = soup.find_all('script', type='application/ld+json')
    for script in script_tags:
        try:
            data = json.loads(script.string)
            
            # Handle array format
            if isinstance(data, list):
                data = data[0]
            
            # Check for datePublished field
            if isinstance(data, dict):
                # Direct datePublished property
                if 'datePublished' in data and isinstance(data['datePublished'], str):
                    try:
                        date_str = data['datePublished']
                        if 'T' in date_str:
                            if date_str.endswith('Z'):
                                return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                            else:
                                return datetime.fromisoformat(date_str)
                    except ValueError:
                        pass
                
                # Check in nested article object
                if 'article' in data and isinstance(data['article'], dict):
                    if 'datePublished' in data['article'] and isinstance(data['article']['datePublished'], str):
                        try:
                            date_str = data['article']['datePublished']
                            if 'T' in date_str:
                                if date_str.endswith('Z'):
                                    return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                                else:
                                    return datetime.fromisoformat(date_str)
                        except ValueError:
                            pass
                
                # Check in @graph array
                if '@graph' in data and isinstance(data['@graph'], list) and len(data['@graph']) > 0:
                    for item in data['@graph']:
                        if isinstance(item, dict) and 'datePublished' in item:
                            try:
                                date_str = item['datePublished']
                                if 'T' in date_str:
                                    if date_str.endswith('Z'):
                                        return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                                    else:
                                        return datetime.fromisoformat(date_str)
                            except ValueError:
                                continue
                        
        except (json.JSONDecodeError, AttributeError):
            continue
    
    return None