from selenium.webdriver import Chrome, ChromeOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium_driver import SeleniumDriver
from bs4 import BeautifulSoup
import json
import logging
import re
import time
from datetime import datetime, timedelta
import traceback

class Scraper:
    def __init__(self):
        # Logger instance
        self.logger = logging.getLogger('uvicorn')
        self.scroll_position = 0

    def scrape_naver_related(self, query: str):
        base_url = 'https://search.naver.com/search.naver?where=nexearch&sm=top_hty&fbm=0&ie=utf8&query='
        results = []
        try:
            with SeleniumDriver(start_url='https://www.naver.com/').driver as driver:
                self.logger.info("Driver generated!")
                driver.get(f'{base_url}{query}')

                self.scroll_down(driver, 5)
                self.logger.info("Scroll down finished, starting crawl")

                soup = BeautifulSoup(driver.page_source, 'html.parser')

                keywords = []
                #links = soup.select('ul[data-template-id="itemKeyword"]')
                #for link in links:
                #    span = link.select_one('span.sds-comps-text.sds-comps-text-ellipsis-1.sds-comps-text-type-body1')
                #    if span:
                #        # get_text(strip=True)로 공백 제거 후 텍스트만 추출
                #        keyword = span.get_text()
                #        keywords.append(keyword)
                ul = soup.find('ul', class_='lst_related_srch _list_box')
                if ul:
                    tit_divs = ul.find_all('div', class_='tit')
                    if len(tit_divs) > 0:
                        rank = 1
                        for div in tit_divs:
                            results.append({
                                'rank': rank,
                                'keyword': div.get_text()
                            })
                            rank = rank + 1


            self.logger.info(f"Final result count: {len(results)}")
            return results
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")

    def scrape_naver_popular(self, query: str):
        base_url = 'https://search.naver.com/search.naver?where=nexearch&sm=top_hty&fbm=0&ie=utf8&query='
        results = []
        try:
            with SeleniumDriver(start_url='https://www.naver.com/').driver as driver:
                self.logger.info("Driver generated!")
                driver.get(f'{base_url}{query}')

                self.scroll_down(driver, 5)
                self.logger.info("Scroll down finished, starting crawl")

                soup = BeautifulSoup(driver.page_source, 'html.parser')

                keyword_spans = soup.select('span.fds-comps-keyword-chip-text')
                keywords = [span.get_text(strip=True) for span in keyword_spans]

                rank = 1
                for keyword in keywords:
                    results.append({
                        'rank': rank,
                        'keyword': keyword
                    })
                    rank = rank + 1

            self.logger.info(f"Final result count: {len(results)}")
            return results
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            self.logger.error(traceback.format_exc())
        finally:
            self.logger.info(f"Scraping completed. result cnt: {len(results)}")

    def scrape_naver_together(self, query: str):
        base_url = 'https://search.naver.com/search.naver?where=nexearch&sm=top_hty&fbm=0&ie=utf8&query='
        results = []
        try:
            with SeleniumDriver(start_url='https://www.naver.com/').driver as driver:
                self.logger.info("Driver generated!")
                driver.get(f'{base_url}{query}')

                self.scroll_down(driver, 5)
                self.logger.info("Scroll down finished, starting crawl")

                soup = BeautifulSoup(driver.page_source, 'html.parser')

                keywords = []
                keyword_links = soup.find_all("a", attrs={"data-template-id": "itemKeyword"})
                keywords = [link.get_text(strip=True) for link in keyword_links]
                rank = 0
                for keyword in keywords:
                    rank = rank + 1
                    results.append({
                        'rank': rank,
                        'keyword': keyword
                    })
                #for span_tag in soup.find_all('span', class_='fds-keyword-text'):
                #    rank = len(results) + 1
                #    topic_text = span_tag.get_text()
                #    results.append({
                #        'rank': rank,
                #        'keyword': topic_text
                #    })
                #links = driver.find_elements(By.CSS_SELECTOR, "div.keyword._rk_hcheck a")
                #for link in links:
                #    rank = len(results) + 1
                #    text = link.text.strip()
                #    results.append({
                #        'rank': rank,
                #        'keyword': text
                #    })
            self.logger.info(f"Final result count: {len(results)}")
            return results
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")

    def scroll_down(self, driver, nloop: int = 1):
        try:
            for _ in range(nloop):
                self.scroll_position += 700
                driver.execute_script(f"window.scrollTo(0, {self.scroll_position})")
                time.sleep(0.5)
                self.logger.info(f"Scrolled down to position: {self.scroll_position}")
        except WebDriverException as e:
            self.logger.error(f"Error during scroll: {e}")
            self.logger.error(traceback.format_exc())

