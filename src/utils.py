"""
Utility functions for the news scraper
"""

import yaml
import logging
import copy
from datetime import datetime
from typing import Dict, Any

def setup_logger(log_file='scraper.log', console_level=logging.INFO, file_level=logging.DEBUG):
    """
    Set up and configure the logger.
    
    Args:
        log_file: Path to the log file
        console_level: Logging level for console output
        file_level: Logging level for file output
        
    Returns:
        Configured logger
    """
    # Create logger
    logger = logging.getLogger("news_scraper")
    
    # Check if handlers are already configured to avoid duplicate handlers
    if logger.handlers:
        return logger
        
    logger.setLevel(logging.DEBUG)  # Set to lowest level to capture everything
    
    # Create formatters
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_formatter = logging.Formatter('%(levelname)s - %(message)s')
    
    # Create file handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(file_level)
    file_handler.setFormatter(file_formatter)
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(console_formatter)
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logger()

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

def resolve_source_inheritance(sources: Dict[str, Any], common_configs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Resolve source inheritance from common configurations.
    
    Args:
        sources: Sources configuration dictionary
        common_configs: Common configurations dictionary
        
    Returns:
        Dictionary of sources with resolved inheritance
    """
    resolved_sources = {}
    
    for name, source_config in sources.items():
        # Create a new dictionary for this source
        resolved_config = {}
        
        # Check if this source inherits from a common config
        inherit_from = source_config.get('inherit')
        if inherit_from and inherit_from in common_configs:
            # Start with the common config as base
            resolved_config.update(copy.deepcopy(common_configs[inherit_from]))
        
        # Update with source-specific config, overriding inherited values if needed
        for key, value in source_config.items():
            if key != 'inherit':  # Skip the inherit key itself
                resolved_config[key] = value
        
        # Store the resolved config
        resolved_sources[name] = resolved_config
        
    return resolved_sources

def init_sources(config: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Process source configurations.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Dictionary of processed source configurations
    """
    sources = {}
    
    # Check if we have the new format with common_configs
    if 'common_configs' in config and 'sources' in config:
        common_configs = config.get('common_configs', {})
        source_configs = config.get('sources', {})
        
        # Resolve inheritance
        resolved_sources = resolve_source_inheritance(source_configs, common_configs)
        
        # Validate sources
        for name, source_config in resolved_sources.items():
            if source_config.get('base_url') and source_config.get('article_selector'):
                sources[name] = source_config
                logger.info(f"Initialized source: {name}")
            else:
                logger.warning(f"Skipping source {name}: missing required configuration")
                
    # Fallback to old format
    else:
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
            # Convert to datetime object to validate format
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