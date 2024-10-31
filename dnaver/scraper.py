from selenium.webdriver import Chrome
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, WebDriverException, TimeoutException
from selenium.webdriver.common.by import By
from selenium_driver import SeleniumDriver
import traceback
from bs4 import BeautifulSoup
import json
import logging
import re
import time

#logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
#logger = logging.getLogger(__name__)

class Scraper:
    def __init__(self):
        self.selenium_driver = SeleniumDriver(start_url='https://www.naver.com/')
        if not self.selenium_driver.health_check():
            print("Driver setup failed.")
            self.selenium_driver = None
        self.driver = self.selenium_driver.driver
        self.scroll_position = 0
        self.logger = logging.getLogger('uvicorn')

    def crawl_naverprice(self, query: str, limit: int = 30):
        driver = self.driver
        base_url = 'https://search.shopping.naver.com/search/all?query='
        driver.get(f'{base_url}{query}')
        print(driver.page_source)
        results = []
        while len(results) < limit:
            try:
                self.scroll_down(driver, 2)
                print("get elements...")
                element = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'item')]"))
                )
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                print(f"soup: {soup}")
                postfixs = soup.select('#dismissible #thumbnail')
                
                for postfix in postfixs:
                    href = postfix.get('href')
                    if not href:
                        continue
                    url = f"https://www.youtube.com{href}"
                    print(url)

                    video_id = url.split('/')[-1] if 'shorts' in url else url.split('v=')[1]
                    if 'watch' in url:
                        # 생성 날짜 가져오는 부분
                        # TODO: 캐시해서 성능 향상시키기
                        (title, view_count, published_date) = self.get_video_detail(url)
                        result = {
                            "VideoID": video_id,
                            "title": title,
                            "url": url,
                            "videoCount": view_count,
                            "publishedDate": published_date,
                            "videoType": "video"
                        }
                    elif 'shorts' in url:
                        (title, view_count, published_date) = self.get_shorts_detail(url)
                        result = {
                            "VideoID": video_id,
                            "title": title,
                            "url": url,
                            "videoCount": view_count,
                            "publishedDate": published_date,
                            "videoType": "shorts"
                        }

                    results.append(result)
            except TimeoutException:
                self.logger.error('TimeoutException during scrolling or element loading.')
        return results

    def scrape_youtube(self, query: str, limit: int = 3):
        driver = self.driver
        base_url = 'https://www.youtube.com/results?search_query='
        driver.get(f'{base_url}{query}')
        results = []
        urls = set()

        while len(urls) < limit * 1.3:
            try:
                self.scroll_down(driver, 3)
                WebDriverWait(driver, 3).until(EC.presence_of_all_elements_located((By.ID, 'thumbnail')))
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                dismissible_items = soup.find_all(id='dismissible')
                urls.update([thumbnail.get_attribute('href') for thumbnail in thumbnails if thumbnail.get_attribute('href')])
            except TimeoutException:
                self.logger.error('TimeoutException during scrolling or element loading.')
        
        results = []
        for url in list(urls)[:limit]:
            try:
                if 'shorts' in url:
                    result = self.get_shorts_detail(url)
                elif 'watcaasdfasdasdsh' in url:
                    result = self.get_video_detail(url)
                else:
                    continue
                results.append(result)
            except TimeoutException:
                self.logger.error(f"TimeoutException for URL: {url}")
                continue
            except Exception as e:
                self.logger.error(f"Error: {e} at traceback: {traceback.format_exc()}")
                continue
        return results

    def get_video_detail(self, url: str):
        driver = self.driver
        driver.get(url)
        WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.ID, 'microformat')))
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        video_id = url.split('v=')[1]
        
        try:
            title_element = soup.find('yt-formatted-string', class_='style-scope ytd-video-description-header-renderer')
            title = title_element.text.strip() if title_element else None

            view_count_text = soup.find('span', class_='view-count style-scope ytd-video-view-count-renderer').text
            view_count_number = re.sub(r'[^0-9]', '', view_count_text)

            published_date_text = soup.find(id='info-strings').text.strip()
            published_date_match = re.search(r'(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.', published_date_text)
            if published_date_match:
                year, month, day = published_date_match.groups()
                published_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"

            return (title, view_count_number, published_date)
        except Exception as e:
            print(f"Error extracting video details: {e} at traceback: {traceback.format_exc()}")
            result = {
                "VideoID": video_id,
                "viewCount": "",
                "publishDate": "",
                "Error": "ExtractionError"
            }
        return result

    def get_shorts_detail(self, url: str):
        driver = self.driver
        driver.get(url)
        WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.ID, 'menu-button')))
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        video_id = url.split('shorts/')[1]
        
        try:
            title_element = soup.find('yt-formatted-string', class_='style-scope ytd-video-description-header-renderer')
            title = title_element.text.strip() if title_element else None

            factoids = soup.find_all('factoid-renderer', class_='YtwFactoidRendererHost')

            view_count = None
            published_date = None

            for factoid in factoids:
                div = factoid.find('div', class_='YtwFactoidRendererFactoid')
                aria_label = div.get('aria-label', '')
                if '조회수' in aria_label:
                    # 조회수 추출
                    view_count = aria_label.replace('조회수', '').replace('회', '').replace(',', '').strip()
                elif '좋아요' in aria_label:
                    # 좋아요 수 추출 (필요하다면)
                    likes = aria_label.replace('좋아요', '').replace('개', '').strip()
                else:
                    # 날짜 추출
                    published_date = aria_label.strip()
            return (title, view_count, published_date)

        except Exception as e:
            self.logger.error(f"Error extracting shorts details: {e} at traceback: {traceback.format_exc()}")
            result = {
                "VideoID": video_id,
                "viewCount": "",
                "publishDate": "",
                "Error": "ExtractionError"
            }
        return result

    def scroll_down(self, driver, nloop: int = 1):
        for _ in range(nloop):
            self.scroll_position += 700
            driver.execute_script(f"window.scrollTo(0, {self.scroll_position})")
            time.sleep(0.5)  # Optional: Add a small delay to allow content to load

if __name__ == "__main__":
    scraper = Scraper()
    result = scraper.scrape_youtube('검은콩', limit=3)
    with open('result.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=4)
