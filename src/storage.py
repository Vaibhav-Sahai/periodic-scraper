"""
Data storage module - Handles saving and loading article data
"""

import os
import csv
import pandas as pd
from utils import logger
from typing import Dict, List, Any

def load_existing_articles(csv_path: str) -> Dict[str, Dict[str, Any]]:
    """
    Load existing articles from a CSV file.
    
    Args:
        csv_path: Path to the CSV file
        
    Returns:
        Dictionary mapping article URLs to their data
    """
    existing = {}
    
    if os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path)
            for _, row in df.iterrows():
                existing[row['url']] = row.to_dict()
                
            logger.info(f"Loaded {len(existing)} existing articles from {csv_path}")
        except Exception as e:
            logger.error(f"Error loading existing articles from {csv_path}: {e}")
    else:
        logger.info(f"No existing articles file found at {csv_path}")
    
    return existing

def save_articles(articles: List[Dict[str, Any]], csv_path: str, 
                 existing_articles: Dict[str, Dict[str, Any]] = None) -> int:
    """
    Save articles to a CSV file, avoiding duplicates.
    
    Args:
        articles: List of article dictionaries to save
        csv_path: Path to the CSV file
        existing_articles: Dictionary of existing articles
        
    Returns:
        Number of new articles saved
    """
    if not articles:
        logger.info("No articles to save")
        return 0
    
    if existing_articles is None:
        existing_articles = load_existing_articles(csv_path)
    
    new_articles = []
    for article in articles:
        if article['url'] not in existing_articles:
            new_articles.append(article)
    
    if not new_articles:
        logger.info("No new articles to save")
        return 0
    
    try:
        all_articles = list(existing_articles.values()) + new_articles
        
        df = pd.DataFrame(all_articles)
        
        required_columns = ['title', 'author', 'content', 'source', 'url', 'date']
        for col in required_columns:
            if col not in df.columns:
                df[col] = ''
        
        df.to_csv(csv_path, index=False, quoting=csv.QUOTE_ALL)
        logger.info(f"Saved {len(new_articles)} new articles to {csv_path}")
        
        return len(new_articles)
        
    except Exception as e:
        logger.error(f"Error saving articles to {csv_path}: {e}")
        return 0