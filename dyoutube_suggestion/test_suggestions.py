import sys
import os
import logging

# Add current directory to path
sys.path.append(os.getcwd())

from scraper import Scraper

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("uvicorn")

def test_suggestions():
    scraper = Scraper()
    query = "속건조"
    
    print(f"Testing get_suggestions for query: '{query}'")
    suggestions = scraper.get_suggestions(query)
    
    print("\n" + "="*50)
    print(f"Final Suggestions Count: {len(suggestions['result'])}")
    print("="*50)
    for item in suggestions['result']:
        print(f"Rank {item['rank']}: {item['query']}")
    print("="*50)

if __name__ == "__main__":
    test_suggestions()
