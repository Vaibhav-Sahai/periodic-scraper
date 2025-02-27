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

def get_date_from_url(url: str) -> Optional[datetime]:
    """
    Extract date from URL for sources like CNN that include dates in URL paths.
    
    Args:
        url: The article URL
        
    Returns:
        Datetime object or None if date couldn't be extracted
    """
    # CNN URLs typically have date format like /2025/02/25/
    match = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', url)
    if match:
        year, month, day = match.groups()
        try:
            return datetime(int(year), int(month), int(day))
        except ValueError:
            return None
    return None

def extract_article_bs4(url: str, source_name: str, source_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Extract content and metadata from an article URL using BeautifulSoup.
    
    Args:
        url: URL of the article to scrape
        source_name: Name of the news source
        source_config: Configuration for the source
        
    Returns:
        Dictionary containing article data or None if extraction failed
    """
    headers = source_config.get('headers', {'User-Agent': 'Mozilla/5.0'})
    
    try:
        response = requests.get(url, headers=headers)
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
        pub_date = None

        # Try to get date from URL first 
        url_date = get_date_from_url(url)
        if url_date:
            pub_date = url_date

        # Look for meta tags with publication date - especially for AP News
        if not pub_date:
            # Check for article:published_time meta tag (used by AP News)
            published_meta = soup.find('meta', {'property': 'article:published_time'})
            if published_meta and published_meta.get('content'):
                try:
                    date_str = published_meta.get('content')
                    # Handle both formats with and without timezone
                    if 'T' in date_str:
                        if date_str.endswith('Z'):
                            pub_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                        else:
                            pub_date = datetime.fromisoformat(date_str)
                except (ValueError, TypeError) as e:
                    logger.warning(f"Error parsing meta date: {e}")

        # If still no date, try time elements as before
        if not pub_date:
            time_element = soup.find('time') or soup.select_one('span[class*="date"]') or soup.select_one('div[class*="date"]')
            if time_element:
                # Try to find a datetime attribute
                datetime_str = time_element.get('datetime') or time_element.get('content')
                if datetime_str:
                    try:
                        pub_date = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
                    except (ValueError, TypeError):
                        # If parsing fails, keep None
                        pass
        
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
        
        # This is our generate metadata
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