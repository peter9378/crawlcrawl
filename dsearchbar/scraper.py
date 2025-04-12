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

# 개선된 셀레니움 드라이버(사용 환경에 맞춰 구현)
from selenium_driver import SeleniumDriver


class Scraper:
    def __init__(self):
        # FastAPI 기반 uvicorn 로거 사용 가정
        self.logger = logging.getLogger("uvicorn")
        # 기본 URL 설정
        self.base_url = "https://www.youtube.com/results?search_query="

    def get_youtube_list(self, query: str):
        """
        주어진 query(검색어)로 유튜브 검색 결과를 크롤링.
        최대 limit개의 동영상 정보를 리스트 형태로 반환.
        """
        results = []

        try:
            # 브라우저/드라이버 실행
            with SeleniumDriver(start_url="https://www.youtube.com/") as selenium_context:
                driver = selenium_context.driver

                # 암묵적 대기(최대 5초)
                driver.implicitly_wait(5)

                self.logger.info("Driver initialized. Navigating to search page.")
                search = driver.find_element_by_name('search_query')
                search.send_keys(query)

                # 검색어 자동완성 항목 파싱
                self.logger.info("Parsing search suggestions...")
                suggestions = self._parse_search_suggestions(driver)
                if suggestions:
                    self.logger.info(f"Found {len(suggestions)} search suggestions")
                    results.extend(suggestions)

                self.logger.info("Start scrolling...")
                self.scroll_down(driver, nloop=limit + 1)
                time.sleep(2)  # 페이지 로딩이 완전히 끝날 때까지 대기

                # 검색 결과 페이지 파싱
                soup = BeautifulSoup(driver.page_source, "html.parser")
                all_items = soup.select("ytd-video-renderer, ytd-reel-item-renderer")

                self.logger.info(f"Parsed {len(all_items)} items from search page.")
                video_results = self._parse_items(driver, all_items, limit)
                self.logger.info(f"Scraped total {len(video_results)} video items.")
                
                # 비디오 결과 추가
                results.extend(video_results)

        except Exception as e:
            self.logger.error(f"Unexpected error in get_list(): {e}")
            self.logger.error(traceback.format_exc())

        finally:
            # 크롤링이 길어져 응답 시간이 초과되면 504 발생 가능
            self.logger.info(f"Final result count: {len(results)}")

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
        if "shorts" in url:
            return url.split("shorts/")[1]
        return url.split("v=")[1]

    def get_coupang_list(self, query: str):
        """
        주어진 query(검색어)로 쿠팡 검색어 제안을 크롤링.
        검색어 제안 목록을 리스트 형태로 반환.
        """
        results = []
        try:
            # 브라우저/드라이버 실행
            with SeleniumDriver(start_url="https://www.coupang.com/") as selenium_context:
                driver = selenium_context.driver
                driver.implicitly_wait(5)

                self.logger.info("Driver initialized. Navigating to Coupang search page.")
                
                # 검색창 찾기 및 검색어 입력
                search = driver.find_element(By.ID, "q")
                search.clear()
                search.send_keys(query)
                
                # 검색어 제안이 로드될 때까지 대기
                time.sleep(1)
                
                # 검색어 제안 파싱
                soup = BeautifulSoup(driver.page_source, "html.parser")
                suggest_div = soup.find("div", id="suggest")
                
                if suggest_div:
                    # class가 kwd인 a 태그 찾기
                    kwd_links = suggest_div.select("a.kwd")
                    
                    self.logger.info(f"Found {len(kwd_links)} search suggestions.")
                    
                    for link in kwd_links:
                        try:
                            # data-click-logging-data 속성 가져오기
                            data_attr = link.get("data-click-logging-data", "")
                            if data_attr:
                                # JSON 파싱
                                data_json = json.loads(data_attr)
                                # q 키의 값 가져오기
                                if "q" in data_json:
                                    results.append(data_json["q"])
                        except Exception as e:
                            self.logger.error(f"Error parsing suggestion data: {e}")
                            continue
                else:
                    self.logger.warning("Search suggestions not found.")

        except Exception as e:
            self.logger.error(f"Unexpected error in get_coupang_list(): {e}")
            self.logger.error(traceback.format_exc())

        return results

    def _parse_search_suggestions(self, driver):
        """
        유튜브 검색창의 자동완성 제안 항목을 파싱합니다.
        """
        suggestions = []
        try:
            # 검색창에 포커스
            search_input = driver.find_element(By.CSS_SELECTOR, "input[name='search_query']")
            search_input.click()
            time.sleep(1)  # 자동완성 항목이 로드될 때까지 대기
            
            # 자동완성 항목 파싱 - 더 정확한 선택자 사용
            suggestion_elements = driver.find_elements(By.CSS_SELECTOR, "div.ytSuggestionComponentSuggestion")
            
            for element in suggestion_elements:
                try:
                    # aria-label 속성에서 전체 검색어 가져오기
                    suggestion_text = element.get_attribute("aria-label")
                    
                    # 검색어 텍스트 요소 찾기 - HTML 구조에 맞게 수정
                    left_container = element.find_element(By.CSS_SELECTOR, "div.ytSuggestionComponentLeftContainer")
                    if left_container:
                        # 일반 텍스트와 굵은 텍스트 모두 가져오기
                        normal_text = left_container.find_element(By.CSS_SELECTOR, "span:first-child").text.strip()
                        bold_text = ""
                        try:
                            bold_element = left_container.find_element(By.CSS_SELECTOR, "span.ytSuggestionComponentBold")
                            if bold_element:
                                bold_text = bold_element.text.strip()
                        except:
                            pass
                        
                        # 전체 검색어 조합
                        full_text = normal_text + bold_text
                        
                        # 검색어가 비어있지 않은 경우에만 추가
                        if full_text:
                            suggestions.append({
                                "type": "suggestion",
                                "text": full_text,
                                "url": f"{self.base_url}{full_text}"
                            })
                except Exception as e:
                    self.logger.warning(f"Error parsing suggestion element: {e}")
            
            # 자동완성 항목이 없거나 적은 경우, 직접 검색창에 입력하여 자동완성 항목 가져오기
            if len(suggestions) < 5:
                try:
                    # 검색창에 입력
                    search_input.clear()
                    search_input.send_keys("속건조")
                    time.sleep(1)  # 자동완성 항목이 로드될 때까지 대기
                    
                    # 자동완성 항목 다시 파싱
                    suggestion_elements = driver.find_elements(By.CSS_SELECTOR, "div.ytSuggestionComponentSuggestion")
                    
                    for element in suggestion_elements:
                        try:
                            # aria-label 속성에서 전체 검색어 가져오기
                            suggestion_text = element.get_attribute("aria-label")
                            
                            # 검색어 텍스트 요소 찾기 - HTML 구조에 맞게 수정
                            left_container = element.find_element(By.CSS_SELECTOR, "div.ytSuggestionComponentLeftContainer")
                            if left_container:
                                # 일반 텍스트와 굵은 텍스트 모두 가져오기
                                normal_text = left_container.find_element(By.CSS_SELECTOR, "span:first-child").text.strip()
                                bold_text = ""
                                try:
                                    bold_element = left_container.find_element(By.CSS_SELECTOR, "span.ytSuggestionComponentBold")
                                    if bold_element:
                                        bold_text = bold_element.text.strip()
                                except:
                                    pass
                                
                                # 전체 검색어 조합
                                full_text = normal_text + bold_text
                                
                                # 검색어가 비어있지 않은 경우에만 추가
                                if full_text and full_text not in [s["text"] for s in suggestions]:
                                    suggestions.append({
                                        "type": "suggestion",
                                        "text": full_text,
                                        "url": f"{self.base_url}{full_text}"
                                    })
                        except Exception as e:
                            self.logger.warning(f"Error parsing suggestion element: {e}")
                except Exception as e:
                    self.logger.warning(f"Error getting additional suggestions: {e}")
                    
        except Exception as e:
            self.logger.error(f"Error parsing search suggestions: {e}")
            
        return suggestions
