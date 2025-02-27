"""
Simple scheduler - Runs scraper and updates Huggingface every 12 hours
"""

import os
import sys
import time
import uuid
import datetime
import subprocess
from collections import OrderedDict
from datasets import load_dataset

def run_scraper():
    """Run the scraper to gather new articles"""
    print("Starting scraper to gather new articles...")
    
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        runner_path = os.path.join(script_dir, "runner.py")
        
        result = subprocess.run([sys.executable, runner_path], 
                                capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"Error running scraper: {result.stderr}")
            return False
        
        print("Scraper completed successfully")
        return True
    
    except Exception as e:
        print(f"Error running scraper: {e}")
        return False

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
        
        before_count = count_articles(csv_path)
        print(f"Found {before_count} articles before processing")
        
        dataset = load_dataset('csv', data_files=csv_path)
        
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
        
        after_count = len(dataset['train'])
        
        diff = after_count - before_count
        
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        commit_message = f"Update {now}: Added {diff} new articles" if diff > 0 else f"Update {now}: No new articles"
        
        print(f"Pushing to Huggingface with message: {commit_message}")
        dataset.push_to_hub(repo_id, commit_message=commit_message)
        
        print(f"Successfully uploaded to {repo_id}")
        return True
    
    except Exception as e:
        print(f"Error uploading to Huggingface: {e}")
        return False

def main():
    """Run the scheduler loop"""
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
    
    try:
        while True:
            scraper_success = run_scraper()
            
            if scraper_success:
                upload_to_huggingface(csv_path)
            
            next_run = datetime.datetime.now() + datetime.timedelta(hours=12)
            print(f"Next run scheduled for: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
            time.sleep(12 * 3600) 
            
    except KeyboardInterrupt:
        print("Scheduler stopped by user")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())