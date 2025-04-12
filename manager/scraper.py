import json
import logging
import re
import time
import traceback
from datetime import datetime, timezone, timedelta
from dateutil.relativedelta import relativedelta

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import (
    TimeoutException, WebDriverException, NoSuchWindowException
)
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from selenium_driver import SeleniumDriver

class Scraper:
    def __init__(self):
        self.logger = logging.getLogger("uvicorn")

    def scrape_naver_shop_related_tags(self, query: str):
        url = f'https://msearch.shopping.naver.com/search/all?query={query}&vertical=search'
        try:
            with SeleniumDriver(start_url=url) as selenium_context:
                driver = selenium_context.driver
                driver.implicitly_wait(5)
                self.logger.info("Driver initialized. Navigating to search page.")
                driver.get(url)
                self.scroll_down(driver, nloop=3)
                time.sleep(2)
                soup = BeautifulSoup(driver.page_source, "html.parser")
                self.logger.info(driver.page_source)

            try:
                # '연관' 텍스트를 가진 h2 태그를 찾고, 그 다음 ul 태그의 li 태그들을 찾습니다
                related_section = soup.find('h2', text='연관')
                if related_section:
                    related_ul = related_section.find_next('ul')
                    if related_ul:
                        related_items = related_ul.find_all('li')
                        result = [item.get_text(strip=True) for item in related_items]
                        print(result)
                        print("?????????????????????")
                        self.logger.info("?????????????????????")
                        self.logger.info(result)
                        return result
                return ['쇼핑 연관 검색어가 없습니다.']
            except Exception as e:
                print(f"Error parsing related tags: {e}")
                return ['쇼핑 연관 검색어 파싱 중 오류가 발생했습니다.']
            finally:
                self.logger.info(f"Final result...")
        except Exception as e:
            self.logger.error(f"Unexpected error in scrape_naver_shop_related_tags(): {e}")
            self.logger.error(traceback.format_exc())

        finally:
            # 크롤링이 길어져 응답 시간이 초과되면 504 발생 가능
            self.logger.info(f"Final result")

    def scroll_down(self, driver, nloop: int = 1):
        """
        유튜브의 검색결과 페이지에서 nloop만큼 스크롤하여
        더 많은 결과를 로드합니다.
        """
        try:
            scroll_increment = 300
            for i in range(nloop):
                driver.execute_script(f"window.scrollBy(0, {scroll_increment});")
                time.sleep(1)
                self.logger.debug(f"Scrolled down by {scroll_increment} pixels")
        except WebDriverException as e:
            self.logger.error(f"Error during scroll: {e}")
            self.logger.error(traceback.format_exc())
        finally:
            self.logger.info("scroll done!")
