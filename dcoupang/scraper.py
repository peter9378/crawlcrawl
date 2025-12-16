import logging
import traceback
import time
import urllib.parse
import platform
from DrissionPage import ChromiumPage, ChromiumOptions

class Scraper:
    def __init__(self):
        self.logger = logging.getLogger("uvicorn")

    def get_coupang_suggestions(self, query: str):
        """
        Coupang 연관검색어 크롤링 (DrissionPage Version)
        """
        final_list = []
        encoded_query = urllib.parse.quote(query)
        # Direct URL
        url = f"https://www.coupang.com/np/search?component=&q={encoded_query}&channel=user"
        
        page = None
        try:
            self.logger.info(f"[COUPANG] Initializing DrissionPage for query: {query}")
            
            # Setup DrissionPage Options
            co = ChromiumOptions()
            
            # 1. Browser Path: Auto-detect or use specific path if needed
            # Removing hardcoded Mac path to allow auto-detection on Linux/Mac
            # If explicit path is needed on VM, set it via:
            # co.set_paths(browser_path='/usr/bin/google-chrome') 
            
            co.auto_port()
            
            # 2. Headless Mode: Essential for VM environments
            # Using 'new' headless mode which is more detectable but stable
            # Only enable headless on Linux (assumed server environment)
            if platform.system() == 'Linux':
                co.set_argument('--headless=new')
            
            # 3. Linux/Container compatibility args
            co.set_argument('--no-sandbox')
            co.set_argument('--disable-dev-shm-usage')
            co.set_argument('--disable-gpu')
            
            # Auto port is default, but let's try to be resilient
            # co.auto_port() 
            
            # Initialize with these options
            page = ChromiumPage(co)
            
            self.logger.info(f"[COUPANG] Navigating to: {url}")
            page.get(url)
            
            # Wait for list to load
            # Coupang related keywords usually in:
            # - dl.related-search-keyword
            # - or a#relatedKeyword
            
            # Use 'ele' to wait for element (like Selenium 'wait')
            # Wait up to 5 seconds
            # Try to find common container
            
            # Wait for body to ensure page loaded
            try:
                page.wait.load_complete(timeout=5)
            except:
                pass # Ignore timeout if load is partial, continue to element check
            
            # Check for Access Denied title
            if "Access Denied" in page.title:
                self.logger.warning("[COUPANG] Access Denied detected by DrissionPage")
                # Dump source
                with open("debug_coupang_Drission.html", "w", encoding="utf-8") as f:
                    f.write(page.html)
                return []

            keywords = []
            
            # Extraction Strategy
            # 1. Prioritize 'channel=relate' links (Matches user expectation)
            relate_links = page.eles('tag:a@@href:channel=relate')
            if relate_links:
                for l in relate_links:
                    t = l.text
                    if t: keywords.append(t)
            
            if not keywords:
                # 2. Look for text "연관검색어" (Common in Next.js structure)
                try:
                    label = page.ele('text:연관검색어')
                    if label:
                        # In new UI, label is <span> inside the div container
                        # Look for siblings or parent's siblings
                        parent = label.parent()
                        if parent:
                            # Try finding links in the same container first
                            links = parent.eles('tag:a')
                            for l in links:
                                href = l.attrs.get('href', '')
                                # Ensure it's a search link or has relate param
                                if 'q=' in href or 'channel=relate' in href:
                                    t = l.text
                                    if t and t != "연관검색어": keywords.append(t)
                except Exception as e:
                    self.logger.warning(f"Error finding '연관검색어': {e}")

            if not keywords:
                # 3. Fallback: dl.related-search-keyword
                dl = page.ele('tag:dl@@class:related-search-keyword')
                if dl:
                    links = dl.eles('tag:dd')
                    for l in links:
                        t = l.text
                        if t: keywords.append(t)

            # Deduplicate preserving order
            unique_keywords = list(dict.fromkeys(keywords))
            
            # Filter out the query itself (normalization might be needed)
            normalized_query = query.replace(" ", "").lower()
            filtered_list = []
            for k in unique_keywords:
                # Normalize keyword for comparison
                nk = k.replace(" ", "").lower()
                if nk != normalized_query:
                    filtered_list.append(k)

            # Construct final result format
            result_list = []
            for idx, k in enumerate(filtered_list):
                result_list.append({
                    "rank": idx + 1,
                    "query": k
                })

            final_result = {
                "keyword": query,
                "result": result_list
            }
            
            self.logger.info(f"[COUPANG] Found {len(result_list)} keywords")
            
            if not result_list:
                with open("debug_coupang_Drission_Empty.html", "w", encoding="utf-8") as f:
                    f.write(page.html)
                self.logger.warning("[COUPANG] Empty results. Dumped HTML to debug_coupang_Drission_Empty.html")

        except Exception as e:
            self.logger.error(f"[COUPANG] Error in get_coupang_suggestions: {e}")
            self.logger.error(traceback.format_exc())
            # Return empty structure on error
            final_result = {
                "keyword": query,
                "result": []
            }
        finally:
            if page:
                try:
                    page.quit()
                except:
                    pass
            
        return final_result
