from bs4 import BeautifulSoup
import json
import logging
import re
import time
import random
import requests
from datetime import datetime, timedelta
import traceback
import urllib.parse
import math
from selenium_driver import SeleniumDriver

class Scraper:
    def __init__(self):
        # Logger instance
        self.logger = logging.getLogger('uvicorn')
        # 랜덤 User-Agent 생성
        self.headers = {
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Referer': 'https://www.naver.com/',
            'Connection': 'keep-alive',
            'Cache-Control': 'max-age=0',
            'sec-ch-ua-mobile': '?0',
        }
        # 쿠키 저장용 세션 객체
        self.session = requests.Session()
        # 페이지 번호 초기화
        self.page = 1
        self.update_user_agent()
        
    def update_user_agent(self):
        """랜덤 User-Agent 생성 및 업데이트"""
        os_list = [
            ('Windows NT 10.0', 'Win64; x64'),
            ('Windows NT 11.0', 'Win64; x64'),
            ('Windows NT 6.1', 'Win64; x64'),  # Windows 7
            ('Windows NT 6.3', 'Win64; x64'),  # Windows 8.1
            ('Macintosh', 'Intel Mac OS X 10_15_7'),
            ('Macintosh', 'Intel Mac OS X 11_6_0'),
            ('Macintosh', 'Intel Mac OS X 12_0_1'),
            ('Macintosh', 'Intel Mac OS X 13_2_1'),
            ('Macintosh', 'Apple Silicon Mac OS X 14_1_0'),
            ('X11', 'Linux x86_64'),
            ('X11', 'Ubuntu; Linux x86_64'),
            ('X11', 'Fedora; Linux x86_64'),
            ('X11', 'Debian; Linux x86_64')
        ]
        
        # 브라우저 종류와 버전
        browsers = [
            {
                'name': 'Chrome',
                'versions': ['118.0.0.0', '119.0.0.0', '120.0.0.0', '121.0.0.0', '122.0.0.0', '123.0.0.0', '124.0.0.0', '125.0.0.0', '126.0.0.0', '127.0.0.0', '128.0.0.0'],
                'webkit_versions': ['537.36', '605.1.15', '605.1.33', '605.1.50'],
                'sec_ch_ua': lambda v: f'"Chromium";v="{v.split(".")[0]}", "Google Chrome";v="{v.split(".")[0]}", "Not?A_Brand";v="24"'
            },
            {
                'name': 'Firefox',
                'versions': ['110.0', '111.0', '112.0', '113.0', '114.0', '115.0', '116.0', '117.0', '118.0', '119.0', '120.0', '121.0', '122.0', '123.0'],
                'gecko_versions': ['20100101', '20100102', '20100103', '20100104', '20100105', '20100106'],
                'sec_ch_ua': lambda v: f'"Firefox";v="{v.split(".")[0]}", "Not?A_Brand";v="8"'
            },
            {
                'name': 'Safari',
                'versions': ['15.4', '15.5', '16.0', '16.1', '16.2', '16.3', '16.4', '17.0', '17.1', '17.2', '17.3'],
                'webkit_versions': ['605.1.15', '605.1.33', '605.1.50', '606.1.15', '606.1.23', '606.1.49'],
                'sec_ch_ua': lambda v: f'"Safari";v="{v.split(".")[0]}", "Apple Safari";v="{v}", "Not?A_Brand";v="8"'
            },
            {
                'name': 'Edge',
                'versions': ['110.0.1587.41', '111.0.1661.54', '112.0.1722.39', '113.0.1774.42', '114.0.1823.51', '115.0.1901.183', '116.0.1938.62', '117.0.2045.60', '118.0.2088.57', '119.0.2151.58', '120.0.2210.77', '121.0.2277.110', '122.0.2365.75'],
                'webkit_versions': ['537.36', '605.1.12', '605.1.31', '605.1.54', '606.1.17', '606.1.28', '606.1.44'],
                'sec_ch_ua': lambda v: f'"Edg";v="{v.split(".")[0]}", "Microsoft Edge";v="{v.split(".")[0]}", "Chromium";v="{v.split(".")[0]}"'
            }
        ]
        
        # 모바일 디바이스 정보
        mobile_devices = [
            ('iPhone', 'CPU iPhone OS 16_0 like Mac OS X'),
            ('iPhone', 'CPU iPhone OS 16_1 like Mac OS X'),
            ('iPhone', 'CPU iPhone OS 16_2 like Mac OS X'),
            ('iPhone', 'CPU iPhone OS 16_3 like Mac OS X'),
            ('iPad', 'CPU OS 16_0 like Mac OS X'),
            ('iPad', 'CPU OS 16_1 like Mac OS X'),
            ('Linux', 'Android 12; SM-G998B'),
            ('Linux', 'Android 13; SM-S908B'),
            ('Linux', 'Android 14; Pixel 7'),
            ('Linux', 'Android 12; Pixel 6'),
            ('Linux', 'Android 13; M2102J20SG')
        ]
        
        # 데스크톱 또는 모바일 랜덤 선택 (70% 확률로 데스크톱)
        is_mobile = random.random() > 0.7
        
        if is_mobile:
            # 모바일 User-Agent 생성
            device, os_version = random.choice(mobile_devices)
            browser = random.choice(browsers)
            browser_version = random.choice(browser['versions'])
            
            if 'iPhone' in device or 'iPad' in device:
                webkit_version = random.choice(['605.1.15', '605.1.33', '605.1.50'])
                mobile_safari_version = random.choice(['15.0', '15.1', '15.2', '15.3', '16.0', '16.1', '16.2', '16.3'])
                user_agent = f'Mozilla/5.0 ({device}; {os_version}) AppleWebKit/{webkit_version} (KHTML, like Gecko) Version/{mobile_safari_version} Mobile/15E148 Safari/{webkit_version}'
                platform = 'iOS'
            else:
                # Android
                chrome_version = random.choice(['119.0.6045.163', '120.0.6099.144', '121.0.6167.143', '122.0.6261.119', '123.0.6312.87'])
                webkit_version = '537.36'
                user_agent = f'Mozilla/5.0 ({os_version}) AppleWebKit/{webkit_version} (KHTML, like Gecko) Chrome/{chrome_version} Mobile Safari/{webkit_version}'
                platform = 'Android'
                
            self.headers['sec-ch-ua-mobile'] = '?1'
            self.headers['sec-ch-ua-platform'] = f'"{platform}"'
        else:
            # 데스크톱 User-Agent 생성
            selected_os, os_version = random.choice(os_list)
            browser = random.choice(browsers)
            browser_version = random.choice(browser['versions'])
            
            if browser['name'] == 'Firefox':
                gecko_version = random.choice(browser['gecko_versions'])
                user_agent = f'Mozilla/5.0 ({selected_os}; {os_version}; rv:{browser_version}) Gecko/{gecko_version} Firefox/{browser_version}'
            elif browser['name'] == 'Safari':
                webkit_version = random.choice(browser['webkit_versions'])
                user_agent = f'Mozilla/5.0 ({selected_os}; {os_version}) AppleWebKit/{webkit_version} (KHTML, like Gecko) Version/{browser_version} Safari/{webkit_version}'
            else:  # Chrome, Edge
                webkit_version = random.choice(browser['webkit_versions'])
                user_agent = f'Mozilla/5.0 ({selected_os}; {os_version}) AppleWebKit/{webkit_version} (KHTML, like Gecko) Chrome/{browser_version} Safari/{webkit_version}'
                if browser['name'] == 'Edge':
                    user_agent = user_agent.replace('Chrome', 'Edg')
            
            self.headers['sec-ch-ua-mobile'] = '?0'
            self.headers['sec-ch-ua-platform'] = f'"{selected_os.split()[0]}"'
        
        # 헤더 업데이트
        self.headers['User-Agent'] = user_agent
        if browser and 'sec_ch_ua' in browser:
            self.headers['sec-ch-ua'] = browser['sec_ch_ua'](browser_version)
        
        self.session.headers.update(self.headers)
        self.logger.info(f"Updated User-Agent: {user_agent}")

    def fetch_page(self, url, max_retries=3, base_delay=0.1):
        """페이지 내용을 가져오는 함수"""
        for attempt in range(max_retries):
            try:
                # 요청마다 User-Agent 업데이트
                if attempt > 0:  # 재시도 시에만 User-Agent 변경
                    self.update_user_agent()
                
                # 요청 간 랜덤 지연 시간 추가 (0.05~0.8초)
                delay = base_delay + random.uniform(0.1, 0.7)
                time.sleep(delay)
                
                self.logger.info(f"Request attempt {attempt+1} with delay {delay:.2f}s")
                response = self.session.get(url)
                response.raise_for_status()  # 에러 발생 시 예외 발생
                
                # 성공적으로 응답 받았을 때 쿠키 저장
                self.session.cookies.update(response.cookies)
                
                return response.text
            except requests.RequestException as e:
                self.logger.error(f"Error fetching page (attempt {attempt+1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    return None
            # 재시도 전 지수 백오프 적용
            time.sleep((2 ** attempt) + random.uniform(0, 1))
        return None

    def fetch_page_with_scroll(self, url: str, limit: int) -> str:
        """Selenium으로 페이지를 열고 limit에 비례해 스크롤한 뒤 HTML을 반환한다."""
        # limit 30당 1번씩, 최소 1번 스크롤
        scroll_times = max(1, math.ceil(limit / 30))
        driver_wrapper = None
        try:
            driver_wrapper = SeleniumDriver(start_url=url)
            driver = driver_wrapper.driver
            if not driver_wrapper.health_check():
                return None
            # 초기 로딩 대기
            time.sleep(0.1)
            # 스크롤 수행: 700px씩 scroll_times회
            for _ in range(scroll_times):
                driver.execute_script("window.scrollBy(0, 700);")
                time.sleep(0.2)
            # 렌더 안정화 대기
            time.sleep(0.1)
            return driver.page_source
        except Exception as e:
            self.logger.error(f"Selenium fetch failed: {e}")
            return None
        finally:
            if driver_wrapper:
                driver_wrapper.remove_driver()
    def _normalize_highlight_text(self, element):
        """span 내부 텍스트를 mark 위치와 상관없이 자연스럽게 결합하여 반환한다."""
        text = element.get_text(separator='', strip=False)
        # 공백을 하나로 축약하고 양끝 공백 제거
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _extract_main_pack_span_texts(self, soup, max_needed):
        """main_pack 하위 목표 span 텍스트를 최대 max_needed개까지 추출"""
        required_classes = [
            'sds-comps-text',
            'sds-comps-text-ellipsis',
            'sds-comps-text-ellipsis-1',
            'sds-comps-text-type-headline1',
            'sds-comps-text-weight-sm',
        ]

        def has_required_classes(class_attr):
            if not class_attr:
                return False
            classes = class_attr.split() if isinstance(class_attr, str) else list(class_attr)
            return all(cls in classes for cls in required_classes)

        containers = []
        main_by_id = soup.find('div', id='main_pack')
        if main_by_id:
            containers.append(main_by_id)
        containers.extend(soup.find_all('div', class_='main_pack'))

        texts = []
        seen = set()
        for container in containers:
            spans = container.find_all('span', class_=has_required_classes)
            for span in spans:
                value = self._normalize_highlight_text(span)
                if not value:
                    continue
                if value in seen:
                    continue
                seen.add(value)
                texts.append(value)
                if len(texts) >= max_needed:
                    return texts
        return texts

    def _extract_main_pack_anchor_texts(self, soup, max_needed):
        """main_pack 하위 a.title_link 텍스트를 최대 max_needed개까지 추출 (카페용)"""
        containers = []
        main_by_id = soup.find('div', id='main_pack')
        if main_by_id:
            containers.append(main_by_id)
        containers.extend(soup.find_all('div', class_='main_pack'))

        texts = []
        seen = set()
        for container in containers:
            anchors = container.find_all('a', class_='title_link')
            for a in anchors:
                value = self._normalize_highlight_text(a)
                if not value:
                    continue
                if value in seen:
                    continue
                seen.add(value)
                texts.append(value)
                if len(texts) >= max_needed:
                    return texts
        return texts

    def scrape_naver_blog(self, query: str, limit: int = 30):
        results = {
            'keyword': query,
            'result': []
        }
        self.page = 1  # 페이지 초기화
        try:
            self.logger.info("Starting blog search")
            encoded_query = urllib.parse.quote(query)
            
            while len(results['result']) < limit:
                url = f'https://search.naver.com/search.naver?ssc=tab.blog.all&sm=tab_jum&query={encoded_query}&start={(self.page-1)*10+1}'
                self.logger.info(f"Fetching page {self.page} from URL: {url}")
                
                # 동적 요소 로딩 대응: 스크롤 포함 페치 시도 후 실패 시 정적 요청으로 폴백
                html_content = self.fetch_page_with_scroll(url, limit)
                if not html_content:
                    html_content = self.fetch_page(url)
                if not html_content:
                    self.logger.error("Failed to fetch page")
                    break
                
                soup = BeautifulSoup(html_content, 'html.parser')
                remaining = limit - len(results['result'])
                span_texts = self._extract_main_pack_span_texts(soup, remaining)
                if not span_texts:
                    self.logger.info("No more results found")
                    break
                for value in span_texts:
                    rank = len(results['result']) + 1
                    results['result'].append({
                        'rank': rank,
                        'title': value,
                        'description': ''
                    })
                
                # Move to next page only if the limit has not been reached
                if len(results['result']) < limit:
                    self.page += 1
                
            self.logger.info(f"Final result count: {len(results['result'])}")
            return results
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            self.logger.error(traceback.format_exc())
            return results
        finally:
            self.logger.info(f"Scraping completed. result cnt: {len(results['result'])}")

    def scrape_naver_cafe(self, query: str, limit: int = 30):
        results = {
            'keyword': query,
            'result': []
        }
        self.page = 1  # 페이지 초기화
        try:
            self.logger.info("Starting cafe search")
            encoded_query = urllib.parse.quote(query)
            
            while len(results['result']) < limit:
                url = f'https://search.naver.com/search.naver?ssc=tab.cafe.all&sm=tab_jum&query={encoded_query}&start={(self.page-1)*10+1}'
                self.logger.info(f"Fetching page {self.page} from URL: {url}")
                
                # 동적 요소 로딩 대응: 스크롤 포함 페치 시도 후 실패 시 정적 요청으로 폴백
                html_content = self.fetch_page_with_scroll(url, limit)
                if not html_content:
                    html_content = self.fetch_page(url)
                if not html_content:
                    self.logger.error("Failed to fetch page")
                    break
                
                soup = BeautifulSoup(html_content, 'html.parser')
                remaining = limit - len(results['result'])
                anchor_texts = self._extract_main_pack_anchor_texts(soup, remaining)
                if not anchor_texts:
                    self.logger.info("No more results found")
                    break
                for value in anchor_texts:
                    rank = len(results['result']) + 1
                    results['result'].append({
                        'rank': rank,
                        'title': value,
                        'description': ''
                    })
                
                # Move to next page only if the limit has not been reached
                if len(results['result']) < limit:
                    self.page += 1
                
            self.logger.info(f"Final result count: {len(results['result'])}")
            return results
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            self.logger.error(traceback.format_exc())
            return results
        finally:
            self.logger.info(f"Scraping completed. result cnt: {len(results['result'])}")

