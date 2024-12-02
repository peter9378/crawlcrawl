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
        # 로거 인스턴스 생성
        self.logger = logging.getLogger('uvicorn')
        self.scroll_position = 0


    def scrape_naver_related(self, query: str):
        base_url = 'https://m.search.naver.com/search.naver?query='
        results = []
        try:
            with SeleniumDriver(start_url='https://m.naver.com/').driver as driver:
                self.logger.info("Driver generated!")
                driver.get(f'{base_url}{query}&sm=mtp_hty.top&where=m')

                self.scroll_down(driver, 3)
                self.logger.info("Scroll down finished, starting crawl")

                soup = BeautifulSoup(driver.page_source, 'html.parser')

                for span_tag in soup.find_all('span', class_='fds-keyword-text'):
                    rank = len(results) + 1
                    topic_text = span_tag.get_text()
                    results.append({
                        'rank': rank,
                        'keyword': topic_text
                    })

            self.logger.info(f"Final result count: {len(results)}")
            return results
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")

    def scrape_naver_popular(self, query: str):
        base_url = 'https://m.search.naver.com/search.naver?query='
        results = []
        try:
            with SeleniumDriver(start_url='https://m.naver.com/').driver as driver:
                self.logger.info("Driver generated!")
                driver.get(f'{base_url}{query}&sm=mtp_hty.top&where=m')

                self.scroll_down(driver, 3)
                self.logger.info("Scroll down finished, starting crawl")

                soup = BeautifulSoup(driver.page_source, 'html.parser')

                for span_tag in soup.find_all('span', class_='F21ZMYiOu4F3fWJ0LxgM'):
                    rank = len(results) + 1
                    topic_text = span_tag.get_text()
                    results.append({
                        'rank': rank,
                        'keyword': topic_text
                    })
                        

            self.logger.info(f"Final result count: {len(results)}")
            return results
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            self.logger.error(traceback.format_exc())
        finally:
            self.logger.info(f"Scraping completed. result cnt: {len(results)}")

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

