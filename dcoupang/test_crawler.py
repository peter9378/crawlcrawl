from scraper import Scraper
import logging

# Configure logging to print to stdout
logging.basicConfig(level=logging.INFO)

def test():
    print("Starting test...")
    scraper = Scraper()
    query = "하리보 젤리"
    print(f"Query: {query}")
    try:
        result = scraper.get_coupang_suggestions(query)
        import json
        print(f"Result: {json.dumps(result, indent=2, ensure_ascii=False)}")
        if result and result.get("result"):
            print("SUCCESS: Suggestions found.")
        else:
            print("WARNING: No suggestions found (could be no related keywords or scraping issue).")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test()
