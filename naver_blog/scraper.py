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

    def scrape_naver_blog(self, query: str, limit: int = 30):
        base_url = 'https://search.naver.com/search.naver?ssc=tab.blog.all&sm=tab_jum&query='
        results = []
        try:
            with SeleniumDriver(start_url='https://www.naver.com/').driver as driver:
                self.logger.info("Driver generated!")
                driver.get(f'{base_url}{query}')

                self.scroll_down(driver, 1)
                self.logger.info("Scroll down finished, starting crawl")

                while len(results) < limit:
                    data = BeautifulSoup(driver.page_source, 'html.parser')

                    title_links = data.find_all('a', class_='title_link')
                    description_links = data.find_all('a', class_='dsc_link')

                    for title_link, description_link in zip(title_links, description_links):
                        rank = len(results) + 1
                        title = title_link.get_text(strip=True)
                        description = description_link.get_text(strip=True)
                        results.append({
                            'rank': rank,
                            'title': title,
                            'description': description
                        })

                        # Stop if we reach the limit
                        if len(results) >= limit:
                            self.logger.info(f"Generated result count: {len(results)}")
                            break

                    # Scroll down only if the limit has not been reached
                    if len(results) < limit:
                        self.scroll_down(driver, 1)

            self.logger.info(f"Final result count: {len(results)}")
            return results
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            self.logger.error(traceback.format_exc())
        finally:
            self.logger.info(f"Scraping completed. result cnt: {len(results)}")

    def scrape_naver_cafe(self, query: str, limit: int = 30):
        base_url = 'https://search.naver.com/search.naver?ssc=tab.cafe.all&sm=tab_jum&query='
        results = []
        try:
            with SeleniumDriver(start_url='https://www.naver.com/').driver as driver:
                self.logger.info("Driver generated!")
                driver.get(f'{base_url}{query}')

                self.scroll_down(driver, 1)
                self.logger.info("Scroll down finished, starting crawl")

                while len(results) < limit:
                    data = BeautifulSoup(driver.page_source, 'html.parser')

                    title_links = data.find_all('a', class_='title_link')
                    description_links = data.find_all('a', class_='dsc_link')

                    for title_link, description_link in zip(title_links, description_links):
                        rank = len(results) + 1
                        title = title_link.get_text(strip=True)
                        description = description_link.get_text(strip=True)
                        results.append({
                            'rank': rank,
                            'title': title,
                            'description': description
                        })

                        # Stop if we reach the limit
                        if len(results) >= limit:
                            self.logger.info(f"Generated result count: {len(results)}")
                            break

                    # Scroll down only if the limit has not been reached
                    if len(results) < limit:
                        self.scroll_down(driver, 1)

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

