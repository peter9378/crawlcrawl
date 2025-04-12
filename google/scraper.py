from selenium import webdriver
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
        # Initialize any necessary variables or objects here
        self.logger = logging.getLogger('uvicorn')
        self.scroll_position = 0

    def scrape_google(self, query: str, limit: int = 30):
        url = f'https://www.google.com/'
        results = []
        
        try:
            with SeleniumDriver(start_url=url).driver as driver:
                base_url = 'https://www.google.com/search?q='
                driver.get(f'{base_url}{query}')
                self.scroll_down(driver, 1)
                print("start crawling google")

                while len(results) < limit:
                    WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.CLASS_NAME, 'AJLUJb')))
                    soup = BeautifulSoup(driver.page_source, 'html.parser')
                    span_elements = soup.find_all('span', class_='dg6jd')
                    print("loop start")

                    new_results = [
                        {"searchType": "pc", "relatedKeyword": element.get_text()}
                        for element in span_elements
                    ]
                    results.extend(new_results)

                    if len(results) < limit:
                        self.scroll_down(driver, 1)

        except TimeoutException:
            self.logger.error("Timeout while waiting for elements.")
        except WebDriverException:
            self.logger.error("WebDriverException occurred.")
            self.logger.error(traceback.format_exc())
        except Exception as e:
            self.logger.error(f'Unexpected error occurred: {str(e)}')
            self.logger.error(traceback.format_exc())

        finally:
            self.logger.info("Scraping completed. Total results: {}".format(len(results)))

        return results


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

if __name__ == '__main__':
    # Test your scraper here
    scraper = Scraper()
    result, succesed = scraper.scrape_google('바시티 자켓 바지')
    print(result)

