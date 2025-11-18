import requests
from bs4 import BeautifulSoup
import logging
import traceback
import time
import random
from urllib.parse import quote

# 개선된 셀레니움 드라이버(사용 환경에 맞춰 구현)
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
        self.logger.info(f"Fetching URL: {url}")
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

    def scrape_naver_related(self, query: str):
        base_url = f'https://search.naver.com/search.naver?where=nexearch&sm=top_hty&fbm=0&ie=utf8&query={quote(query)}'
        results = {
            'keyword': query,
            'result': []
        }
        try:
            self.logger.info("Fetching page content")
            html_content = self.fetch_page(base_url)
            
            if not html_content:
                self.logger.error("Failed to fetch page content")
                return results
                
            soup = BeautifulSoup(html_content, 'html.parser')
            self.logger.info("Page content parsed with BeautifulSoup")

            ul = soup.find('ul', class_='lst_related_srch _list_box')
            if ul:
                tit_divs = ul.find_all('div', class_='tit')
                if len(tit_divs) > 0:
                    rank = 1
                    for div in tit_divs:
                        results['result'].append({
                            'rank': rank,
                            'keyword': div.get_text()
                        })
                        rank = rank + 1
            else:
                self.logger.warn(f"{query}에 해당하는 연관검색어가 없습니다.")

            self.logger.info(f"Final result count: {len(results['result'])}")
            return results
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            self.logger.error(traceback.format_exc())
            return results

    def scrape_naver_popular(self, query: str):
        base_url = f'https://search.naver.com/search.naver?where=nexearch&sm=top_hty&fbm=0&ie=utf8&query={quote(query)}'
        results = {
            'keyword': query,
            'result': []
        }
        try:
            self.logger.info("Fetching page content")
            html_content = self.fetch_page(base_url)
            
            if not html_content:
                self.logger.error("Failed to fetch page content")
                return results
                
            soup = BeautifulSoup(html_content, 'html.parser')
            self.logger.info("Page content parsed with BeautifulSoup")

            keyword_spans = soup.select('span.fds-comps-keyword-chip-text')
            keywords = [span.get_text(strip=True) for span in keyword_spans]

            rank = 1
            for keyword in keywords:
                results['result'].append({
                    'rank': rank,
                    'keyword': keyword
                })
                rank = rank + 1

            self.logger.info(f"Final result count: {len(results['result'])}")
            return results
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            self.logger.error(traceback.format_exc())
        finally:
            self.logger.info(f"Scraping completed. result cnt: {len(results['result'])}")
            return results

    def scrape_naver_together(self, query: str):
        base_url = f'https://search.naver.com/search.naver?where=nexearch&sm=top_hty&fbm=0&ie=utf8&query={quote(query)}'
        results = {
            'keyword': query,
            'result': []
        }
        
        try:
            self.logger.info(f"Fetching URL with Selenium: {base_url}")
            
            # 브라우저/드라이버 실행
            with SeleniumDriver(start_url=base_url) as selenium_context:
                driver = selenium_context.driver
                
                # 암묵적 대기(최대 5초)
                driver.implicitly_wait(5)
                
                self.logger.info("Driver initialized. Page loaded.")
                
                # 페이지가 완전히 로드될 때까지 대기
                time.sleep(2)
                
                # 현재 페이지 정보 로깅
                self.logger.info(f"Current page title: {driver.title}")
                self.logger.info(f"Current URL: {driver.current_url}")
                
                # 스크롤을 통해 동적 콘텐츠 로드
                self.logger.info("Start scrolling...")
                selenium_context.scroll_down(nloop=5)  # 5번 스크롤
                time.sleep(2)  # 페이지 로딩이 완전히 끝날 때까지 대기
                
                # 페이지 소스 가져오기
                html_content = driver.page_source
                soup = BeautifulSoup(html_content, 'html.parser')
                self.logger.info("Page content parsed with BeautifulSoup")

                # 새로운 HTML 구조에서 키워드 추출
                # span.sds-comps-ellipsis-content 클래스를 가진 요소에서 텍스트 추출
                keyword_spans = soup.select('span.sds-comps-ellipsis-content')
                self.logger.info(f"Found {len(keyword_spans)} keyword spans")
                
                # 중복 제거를 위해 set 사용 후 순서 유지를 위해 list로 변환
                seen = set()
                keywords = []
                for span in keyword_spans:
                    # get_text()로 mark 태그를 제거하고 순수 텍스트만 추출
                    keyword = span.get_text(strip=True)
                    # 빈 문자열이 아니고 중복이 아닌 경우만 추가
                    if keyword and keyword not in seen:
                        keywords.append(keyword)
                        seen.add(keyword)
                        self.logger.info(f"Extracted keyword: {keyword}")
                
                rank = 0
                for keyword in keywords:
                    rank = rank + 1
                    results['result'].append({
                        'rank': rank,
                        'keyword': keyword
                    })

                self.logger.info(f"Final result count: {len(results['result'])}")
                
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            self.logger.error(traceback.format_exc())
        
        finally:
            self.logger.info(f"Scraping completed. result cnt: {len(results['result'])}")
            
        return results
