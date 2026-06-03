import gc
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
from selenium.webdriver.common.action_chains import ActionChains

# 개선된 셀레니움 드라이버 풀 사용
from selenium_driver import SeleniumDriver
from selenium_pool import get_driver_pool


class Scraper:
    def __init__(self):
        # FastAPI 기반 uvicorn 로거 사용 가정
        self.logger = logging.getLogger("uvicorn")

    def get_list(self, query: str, limit: int = 30):
        """
        주어진 query(검색어)로 유튜브 검색 결과를 크롤링.
        최대 limit개의 동영상 정보를 리스트 형태로 반환.
        드라이버 풀을 사용하여 성능을 개선합니다.
        """
        # gl=us를 붙여서 미국검색을 한다.
        base_url = "https://www.youtube.com/?gl=us"
        results = []

        try:
            self.logger.info(f"[YOUTUBE] Starting scrape for query: {query}, limit: {limit}")
            
            # 드라이버 풀에서 드라이버 가져오기 (새 탭에서 실행)
            pool = get_driver_pool()
            
            with pool.get_driver(base_url) as driver_wrapper:
                driver = driver_wrapper.driver
                wait = WebDriverWait(driver, 10)
                
                self.logger.info("[YOUTUBE] Driver obtained from pool. Page loaded.")
                
                # 1. 페이지 로딩 대기 (검색창이 나타날 때까지 대기)
                time.sleep(0.5)  # 최소한의 스크립트 바인딩 시간 확보
                try:
                    search_input_home = wait.until(
                        EC.element_to_be_clickable((By.NAME, "search_query"))
                    )
                    self.logger.info("[YOUTUBE] Found home search input")
                    
                    # 성능 개선: 글자를 하나씩 타이핑하지 않고 JavaScript로 즉시 주입 (복사-붙여넣기 시뮬레이션)
                    driver.execute_script(
                        "arguments[0].value = arguments[1]; "
                        "arguments[0].dispatchEvent(new Event('input', { bubbles: true })); "
                        "arguments[0].dispatchEvent(new Event('change', { bubbles: true }));",
                        search_input_home, query
                    )
                    search_input_home.send_keys(Keys.RETURN)
                    self.logger.info(f"[YOUTUBE] Injected query '{query}' via JS and pressed ENTER")

                except Exception as e:
                    self.logger.error(f"[YOUTUBE] Failed to search on home page: {e}")
                    raise e
                
                # 3. 결과 페이지 로딩 대기 (고정 대기 대신 동적 대기로 시간 단축)
                try:
                    wait.until(EC.url_contains("results"))
                    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "ytd-video-renderer, ytd-reel-item-renderer")))
                    self.logger.info("[YOUTUBE] Search results loaded successfully")
                except Exception as e:
                    self.logger.warning(f"[YOUTUBE] Timeout waiting for search results: {e}, continuing...")
                self.logger.info(f"[YOUTUBE] Current URL after search: {driver.current_url}")

                self.logger.info("[YOUTUBE] Start scrolling...")
                try:
                    # 개선: limit 개수만큼만 확인하며 동적 스크롤 (속도 및 성능 최적화)
                    last_height = driver.execute_script("return document.documentElement.scrollHeight")
                    max_scrolls = (limit // 10) + 15  # 대략 1번 스크롤 시 최소 10~20개 로딩 가정
                    
                    for _ in range(max_scrolls):
                        # 현재 렌더링된 아이템 개수 확인 (DOM 직접 조회로 Python 메모리 부하 및 통신 지연 최소화)
                        current_count = driver.execute_script(
                            "return document.querySelectorAll('ytd-video-renderer, ytd-reel-item-renderer').length;"
                        )
                        if current_count >= limit:
                            self.logger.info(f"[YOUTUBE] Sufficient items loaded ({current_count} >= {limit}). Stop scrolling.")
                            break
                            
                        # 끝까지 스크롤
                        driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")
                        time.sleep(1.5)  # 새로운 항목이 로딩될 때까지 대기
                        
                        new_height = driver.execute_script("return document.documentElement.scrollHeight")
                        if new_height == last_height:
                            # 더이상 높이 변화가 없으면 지연 대기 후 재확인
                            time.sleep(1.5)
                            new_height = driver.execute_script("return document.documentElement.scrollHeight")
                            if new_height == last_height:
                                self.logger.info("[YOUTUBE] Reached bottom of the page. No more items to load.")
                                break
                        last_height = new_height
                        
                except Exception as e:
                    self.logger.warning(f"[YOUTUBE] Error during dynamic scroll: {e}, continuing anyway...")

                # 검색 결과 페이지 파싱
                html_content = driver_wrapper.get_page_source()
                
                if not html_content or len(html_content) < 100:
                    self.logger.error("[YOUTUBE] Page source is empty or too short")
                    return results
                
                soup = BeautifulSoup(html_content, "html.parser")
                all_items = soup.select("ytd-video-renderer, ytd-reel-item-renderer")

                self.logger.info(f"[YOUTUBE] Parsed {len(all_items)} items from search page.")
                results = self._parse_items(driver, all_items, limit)
                self.logger.info(f"[YOUTUBE] Scraped total {len(results)} items.")
                
                # 메모리 안정성 개선: BeautifulSoup 객체 및 대용량 HTML 문자열 명시적 해제
                soup.decompose()
                del soup
                del html_content
                del all_items

        except Exception as e:
            self.logger.error(f"[YOUTUBE] Unexpected error in get_list(): {e}")
            self.logger.error(traceback.format_exc())

        finally:
            # 크롤링이 길어져 응답 시간이 초과되면 504 발생 가능
            self.logger.info(f"[YOUTUBE] Final result count: {len(results)}")
            # 가비지 컬렉터 강제 실행하여 메모리 단편화 및 릭 방지
            gc.collect()

        return results

    def _parse_items(self, driver, all_items, limit):
        """
        검색 결과 목록(여러 아이템)을 순회하며
        동영상 상세 정보를 필요한 만큼(limit) 수집.
        """
        results = []
        original_window = driver.current_window_handle

        for item in all_items:
            if len(results) >= limit:
                break

            # 1) 일반 동영상 (ytd-video-renderer)
            if item.name == "ytd-video-renderer":
                title_tag = item.select_one("#video-title")
                if not title_tag:
                    continue

                title = title_tag.get("title", "").strip()
                href = title_tag.get("href", "")
                url = (
                    f"https://www.youtube.com{href}"
                    if href.startswith("/")
                    else href
                )

                channel_tag = item.select_one("ytd-channel-name #text")
                channel = channel_tag.get_text(strip=True) if channel_tag else ""

                # 조회수, 업로드 날짜 파싱
                meta_info = item.select_one("#metadata-line")
                view_count, published_date = "", ""
                if meta_info:
                    spans = meta_info.find_all("span")
                    if len(spans) >= 2:
                        try:
                            view_count = self.get_view_count(spans[0].get_text(strip=True))
                            published_date = self.calculate_before_date(spans[1].get_text(strip=True))
                        except Exception as e:
                            self.logger.warning(
                                f"Error processing meta info: {e} - {spans}"
                            )

                # 동영상 상세 정보 확인 (새 탭 사용)
                desc_texts = []
                snippet_containers = item.select("div.metadata-snippet-container-one-line")

                video_title_tag = item.find('a', id='video-title')
                aria_label = video_title_tag.get('aria-label', '')
                #print(aria_label)
                match = re.search(r'(?:조회수\s+)?([\d,]+)(?:회| views)', aria_label)
                if match:
                    view_count = match.group(1).replace(",", "")

                for container in snippet_containers:
                    # (1) 링크 영역에 들어간 snippet-text-navigation
                    link_snippet = container.select_one("a.metadata-snippet-timestamp yt-formatted-string.metadata-snippet-text-navigation")
                    if link_snippet:
                        desc_texts.append(link_snippet.get_text(separator=" ", strip=True))

                    # (2) 링크 밖에 있는 snippet-text
                    no_link_snippet = container.select_one("yt-formatted-string.metadata-snippet-text")
                    # 경우에 따라 hidden="" 되어 있을 수도 있는데, 일단 get_text()로 시도
                    if no_link_snippet:
                        desc_texts.append(no_link_snippet.get_text(separator=" ", strip=True))

                # 최종적으로 2~3개의 문자열이 들어올 수 있으니 합쳐서 하나의 문자열로
                description = "\n".join(desc_texts).strip()
                #description = self._open_new_tab_and_collect_info(
                #    driver=driver,
                #    url=url
                #)
                video_id = self.get_video_id_with_split(url)

                results.append({
                    "VideoID": video_id,
                    "title": title,
                    "channel": channel,
                    "url": url,
                    "description": description,
                    "publishedDate": published_date,
                    "videoCount": view_count,
                    "videoType": "shorts" if "shorts" in url else "video",
                })

            # 2) Shorts (ytd-reel-item-renderer)
            elif item.name == "ytd-reel-item-renderer":
                title_tag = item.select_one("#shorts-title")
                if not title_tag:
                    continue
                title = title_tag.get_text(strip=True)

                shorts_link_tag = item.select_one("a#thumbnail")
                if not shorts_link_tag:
                    continue

                href = shorts_link_tag.get("href", "")
                url = f"https://www.youtube.com{href}"

                channel_tag = item.select_one("ytd-channel-name #text")
                channel = channel_tag.get_text(strip=True) if channel_tag else ""

                # Shorts의 조회수/업로드 날짜는 검색결과에서 잘 안 보이므로 기본값
                view_count, published_date = "", ""
                video_id = ""
                if "shorts" in url:
                    video_id = video_id.split("shorts/")[1]

                # 필요 시 상세 페이지 열어서 정보 수집 가능
                # 여기서는 예시로 생략
                results.append({
                    "VideoID": video_id,
                    "title": title,
                    "channel": channel,
                    "url": url,
                    "description": "",
                    "publishedDate": published_date,
                    "videoCount": view_count,
                    "videoType": "shorts"
                })

        return results


    def calculate_before_date(self, input_str: str):
        """
        예: '3개월 전', '2일 전', '1주 전', '11 months ago' 등을 
        현재 시점 기준(오늘)에서 계산한 실제 날짜 YYYY-MM-DD 로 반환.
        """
        pattern = r"(\d+)\s*(년|개월|주|일|시간|분|초|year|month|week|day|hour|minute|second)s?\s*(전|ago)"
        match = re.search(pattern, input_str.strip(), re.IGNORECASE)
        if not match:
            # 매칭 실패 시 그냥 빈 문자열 반환
            return ""

        number_str, unit_str, _ = match.groups()
        number = int(number_str)

        unit_map = {
            "년": "years", "year": "years",
            "개월": "months", "month": "months",
            "주": "weeks", "week": "weeks",
            "일": "days", "day": "days",
            "시간": "hours", "hour": "hours",
            "분": "minutes", "minute": "minutes",
            "초": "seconds", "second": "seconds",
        }

        unit_key = unit_str.lower()
        if unit_key not in unit_map:
            return ""

        now = datetime.now()
        delta_args = {unit_map[unit_key]: number}
        before_date = now - relativedelta(**delta_args)
        return before_date.strftime("%Y-%m-%d")

    def get_view_count(self, view_str: str) -> str:
        """
        예) '조회수 1.2만회', '125k views', '1.3M' 등을 정수 형식 문자열로 변환.
        """
        s = view_str.strip().lower()
        s = re.sub(r"(조회수|views|회|\s+)", "", s)

        # '1.2만', '3.5천' 등
        korean_match = re.match(r"^(\d+(?:\.\d+)?)(만|천)$", s)
        if korean_match:
            number_str, unit_str = korean_match.groups()
            number = float(number_str)
            if unit_str == "만":
                return str(int(number * 10_000))
            elif unit_str == "천":
                return str(int(number * 1_000))

        # 영문 k, m 등
        multiplier = 1
        if "k" in s:
            multiplier = 1_000
            s = s.replace("k", "")
        elif "m" in s:
            multiplier = 1_000_000
            s = s.replace("m", "")

        try:
            value = float(s)
        except ValueError:
            return "0"

        return str(int(value * multiplier))

    def to_kst(self, timestamp: str):
        """
        문자열 형태의 UTC/로컬 시간을 KST(UTC+9)로 변환.
        """
        dt = datetime.fromisoformat(timestamp)
        kst = timezone(timedelta(hours=9))
        dt_kst = dt.astimezone(kst)
        return dt_kst.isoformat()

    def get_video_id_with_split(self, url: str):
        if 'shorts' in url:
            return url.split("shorts/")[1]
        if 'v=' not in url:
            return ""  # 혹은 raise 예외 처리

        parts = url.split('v=')
        if len(parts) < 2:
            return ""  # 혹은 raise 예외 처리

        video_id_part = parts[1]
        # '&'가 있을 경우 '&' 이전까지만 ID로 사용
        video_id = video_id_part.split('&')[0]
        return video_id
