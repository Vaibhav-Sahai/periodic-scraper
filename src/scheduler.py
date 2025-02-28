"""
Simple scheduler - Runs scraper and updates Huggingface every 12 hours
Only pushes when there are new articles
"""

import os
import sys
import time
import uuid
import datetime
import pandas as pd
from collections import OrderedDict
from datasets import load_dataset

# Import runner directly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from runner import run as run_scraper
from utils import logger

def count_articles(csv_path):
    """Count the number of articles in the CSV file"""
    try:
        import pandas as pd
        df = pd.read_csv(csv_path)
        return len(df)
    except Exception as e:
        print(f"Error counting articles: {e}")
        return 0

def get_article_count_from_csv(csv_path):
    """Count the number of articles in the CSV file"""
    try:
        df = pd.read_csv(csv_path)
        return len(df)
    except Exception as e:
        logger.error(f"Error counting articles: {e}")
        return 0

def upload_to_huggingface(csv_path, repo_id="VaibhavSahai/news_articles"):
    """Process and upload the dataset to Huggingface"""
    try:
        # Important: Store the article count BEFORE processing
        logger.info(f"Reading CSV file: {csv_path}")
        before_count = get_article_count_from_csv(csv_path)
        logger.info(f"Found {before_count} articles before processing")
        
        # Load the dataset
        dataset = load_dataset('csv', data_files=csv_path)
        
        # Apply transformations
        def add_uuid(example):
            example['uuid'] = str(uuid.uuid5(uuid.NAMESPACE_URL, example['url']))
            return example

        def update_source(example):
            if example['source'] == "cnn":
                example['source'] = "cnn_world"
            elif example['source'] == "fox_news":
                example['source'] = "fox_news_world"
            return example

        def reorder_columns(example):
            return OrderedDict([
                ('uuid', example['uuid']),
                ('title', example['title']),
                ('author', example['author']),
                ('source', example['source']),
                ('url', example['url']),
                ('date', example['date']),
                ('content', example['content']),
            ])
        
        dataset = dataset.map(update_source)
        dataset = dataset.map(add_uuid)
        dataset = dataset.map(reorder_columns)
        
        # Count after processing
        after_count = len(dataset['train'])
        logger.info(f"Found {after_count} articles after processing")
        
        # Calculate the number of new articles
        diff = after_count - before_count
        
        # Only push if there are new articles
        if diff > 0:
            # Create commit message
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            commit_message = f"Update {now}: Added {diff} new articles"
            
            # Push to hub
            logger.info(f"Pushing to Huggingface with message: {commit_message}")
            dataset.push_to_hub(repo_id, commit_message=commit_message)
            
            logger.info(f"Successfully uploaded {diff} new articles to {repo_id}")
            return True
        else:
            logger.info("No new articles found, skipping upload")
            return False
    
    except Exception as e:
        logger.error(f"Error uploading to Huggingface: {e}")
        return False

def main():
    """Run the scheduler loop"""
    # Find the CSV file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(script_dir)
    
    csv_path = None
    for path in [
        os.path.join(script_dir, "news_articles.csv"),
        os.path.join(parent_dir, "news_articles.csv"),
        os.path.join(parent_dir, "src", "news_articles.csv")
    ]:
        if os.path.exists(path):
            csv_path = path
            break
    
    if not csv_path:
        logger.error("Could not find news_articles.csv")
        return 1
    
    logger.info(f"Using CSV file: {csv_path}")
    
    # Check for Huggingface token
    if not os.environ.get('HF_TOKEN'):
        logger.warning("HF_TOKEN environment variable not set")
        logger.warning("Will attempt to use cached credentials")
    
    # Create a persistent file to store the last article count
    tracker_file = os.path.join(os.path.dirname(csv_path), ".last_article_count")
    
    # Function to get and update the tracker
    def get_last_article_count():
        if os.path.exists(tracker_file):
            try:
                with open(tracker_file, 'r') as f:
                    return int(f.read().strip())
            except:
                return 0
        return 0
        
    def save_article_count(count):
        try:
            with open(tracker_file, 'w') as f:
                f.write(str(count))
        except Exception as e:
            logger.error(f"Error saving article count: {e}")
    
    # Option to run once or continuously
    continuous = True
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        continuous = False
        logger.info("Running in single-execution mode")
    
    try:
        while True:
            # Get article count before running scraper
            last_count = get_last_article_count()
            logger.info(f"Last recorded article count: {last_count}")
            
            # Run the scraper
            logger.info("Starting scraper to gather new articles...")
            scraper_result = run_scraper()
            
            if scraper_result == 0:
                logger.info("Scraper completed successfully")
                
                # Get current article count
                current_count = get_article_count_from_csv(csv_path)
                logger.info(f"Current article count: {current_count}")
                
                # Only upload if we have new articles
                if current_count > last_count:
                    logger.info(f"Found {current_count - last_count} new articles")
                    # Add the count difference to the dataset object in upload_to_huggingface
                    # so we know exactly how many articles to report in the commit message
                    upload_success = upload_to_huggingface(csv_path)
                    
                    if upload_success:
                        # Update the tracker file only if upload was successful
                        save_article_count(current_count)
                        logger.info(f"Updated tracker with new count: {current_count}")
                else:
                    logger.info("No new articles found")
            else:
                logger.error(f"Scraper failed with exit code {scraper_result}")
            
            # Exit if we're in single-execution mode
            if not continuous:
                break
                
            # Sleep for 12 hours
            next_run = datetime.datetime.now() + datetime.timedelta(hours=12)
            logger.info(f"Next run scheduled for: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
            time.sleep(12 * 3600)  # 12 hours in seconds
            
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
    except Exception as e:
        logger.error(f"Error in scheduler: {e}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())