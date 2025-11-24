import requests
from bs4 import BeautifulSoup
import logging
import traceback
import time
import random
from urllib.parse import quote
from typing import Optional, Dict, Any
from functools import wraps

# 개선된 셀레니움 드라이버(사용 환경에 맞춰 구현)
from selenium_driver import SeleniumDriver
from selenium_pool import get_driver_pool


class ScraperException(Exception):
    """스크래핑 실패 시 발생하는 예외"""
    pass


def retry_with_exponential_backoff(
    max_retries: int = 5,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """지수 백오프를 사용한 재시도 데코레이터
    
    Args:
        max_retries: 최대 재시도 횟수
        initial_delay: 초기 대기 시간 (초)
        max_delay: 최대 대기 시간 (초)
        exponential_base: 지수 증가 베이스
        exceptions: 재시도할 예외 타입들
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_retries - 1:
                        # 마지막 시도에서도 실패하면 예외 발생
                        raise ScraperException(
                            f"Failed after {max_retries} attempts: {str(e)}"
                        ) from e
                    
                    # 로깅
                    logger = logging.getLogger('uvicorn')
                    logger.warning(
                        f"Attempt {attempt + 1}/{max_retries} failed: {str(e)}. "
                        f"Retrying in {delay:.2f} seconds..."
                    )
                    
                    # 지수 백오프 대기
                    time.sleep(delay + random.uniform(0, delay * 0.1))
                    
                    # 다음 재시도를 위한 delay 증가
                    delay = min(delay * exponential_base, max_delay)
            
            # 이 코드에 도달하면 안되지만, 안전장치
            if last_exception:
                raise last_exception
                
        return wrapper
    return decorator

class Scraper:
    # 네트워크 요청 타임아웃 (초)
    REQUEST_TIMEOUT = 30
    # 세션 복구를 위한 최대 재시도 횟수
    SESSION_RESET_MAX_RETRIES = 3
    
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
        self.session = None
        self._initialize_session()
    
    def _initialize_session(self):
        """세션 초기화 또는 재생성"""
        if self.session:
            try:
                self.session.close()
            except Exception as e:
                self.logger.warning(f"Error closing old session: {e}")
        
        self.session = requests.Session()
        self.update_user_agent()
        self.logger.info("Session initialized/reset successfully")
    
    def _reset_session_on_error(self):
        """에러 발생 시 세션 리셋"""
        self.logger.warning("Resetting session due to errors...")
        self._initialize_session()
        
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

    def fetch_page(self, url: str, max_retries: int = 5, base_delay: float = 0.1) -> Optional[str]:
        """페이지 내용을 가져오는 함수
        
        Args:
            url: 가져올 URL
            max_retries: 최대 재시도 횟수
            base_delay: 기본 지연 시간 (초)
            
        Returns:
            HTML 페이지 내용 또는 실패 시 None
            
        Raises:
            ScraperException: 모든 재시도 실패 시
        """
        self.logger.info(f"Fetching URL: {url}")
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                # 재시도 시 User-Agent 업데이트 및 세션 복구
                if attempt > 0:
                    self.update_user_agent()
                    
                    # 3번째 재시도부터는 세션 리셋
                    if attempt >= 2:
                        self._reset_session_on_error()
                
                # Rate limiting을 위한 랜덤 지연
                delay = base_delay + random.uniform(0.1, 0.7)
                time.sleep(delay)
                
                self.logger.info(f"Request attempt {attempt+1}/{max_retries} with delay {delay:.2f}s")
                
                # timeout 설정으로 무한 대기 방지
                response = self.session.get(
                    url,
                    timeout=self.REQUEST_TIMEOUT,
                    allow_redirects=True
                )
                
                # HTTP 에러 체크
                response.raise_for_status()
                
                # 응답 검증
                if not response.text or len(response.text) < 100:
                    raise requests.RequestException("Response content too short or empty")
                
                # 성공적으로 응답 받았을 때 쿠키 저장
                self.session.cookies.update(response.cookies)
                
                self.logger.info(f"Successfully fetched page (length: {len(response.text)})")
                return response.text
                
            except requests.Timeout as e:
                last_exception = e
                self.logger.error(f"Timeout error (attempt {attempt+1}/{max_retries}): {e}")
                
            except requests.ConnectionError as e:
                last_exception = e
                self.logger.error(f"Connection error (attempt {attempt+1}/{max_retries}): {e}")
                
            except requests.HTTPError as e:
                last_exception = e
                status_code = e.response.status_code if e.response else 'Unknown'
                self.logger.error(f"HTTP error {status_code} (attempt {attempt+1}/{max_retries}): {e}")
                
                # 특정 HTTP 에러는 재시도하지 않음
                if e.response and e.response.status_code in [400, 401, 403, 404]:
                    self.logger.error(f"Non-retryable HTTP error {status_code}, failing immediately")
                    break
                    
            except requests.RequestException as e:
                last_exception = e
                self.logger.error(f"Request error (attempt {attempt+1}/{max_retries}): {e}")
            
            except Exception as e:
                last_exception = e
                self.logger.error(f"Unexpected error (attempt {attempt+1}/{max_retries}): {e}")
                self.logger.error(traceback.format_exc())
            
            # 마지막 시도가 아니면 지수 백오프 대기
            if attempt < max_retries - 1:
                backoff_delay = min((2 ** attempt) + random.uniform(0, 1), 30)
                self.logger.info(f"Backing off for {backoff_delay:.2f} seconds before retry...")
                time.sleep(backoff_delay)
        
        # 모든 재시도 실패
        error_msg = f"Failed to fetch {url} after {max_retries} attempts"
        if last_exception:
            error_msg += f": {str(last_exception)}"
        
        self.logger.error(error_msg)
        raise ScraperException(error_msg)

    @retry_with_exponential_backoff(
        max_retries=3,
        initial_delay=1.5,
        max_delay=30.0,
        exceptions=(ScraperException, Exception)
    )
    def scrape_naver_related(self, query: str) -> Dict[str, Any]:
        """네이버 연관검색어 스크래핑 (Selenium 드라이버 풀 사용)
        
        드라이버를 매번 생성하지 않고 풀에서 재사용하여 속도를 대폭 개선합니다.
        
        Args:
            query: 검색 키워드
            
        Returns:
            {'keyword': str, 'result': [{'rank': int, 'keyword': str}, ...]}
            
        Raises:
            ScraperException: 스크래핑 실패 시
        """
        base_url = f'https://search.naver.com/search.naver?where=nexearch&sm=top_hty&fbm=0&ie=utf8&query={quote(query)}'
        results = {
            'keyword': query,
            'result': []
        }
        
        try:
            self.logger.info(f"[RELATED] Starting Selenium scrape for keyword: {query}")
            self.logger.info(f"[RELATED] URL: {base_url}")
            
            # 드라이버 풀에서 드라이버 가져오기 (새 탭에서 실행)
            pool = get_driver_pool()
            
            with pool.get_driver(base_url) as driver_wrapper:
                driver = driver_wrapper.driver
                
                self.logger.info("[RELATED] Driver obtained from pool. Page loaded.")
                
                # 페이지가 완전히 로드될 때까지 대기
                time.sleep(1)
                
                # 연관검색어는 약간만 스크롤 (2회)
                self.logger.info("[RELATED] Scrolling to load related keywords...")
                try:
                    driver_wrapper.scroll_down(nloop=2, scroll_increment=300)
                    time.sleep(0.5)  # 스크롤 후 로딩 대기
                except Exception as e:
                    self.logger.warning(f"[RELATED] Error during scroll: {e}, continuing anyway...")
                
                # 페이지 소스 가져오기
                html_content = driver_wrapper.get_page_source()
                
                if not html_content or len(html_content) < 100:
                    raise ScraperException("[RELATED] Page source is empty or too short")
                
                soup = BeautifulSoup(html_content, 'html.parser')
                self.logger.info("[RELATED] Page content parsed with BeautifulSoup")

                # 연관검색어 추출
                ul = soup.find('ul', class_='lst_related_srch _list_box')
                if ul:
                    tit_divs = ul.find_all('div', class_='tit')
                    if len(tit_divs) > 0:
                        rank = 1
                        for div in tit_divs:
                            keyword_text = div.get_text(strip=True)
                            if keyword_text:  # 빈 문자열 제외
                                results['result'].append({
                                    'rank': rank,
                                    'keyword': keyword_text
                                })
                                rank += 1
                                self.logger.debug(f"[RELATED] Extracted keyword #{rank}: {keyword_text}")
                    else:
                        self.logger.warning(f"[RELATED] No related keywords found for: {query}")
                else:
                    self.logger.warning(f"[RELATED] Related keyword section not found for: {query}")

            # with 블록 종료 시 탭이 자동으로 닫히고 드라이버는 풀로 반환됨
            self.logger.info(f"[RELATED] Successfully scraped {len(results['result'])} keywords for: {query}")
            return results
            
        except ScraperException:
            # 이미 ScraperException인 경우 그대로 전파
            raise
            
        except Exception as e:
            error_msg = f"[RELATED] Unexpected error scraping {query}: {str(e)}"
            self.logger.error(error_msg)
            self.logger.error(traceback.format_exc())
            raise ScraperException(error_msg) from e
        
        finally:
            self.logger.info(f"[RELATED] Scraping completed. Result count: {len(results['result'])}")

    @retry_with_exponential_backoff(
        max_retries=3,
        initial_delay=1.5,
        max_delay=30.0,
        exceptions=(ScraperException, Exception)
    )
    def scrape_naver_popular(self, query: str) -> Dict[str, Any]:
        """네이버 인기주제 스크래핑 (Selenium 드라이버 풀 사용)
        
        드라이버를 매번 생성하지 않고 풀에서 재사용하여 속도를 대폭 개선합니다.
        
        Args:
            query: 검색 키워드
            
        Returns:
            {'keyword': str, 'result': [{'rank': int, 'keyword': str}, ...]}
            
        Raises:
            ScraperException: 스크래핑 실패 시
        """
        base_url = f'https://search.naver.com/search.naver?where=nexearch&sm=top_hty&fbm=0&ie=utf8&query={quote(query)}'
        results = {
            'keyword': query,
            'result': []
        }
        
        try:
            self.logger.info(f"[POPULAR] Starting Selenium scrape for keyword: {query}")
            self.logger.info(f"[POPULAR] URL: {base_url}")
            
            # 드라이버 풀에서 드라이버 가져오기 (새 탭에서 실행)
            pool = get_driver_pool()
            
            with pool.get_driver(base_url) as driver_wrapper:
                driver = driver_wrapper.driver
                
                self.logger.info("[POPULAR] Driver obtained from pool. Page loaded.")
                
                # 페이지가 완전히 로드될 때까지 대기
                time.sleep(1)
                
                # 인기주제도 약간 스크롤 (1회)
                self.logger.info("[POPULAR] Scrolling to load popular keywords...")
                try:
                    driver_wrapper.scroll_down(nloop=1, scroll_increment=300)
                    time.sleep(0.5)  # 스크롤 후 로딩 대기
                except Exception as e:
                    self.logger.warning(f"[POPULAR] Error during scroll: {e}, continuing anyway...")
                
                # 페이지 소스 가져오기
                html_content = driver_wrapper.get_page_source()
                
                if not html_content or len(html_content) < 100:
                    raise ScraperException("[POPULAR] Page source is empty or too short")
                
                soup = BeautifulSoup(html_content, 'html.parser')
                self.logger.info("[POPULAR] Page content parsed with BeautifulSoup")

                # 인기주제 키워드 추출
                keyword_spans = soup.select('span.fds-comps-keyword-chip-text')
                
                if not keyword_spans:
                    self.logger.warning(f"[POPULAR] No popular keywords found for: {query}")
                else:
                    rank = 1
                    for span in keyword_spans:
                        keyword_text = span.get_text(strip=True)
                        if keyword_text:  # 빈 문자열 제외
                            results['result'].append({
                                'rank': rank,
                                'keyword': keyword_text
                            })
                            rank += 1
                            self.logger.debug(f"[POPULAR] Extracted keyword #{rank}: {keyword_text}")

            # with 블록 종료 시 탭이 자동으로 닫히고 드라이버는 풀로 반환됨
            self.logger.info(f"[POPULAR] Successfully scraped {len(results['result'])} keywords for: {query}")
            return results
            
        except ScraperException:
            # 이미 ScraperException인 경우 그대로 전파
            raise
            
        except Exception as e:
            error_msg = f"[POPULAR] Unexpected error scraping {query}: {str(e)}"
            self.logger.error(error_msg)
            self.logger.error(traceback.format_exc())
            raise ScraperException(error_msg) from e
        
        finally:
            self.logger.info(f"[POPULAR] Scraping completed. Result count: {len(results['result'])}")

    @retry_with_exponential_backoff(
        max_retries=3,
        initial_delay=2.0,
        max_delay=30.0,
        exceptions=(ScraperException, Exception)
    )
    def scrape_naver_together(self, query: str) -> Dict[str, Any]:
        """네이버 함께찾은 키워드 스크래핑 (Selenium 드라이버 풀 사용)
        
        드라이버를 매번 생성하지 않고 풀에서 재사용하여 속도를 대폭 개선합니다.
        
        Args:
            query: 검색 키워드
            
        Returns:
            {'keyword': str, 'result': [{'rank': int, 'keyword': str}, ...]}
            
        Raises:
            ScraperException: 스크래핑 실패 시
        """
        base_url = f'https://search.naver.com/search.naver?where=nexearch&sm=top_hty&fbm=0&ie=utf8&query={quote(query)}'
        results = {
            'keyword': query,
            'result': []
        }
        
        try:
            self.logger.info(f"[TOGETHER] Starting Selenium scrape for keyword: {query}")
            self.logger.info(f"[TOGETHER] URL: {base_url}")
            
            # 드라이버 풀에서 드라이버 가져오기 (새 탭에서 실행)
            pool = get_driver_pool()
            
            with pool.get_driver(base_url) as driver_wrapper:
                driver = driver_wrapper.driver
                
                self.logger.info("[TOGETHER] Driver obtained from pool. Page loaded.")
                
                # 페이지가 완전히 로드될 때까지 대기
                time.sleep(1)
                
                # 현재 페이지 정보 로깅
                try:
                    page_title = driver.title
                    current_url = driver.current_url
                    self.logger.info(f"[TOGETHER] Current page title: {page_title}")
                    self.logger.info(f"[TOGETHER] Current URL: {current_url}")
                except Exception as e:
                    self.logger.warning(f"[TOGETHER] Could not get page info: {e}")
                
                # 스크롤을 통해 동적 콘텐츠 로드
                self.logger.info("[TOGETHER] Start scrolling...")
                try:
                    driver_wrapper.scroll_down(nloop=3)  # 3번 스크롤
                    time.sleep(1)  # 페이지 로딩이 완전히 끝날 때까지 대기
                except Exception as e:
                    self.logger.warning(f"[TOGETHER] Error during scroll: {e}, continuing anyway...")
                
                # 페이지 소스 가져오기
                html_content = driver_wrapper.get_page_source()
                
                if not html_content or len(html_content) < 100:
                    raise ScraperException("[TOGETHER] Page source is empty or too short")
                
                soup = BeautifulSoup(html_content, 'html.parser')
                self.logger.info("[TOGETHER] Page content parsed with BeautifulSoup")

                # 새로운 HTML 구조에서 키워드 추출
                keyword_spans = soup.select('span.sds-comps-ellipsis-content')
                self.logger.info(f"[TOGETHER] Found {len(keyword_spans)} keyword spans")
                
                if not keyword_spans:
                    self.logger.warning(f"[TOGETHER] No keyword spans found for: {query}")
                
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
                
                # 결과 저장
                rank = 0
                for keyword in keywords:
                    rank += 1
                    results['result'].append({
                        'rank': rank,
                        'keyword': keyword
                    })
                    self.logger.debug(f"[TOGETHER] Extracted keyword #{rank}: {keyword}")

            # with 블록 종료 시 탭이 자동으로 닫히고 드라이버는 풀로 반환됨
            self.logger.info(f"[TOGETHER] Successfully scraped {len(results['result'])} keywords for: {query}")
            return results
            
        except ScraperException:
            # 이미 ScraperException인 경우 그대로 전파
            raise
            
        except Exception as e:
            error_msg = f"[TOGETHER] Unexpected error scraping {query}: {str(e)}"
            self.logger.error(error_msg)
            self.logger.error(traceback.format_exc())
            raise ScraperException(error_msg) from e
        
        finally:
            self.logger.info(f"[TOGETHER] Scraping completed. Result count: {len(results['result'])}")
