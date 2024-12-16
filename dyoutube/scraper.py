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
import threading
import psutil

# 전역 Lock 정의
_lock = threading.Lock()

class Scraper:
    def __init__(self):
        # 로거 인스턴스 생성
        self.logger = logging.getLogger('uvicorn')
        self.scroll_position = 0
        self.driver = None  # 필요 시 드라이버 인스턴스 보관용

    def get_list(self, query: str, limit: int = 30):
        # 전역 Lock을 사용하여 한 번에 하나의 요청만 처리
        with _lock:
            base_url = 'https://www.youtube.com/results?search_query='
            results = []
            try:
                with SeleniumDriver(start_url='https://www.youtube.com/').driver as driver:
                    self.driver = driver
                    self.logger.info("Driver generated!")
                    driver.get(f'{base_url}{query}')

                    self.scroll_down(driver, 1)
                    self.logger.info("Scroll down finished, starting crawl")

                    while len(results) < limit:
                        # Wait for elements to load
                        WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.ID, 'thumbnail')))
                        soup = BeautifulSoup(driver.page_source, 'html.parser')
                        postfixs = soup.select('#dismissible #thumbnail')
                        self.logger.info("Elements selected for parsing.")

                        for postfix in postfixs:
                            href = postfix.get('href')
                            if not href:
                                continue

                            url = f"https://www.youtube.com{href}"
                            video_id = url.split('/')[-1] if 'shorts' in url else url.split('v=')[1]

                            if 'watch' in url:
                                title, view_count, published_date = self.get_video_detail(driver, url)
                                result = {
                                    "VideoID": video_id,
                                    "title": title,
                                    "url": url,
                                    "videoCount": view_count,
                                    "publishedDate": published_date,
                                    "videoType": "video"
                                }
                            elif 'shorts' in url:
                                title, view_count, published_date = self.get_shorts_detail(driver, url)
                                result = {
                                    "VideoID": video_id,
                                    "title": title,
                                    "url": url,
                                    "videoCount": view_count,
                                    "publishedDate": published_date,
                                    "videoType": "shorts"
                                }
                            else:
                                continue

                            results.append(result)
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
                self.quit_driver()  # 드라이버 종료

    def get_video_detail(self, driver, url: str):
        try:
            self.logger.info(f"Fetching video details for URL: {url}")
            driver.get(url)
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, 'microformat')))
            soup = BeautifulSoup(driver.page_source, 'html.parser')

            title_element = soup.find('yt-formatted-string', class_='style-scope ytd-video-description-header-renderer')
            title = title_element.text.strip() if title_element else None

            view_count_text = soup.find('span', class_='view-count style-scope ytd-video-view-count-renderer').text
            view_count_number = re.sub(r'[^0-9]', '', view_count_text)

            published_date_text = soup.find(id='info-strings').text.strip()
            published_date = self.convert_date(published_date_text)

            return title, view_count_number, published_date
        except TimeoutException:
            self.logger.warning(f"TimeoutException while fetching video details for URL: {url}")
            return None, None, None
        except Exception as e:
            self.logger.error(f"Error extracting video details: {e}")
            self.logger.error(traceback.format_exc())
            return None, None, None

    def get_shorts_detail(self, driver, url: str):
        try:
            self.logger.info(f"Fetching shorts details for URL: {url}")
            driver.get(url)
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, 'menu-button')))
            soup = BeautifulSoup(driver.page_source, 'html.parser')

            title_element = soup.find('yt-formatted-string', class_='style-scope ytd-video-description-header-renderer')
            title = title_element.text.strip() if title_element else None

            factoids = soup.find_all('factoid-renderer', class_='YtwFactoidRendererHost')

            view_count = None
            published_date = None

            for factoid in factoids:
                div = factoid.find('div', class_='YtwFactoidRendererFactoid')
                aria_label = div.get('aria-label', '')
                if 'views' in aria_label:
                    view_count = aria_label.replace(' views', '').replace(',', '').strip()
                else:
                    published_date = self.convert_date(aria_label)

            return title, view_count, published_date
        except TimeoutException:
            self.logger.warning(f"TimeoutException while fetching shorts details for URL: {url}")
            return None, None, None
        except Exception as e:
            self.logger.error(f"Error extracting shorts details: {e}")
            self.logger.error(traceback.format_exc())
            return None, None, None

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

    def convert_date(self, input_str: str):
        try:
            date_pattern = r'(?:Streamed live on |Premiered )?(\w{3}) (\d{1,2}), (\d{4})'
            hours_ago_pattern = r'Streamed live (\d+) hours ago'
            korean_date_pattern = r'(\d{4})\. (\d{1,2})\. (\d{1,2})\.'
            premiered_korean_pattern = r'\u최초 공개: (\d{4})\. (\d{1,2})\. (\d{1,2})\.'
            minutes_ago_pattern = r'(\d+)\u분 전 최초 공개'

            match = re.search(date_pattern, input_str)
            if match:
                month_str, day, year = match.groups()
                date_obj = datetime.strptime(f'{month_str} {day} {year}', '%b %d %Y')
                return date_obj.strftime('%Y-%m-%d')

            match = re.search(hours_ago_pattern, input_str)
            if match:
                hours_ago = int(match.group(1))
                date_obj = datetime.now() - timedelta(hours=hours_ago)
                return date_obj.strftime('%Y-%m-%d')

            match = re.search(korean_date_pattern, input_str)
            if match:
                year, month, day = match.groups()
                date_obj = datetime.strptime(f'{year}-{month}-{day}', '%Y-%m-%d')
                return date_obj.strftime('%Y-%m-%d')

            match = re.search(premiered_korean_pattern, input_str)
            if match:
                year, month, day = match.groups()
                date_obj = datetime.strptime(f'{year}-{month}-{day}', '%Y-%m-%d')
                return date_obj.strftime('%Y-%m-%d')

            match = re.search(minutes_ago_pattern, input_str)
            if match:
                minutes_ago = int(match.group(1))
                date_obj = datetime.now() - timedelta(minutes=minutes_ago)
                return date_obj.strftime('%Y-%m-%d')

            return "9999-09-09"
        except ValueError as e:
            self.logger.error(f"Error converting date: {e}")
            self.logger.error(traceback.format_exc())
            return f"Error: {e}"

    def quit_driver(self):
        try:
            if self.driver:
                self.driver.quit()
                self.logger.info("Driver successfully quit.")
            self.kill_zombie_processes()
        except Exception as e:
            self.logger.error(f"Error quitting driver: {e}")
            self.logger.error(traceback.format_exc())

    def kill_zombie_processes(self):
        try:
            for proc in psutil.process_iter():
                if proc.name() in ["chrome", "chromedriver"]:
                    self.logger.info(f"Terminating process: {proc.name()} (PID: {proc.pid})")
                    proc.terminate()  # 종료 시도
                    proc.wait(timeout=3)  # 종료 대기
        except psutil.NoSuchProcess:
            pass
        except psutil.TimeoutExpired:
            self.logger.warning("Timeout while waiting for process termination.")
        except Exception as e:
            self.logger.error(f"Error killing zombie processes: {e}")
            self.logger.error(traceback.format_exc())

