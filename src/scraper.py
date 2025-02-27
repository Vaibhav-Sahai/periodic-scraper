"""
Simple News Scraper - Basic implementation to read from config and prepare for parsing
"""

import yaml
import logging
from datetime import datetime
from typing import Dict, Any

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger("news_scraper")

def load_config(config_path: str) -> Dict[str, Any]:
    """
    Load configuration from a YAML file.
    
    Args:
        config_path: Path to the YAML configuration file
        
    Returns:
        Dictionary containing the configuration
    """
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            logger.info(f"Loaded configuration from {config_path}")
            return config
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        raise

def init_sources(config: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Process source configurations.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Dictionary of processed source configurations
    """
    sources = {}
    for name, source_config in config.get('sources', {}).items():
        if source_config.get('base_url') and source_config.get('article_selector'):
            sources[name] = source_config
            logger.info(f"Initialized source: {name}")
        else:
            logger.warning(f"Skipping source {name}: missing required configuration")
    
    return sources

def get_settings(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract and validate settings from config.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Dictionary of settings
    """
    settings = config.get('settings', {})
    
    if 'start_date' in settings:
        try:
            start_date = datetime.strptime(settings['start_date'], "%Y-%m-%d")
            logger.info(f"Filtering articles from {start_date.strftime('%Y-%m-%d')}")
        except ValueError as e:
            logger.warning(f"Invalid start_date format: {e}. Using current date.")
            settings['start_date'] = datetime.now().strftime("%Y-%m-%d")
    else:
        logger.warning("No start_date provided. Using current date.")
        settings['start_date'] = datetime.now().strftime("%Y-%m-%d")
    
    settings.setdefault('output_csv', 'news_articles.csv')
    settings.setdefault('request_delay', 1.0)
    
    return settings

def main():
    """Main function to demonstrate config loading."""
    config_path = 'src/config.yaml'
    
    try:
        config = load_config(config_path)
        
        sources = init_sources(config)
        logger.info(f"Initialized {len(sources)} sources: {', '.join(sources.keys())}")
        
        settings = get_settings(config)
        logger.info(f"Settings: output_csv={settings['output_csv']}, " 
                    f"request_delay={settings['request_delay']}, "
                    f"start_date={settings['start_date']}")
        
        #@TODO: get started on parsing logic
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
    exit(main())