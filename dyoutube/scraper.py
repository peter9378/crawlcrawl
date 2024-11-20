from selenium.webdriver import Chrome, ChromeOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium_driver import SeleniumDriver
from bs4 import BeautifulSoup
import json
import logging
import re
import time
from datetime import datetime, timedelta

class Scraper:
    def __init__(self):
        self.selenium_driver = SeleniumDriver(start_url='https://www.youtube.com/')
        if not self.selenium_driver.health_check():
            print("Driver setup failed.")
            self.selenium_driver = None
        self.driver = self.selenium_driver.driver
        self.scroll_position = 0
        self.logger = logging.getLogger('uvicorn')

    def get_list(self, query: str, limit: int = 30):
        driver = self.driver
        base_url = 'https://www.youtube.com/results?search_query='
        driver.get(f'{base_url}{query}')
        results = []
        while len(results) < limit:
            try:
                self.scroll_down(driver, int(limit/10) + 1)
                WebDriverWait(driver, 3).until(EC.presence_of_all_elements_located((By.ID, 'thumbnail')))
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                postfixs = soup.select('#dismissible #thumbnail')

                for postfix in postfixs:
                    href = postfix.get('href')
                    if not href:
                        continue
                    url = f"https://www.youtube.com{href}"
                    video_id = url.split('/')[-1] if 'shorts' in url else url.split('v=')[1]
                    if 'watch' in url:
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
                    else:
                        continue

                    results.append(result)
            except TimeoutException:
                self.logger.error('TimeoutException during scrolling or element loading.')
        driver.quit()  # Ensure driver quits to prevent zombie processes
        print(f"result cnt: {len(results)}")
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
            published_date = self.convert_date(published_date_text)

            return (title, view_count_number, published_date)
        except Exception as e:
            self.logger.error(f"Error extracting video details: {e}")
            return (None, None, None)

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
                if 'views' in aria_label:
                    view_count = aria_label.replace(' views', '').replace(',', '').strip()
                else:
                    published_date = self.convert_date(aria_label)
            return (title, view_count, published_date)

        except Exception as e:
            self.logger.error(f"Error extracting shorts details: {e}")
            return (None, None, None)

    def scroll_down(self, driver, nloop: int = 1):
        for _ in range(nloop):
            self.scroll_position += 700
            driver.execute_script(f"window.scrollTo(0, {self.scroll_position})")
            time.sleep(0.5)

    def convert_date(self, input_str: str):
        try:
            date_pattern = r'(?:Streamed live on |Premiered )?(\w{3}) (\d{1,2}), (\d{4})'
            hours_ago_pattern = r'Streamed live (\d+) hours ago'
            korean_date_pattern = r'(\d{4})\. (\d{1,2})\. (\d{1,2})\.'
            premiered_korean_pattern = r'최초 공개: (\d{4})\. (\d{1,2})\. (\d{1,2})\.'
            minutes_ago_pattern = r'(\d+)분 전 최초 공개'

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
            return f"Error: {e}"

if __name__ == "__main__":
    scraper = Scraper()
    result = scraper.get_list('검은콩', limit=10)
    with open('result.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=4)

