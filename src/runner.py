"""
Runner module - Entry point for the news scraper application
"""

import sys
import os
from scraper import main as scraper_main

def run():
    """
    Run the news scraper with default configuration
    """
    # find the directory where the script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    os.chdir(script_dir)
    
    return scraper_main()

if __name__ == "__main__":
    sys.exit(run())