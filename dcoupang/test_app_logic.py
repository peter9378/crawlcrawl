import sys
import os

# Add current directory to sys.path so we can import app
sys.path.append(os.getcwd())

from app import crawl_coupang_sync

def test_app():
    print("Testing app.crawl_coupang_sync...")
    keyword = "하리보"
    try:
        result = crawl_coupang_sync(keyword)
        print(f"Result: {result}")
        if "suggestions" in result:
             print("SUCCESS: Result structure is correct.")
        else:
             print("FAILURE: 'suggestions' key missing.")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_app()
