"""
News Article Scraper - Main module
"""

import argparse
import sys
import time
import logging
from utils import logger, load_config, init_sources, get_settings
from article_scraper import scrape_source, get_article_urls, extract_article
from storage import load_existing_articles, save_articles

def main():
    """Main entry point for the news scraper."""

    parser = argparse.ArgumentParser(description='News Article Scraper')
    parser.add_argument('--config', default='config.yaml', help='Path to configuration file')
    parser.add_argument('--log-level', 
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        default='INFO',
                        help='Set the logging level')
    parser.add_argument('--source', help='Scrape only a specific source')
    parser.add_argument('--save-interval', type=int, help='Save interval (overrides config)')
    args = parser.parse_args()
    

    if args.log_level:
        level = getattr(logging, args.log_level)
        for handler in logger.handlers:
            if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
                handler.setLevel(level)
    
    try:
        config = load_config(args.config)
        sources = init_sources(config)
        if not sources:
            logger.error("No valid sources found in configuration")
            return 1
            
        logger.info(f"Initialized {len(sources)} sources: {', '.join(sources.keys())}")
        
        settings = get_settings(config)
        logger.info(f"Settings: output_csv={settings['output_csv']}, " 
                    f"request_delay={settings['request_delay']}, "
                    f"start_date={settings['start_date']}")
        
        save_interval = args.save_interval if args.save_interval is not None else settings.get('save_interval', 0)
        if save_interval > 0:
            logger.info(f"Will save to CSV after every {save_interval} articles")
        
        output_csv = settings['output_csv']
        existing_articles = load_existing_articles(output_csv)
        
        if args.source:
            if args.source in sources:
                sources = {args.source: sources[args.source]}
                logger.info(f"Filtering to scrape only source: {args.source}")
            else:
                logger.error(f"Source '{args.source}' not found in configuration")
                return 1
        
        all_articles = []
        articles_since_save = 0
        
        for source_name, source_config in sources.items():
            try:
                logger.info(f"Processing source: {source_name}")
                
                # If using incremental save, we'll handle articles one by one
                if save_interval > 0:
                    # Get article URLs
                    max_articles = source_config.get('max_articles', settings.get('max_articles_per_source'))
                    
                    urls = get_article_urls(
                        source_name=source_name,
                        source_config=source_config,
                        request_delay=float(settings.get('request_delay', 1.0)),
                        max_articles=max_articles
                    )
                    
                    start_date_str = settings.get('start_date')
                    start_date = None
                    if start_date_str:
                        from datetime import datetime
                        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
                    
                    source_articles = []
                    
                    # Process each URL
                    for url in urls:
                        article_data = extract_article(
                            url=url,
                            source_name=source_name,
                            source_config=source_config,
                            start_date=start_date
                        )
                        
                        if article_data:
                            source_articles.append(article_data)
                            all_articles.append(article_data)
                            articles_since_save += 1
                            
                            logger.info(f"Extracted article: {article_data['title']}")
                            
                            if save_interval > 0 and articles_since_save >= save_interval:
                                num_saved = save_articles(all_articles, output_csv, existing_articles)
                                logger.info(f"Checkpoint save: Added {num_saved} new articles to {output_csv}")
                                
                                for article in all_articles:
                                    existing_articles[article['url']] = article
                                
                                # counter reset
                                articles_since_save = 0
                            
                            # if we've reached the maximum number of articles for this source
                            if max_articles and len(source_articles) >= max_articles:
                                logger.info(f"Reached maximum limit of {max_articles} articles for {source_name}")
                                break
                        
                        # let us not bombard our sources
                        time.sleep(float(settings.get('request_delay', 1.0)))
                    
                    logger.info(f"Scraped {len(source_articles)} articles from {source_name}")
                    
                else:
                    # OG approach - get all articles at once
                    articles = scrape_source(source_name, source_config, settings)
                    all_articles.extend(articles)
                    logger.info(f"Scraped {len(articles)} articles from {source_name}")
                
            except Exception as e:
                logger.error(f"Error scraping source {source_name}: {e}")
        
        # save of any remaining articles
        if all_articles and (articles_since_save > 0 or save_interval == 0):
            num_new = save_articles(all_articles, output_csv, existing_articles)
            logger.info(f"Scraping completed. Added {num_new} new articles to {output_csv}")
    
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    import logging  
    sys.exit(main())