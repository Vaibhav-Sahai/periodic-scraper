"""
Simple scheduler - Runs scraper and updates Huggingface every 12 hours
Only pushes when there are new articles
"""

import os
import sys
import time
import uuid
import datetime
from collections import OrderedDict
from datasets import load_dataset
from huggingface_hub import login

# Import runner directly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from runner import run as run_scraper

def count_articles(csv_path):
    """Count the number of articles in the CSV file"""
    try:
        import pandas as pd
        df = pd.read_csv(csv_path)
        return len(df)
    except Exception as e:
        print(f"Error counting articles: {e}")
        return 0

def upload_to_huggingface(csv_path, repo_id="VaibhavSahai/news_articles"):
    """Process and upload the dataset to Huggingface"""
    try:
        print("Processing dataset...")
        
        # Count articles before processing
        before_count = count_articles(csv_path)
        print(f"Found {before_count} articles before processing")
        
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
        
        # Calculate the number of new articles
        diff = after_count - before_count
        
        # Only push if there are new articles
        if diff > 0:
            # Create commit message
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            commit_message = f"Update {now}: Added {diff} new articles"
            
            # Push to hub
            print(f"Pushing to Huggingface with message: {commit_message}")
            dataset.push_to_hub(repo_id, commit_message=commit_message)
            
            print(f"Successfully uploaded {diff} new articles to {repo_id}")
            return True
        else:
            print("No new articles found, skipping upload")
            return False
    
    except Exception as e:
        print(f"Error uploading to Huggingface: {e}")
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
        print("Could not find news_articles.csv")
        return 1
    
    print(f"Using CSV file: {csv_path}")
    
    # Check for Huggingface token
    if not os.environ.get('HF_TOKEN'):
        print("Warning: HF_TOKEN environment variable not set")
        print("Will attempt to use cached credentials")
    
    # Option to run once or continuously
    continuous = True
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        continuous = False
        print("Running in single-execution mode")
    
    try:
        while True:
            # Run the scraper
            print("Starting scraper to gather new articles...")
            scraper_result = run_scraper()
            
            if scraper_result == 0:
                print("Scraper completed successfully")
                # Upload to Huggingface only if there are new articles
                upload_to_huggingface(csv_path)
            else:
                print(f"Scraper failed with exit code {scraper_result}")
            
            # Exit if we're in single-execution mode
            if not continuous:
                break
                
            # Sleep for 12 hours
            next_run = datetime.datetime.now() + datetime.timedelta(hours=12)
            print(f"Next run scheduled for: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
            time.sleep(12 * 3600)  # 12 hours in seconds
            
    except KeyboardInterrupt:
        print("Scheduler stopped by user")
    except Exception as e:
        print(f"Error in scheduler: {e}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())