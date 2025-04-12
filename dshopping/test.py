from playwright.sync_api import sync_playwright
import time
import random

def crawl_site(url, num_requests=5, delay_range=(3, 7)):
    with sync_playwright() as p:
        # Launch Chromium with extra arguments to reduce detection
        browser = p.chromium.launch(
            headless=False,  # Set True to run headless after testing
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled"
            ]
        )
        # Create a new browser context with a common user agent and locale
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.5845.110 Safari/537.36",
            locale="ko-KR",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()
        
        for i in range(num_requests):
            print(f"Request {i+1}: Loading {url} ...")
            page.goto(url, timeout=60000)
            # Allow dynamic content to load
            time.sleep(random.uniform(*delay_range))
            
            # Scroll to trigger lazy-loaded content
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            
            content = page.content()
            print(f"Request {i+1}: Page loaded (first 200 characters):")
            print(content[:200])
            print("-" * 80)
            
            # Wait a bit before the next request
            time.sleep(random.uniform(*delay_range))
        
        context.close()
        browser.close()

if __name__ == "__main__":
    target_url = "https://search.shopping.naver.com/ns/search?query=%EC%B9%98%ED%86%A0%EC%8A%A4"
    crawl_site(target_url)

