"""
News Article Scraper - Main module
"""

import argparse
import sys
from utils import logger, load_config, init_sources, get_settings

def main():
    """Main entry point for the news scraper."""
    parser = argparse.ArgumentParser(description='News Article Scraper')
    parser.add_argument('--config', default='src/config.yaml', help='Path to configuration file')
    parser.add_argument('--log-level', 
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        default='INFO',
                        help='Set the logging level')
    args = parser.parse_args()
    
    # adjust level as needed
    if args.log_level:
        level = getattr(logging, args.log_level)
        for handler in logger.handlers:
            if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
                handler.setLevel(level)
    
    try:
        config = load_config(args.config)
        sources = init_sources(config)
        logger.info(f"Initialized {len(sources)} sources: {', '.join(sources.keys())}")
        
        settings = get_settings(config)
        logger.info(f"Settings: output_csv={settings['output_csv']}, " 
                    f"request_delay={settings['request_delay']}, "
                    f"start_date={settings['start_date']}")
        
        # @TODO: finish up parsing logic
        logger.info("Configuration loaded - ready for parsing")
        
        if sources:
            first_source_name = next(iter(sources))
            first_source = sources[first_source_name]
            logger.info(f"First source: {first_source_name}")
            logger.info(f"  - URL: {first_source['base_url']}")
            logger.info(f"  - Selector: {first_source['article_selector']}")
    
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    import logging  # Import here to access the logging module
    sys.exit(main())