from bs4 import BeautifulSoup
import logging
import re
import ssl
import sys
from typing import Optional
import subprocess
import undetected_chromedriver as uc
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
import urllib.parse
import traceback
import time
import random


class Scraper:
    # Chrome 실행 경로 후보 (macOS + Linux)
    _CHROME_PATHS = [
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ]

    def __init__(self):
        self.logger = logging.getLogger('uvicorn')
        self._chrome_version: Optional[int] = self._get_chrome_version()
        if self._chrome_version:
            print(f"[uc] Detected Chrome version: {self._chrome_version}")
        else:
            print("[uc] Chrome version not detected; will bypass SSL for patcher.")

    # ------------------------------------------------------------------ #
    #  Chrome 버전 감지                                                     #
    # ------------------------------------------------------------------ #

    def _get_chrome_version(self) -> Optional[int]:
        """로컬 Chrome 버전의 메이저 번호를 반환. 실패 시 None."""
        candidates = list(self._CHROME_PATHS)

        # PATH 상의 chrome 찾기
        for cmd in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
            try:
                path = subprocess.check_output(
                    ["which", cmd], stderr=subprocess.DEVNULL, timeout=3
                ).decode().strip()
                if path:
                    candidates.append(path)
            except Exception:
                pass

        # macOS Spotlight 검색
        try:
            found = subprocess.check_output(
                ["mdfind", "kMDItemCFBundleIdentifier == 'com.google.Chrome'"],
                stderr=subprocess.DEVNULL, timeout=5
            ).decode().strip()
            for line in found.splitlines():
                candidates.append(f"{line.strip()}/Contents/MacOS/Google Chrome")
        except Exception:
            pass

        for path in candidates:
            try:
                out = subprocess.check_output(
                    [path, "--version"], stderr=subprocess.DEVNULL, timeout=5
                ).decode()
                match = re.search(r"(\d+)\.\d+\.\d+\.\d+", out)
                if match:
                    return int(match.group(1))
            except Exception:
                continue

        return None

    # ------------------------------------------------------------------ #
    #  드라이버 생성                                                         #
    # ------------------------------------------------------------------ #

    def _create_driver(self) -> uc.Chrome:
        options = uc.ChromeOptions()
        
        # 1. 윈도우 사이즈 무작위화
        width = random.randint(1800, 1920)
        height = random.randint(900, 1080)
        options.add_argument(f'--window-size={width},{height}')
        
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--mute-audio')
        options.add_argument('--disable-notifications')
        options.add_argument('--disable-popup-blocking')
        options.add_argument('--disable-geolocation')
        options.add_argument('--lang=en-US,en;q=0.9')
        options.add_argument('--disable-blink-features=AutomationControlled')
        # GCP 환경에서 DISPLAY 가 없을 때 렌더링 오류 방지
        options.add_argument('--disable-software-rasterizer')
        options.add_argument('--disable-extensions')
        # User-Agent 설정 제거: undetected-chromedriver가 내부적으로 
        # 브라우저의 실제 UA 및 sec-ch-ua 헤더를 유지하도록 하여 구글 봇 탐지 우회
        prefs = {
            "profile.managed_default_content_settings.images": 2,
            "profile.default_content_setting_values.notifications": 2,
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,
        }
        options.add_experimental_option("prefs", prefs)

        kwargs = dict(options=options, use_subprocess=True)
        if self._chrome_version:
            kwargs["version_main"] = self._chrome_version

        # uc patcher 는 chromedriver 캐시가 없으면 항상 HTTPS 다운로드를 시도한다.
        # Python.org macOS 설치본은 SSL 인증서가 없어 실패하므로
        # uc.Chrome() 초기화 구간에만 SSL 검증을 일시 우회하고 즉시 복원한다.
        _orig_ctx = ssl._create_default_https_context
        ssl._create_default_https_context = ssl._create_unverified_context
        try:
            driver = uc.Chrome(**kwargs)
        finally:
            ssl._create_default_https_context = _orig_ctx

        # navigator.webdriver 숨김
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"}
        )
        return driver

    # ------------------------------------------------------------------ #
    #  Xvfb 가상 디스플레이 (Linux 전용)                                    #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _is_linux() -> bool:
        return sys.platform.startswith("linux")

    @staticmethod
    def _start_xvfb() -> Optional[subprocess.Popen]:
        """
        Linux 서버에서 Xvfb 가상 디스플레이를 시작한다.
        Chrome을 headless 없이 실행하면 Google bot 탐지를 피할 수 있다.
        반환값: Popen 프로세스 (종료 시 terminate 필요), 실패 시 None.
        """
        try:
            proc = subprocess.Popen(
                ["Xvfb", ":99", "-screen", "0", "1920x1080x24", "-ac"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(0.8)  # Xvfb 초기화 대기
            return proc
        except FileNotFoundError:
            return None

    # ------------------------------------------------------------------ #
    #  메인 스크래핑                                                         #
    # ------------------------------------------------------------------ #

    def scrape_google(self, query: str, limit: int = 30):
        encoded_query = urllib.parse.quote(query)
        search_url = f"https://www.google.com/search?q={encoded_query}&gl=us&hl=en"
        results = []
        driver = None
        xvfb_proc = None

        try:
            print(f"start crawling google with undetected_chromedriver for query: {query}")

            # Linux 서버: Xvfb 가상 디스플레이 위에서 Chrome을 headless 없이 실행
            if self._is_linux():
                xvfb_proc = self._start_xvfb()
                if xvfb_proc:
                    import os
                    os.environ["DISPLAY"] = ":99"
                    print("[uc] Xvfb virtual display started on :99")
                else:
                    # Xvfb 없으면 headless=new 로 fallback
                    print("[uc] Xvfb not found, falling back to --headless=new")

            driver = self._create_driver()
            
            # 홈페이지를 먼저 방문하여 유저 이벤트를 생성 (직접 URL 접속 시 bot 탐지 확률 높음)
            home_url = "https://www.google.com/?gl=us&hl=en"
            driver.get(home_url)
            time.sleep(random.uniform(1.0, 2.5))
            
            try:
                # 검색창 요소 찾기 (보통 name="q"인 textarea 혹은 input)
                search_box = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.NAME, "q"))
                )
                # 실제 유저처럼 클릭 후 타이핑하여 검색 수행
                actions = ActionChains(driver)
                actions.move_to_element(search_box).click().pause(0.5).send_keys(query).pause(0.5).send_keys(Keys.RETURN).perform()
                self.logger.info("Successfully typed the query and pressed ENTER on homepage.")
                
                # 결과 페이지 전환 대기
                time.sleep(random.uniform(2.0, 3.5))
                
            except Exception as e:
                self.logger.warning(f"Failed to use type-and-search: {e}. Falling back to direct URL.")
                driver.get(search_url)
                time.sleep(random.uniform(1.0, 2.0))

            # 스크롤로 lazy-load 트리거
            self._scroll_down(driver, nloop=3)

            # #bres (관련 검색어 컨테이너) 대기
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, 'bres'))
                )
                time.sleep(1)
            except TimeoutException:
                self.logger.warning("Timeout waiting for #bres, falling back to current DOM.")

            html_content = driver.page_source

            # CAPTCHA / bot 차단 탐지 — URL 기반으로 정확히 판단
            if '/sorry/' in driver.current_url or 'solveSimpleChallenge' in html_content:
                self.logger.error(
                    f"Google CAPTCHA detected! current_url={driver.current_url}"
                )
                return results

            soup = BeautifulSoup(html_content, 'html.parser')
            seen = set()
            bres_div = soup.find(id='bres')

            if bres_div:
                for a in bres_div.find_all('a'):
                    text = a.get_text(separator=' ', strip=True)
                    if text and len(text) > 1 and text not in seen:
                        seen.add(text)
                        results.append({"rank": len(results) + 1, "keyword": text})

            # Fallback: 'Related searches' 섹션 파싱
            if not results:
                headers = soup.find_all(
                    string=lambda t: t and (
                        'Related searches' in t or 'People also search for' in t
                    )
                )
                for h in headers:
                    container = h.parent.find_parent()
                    while container and container.name != 'div':
                        container = container.parent
                    if container:
                        for a in container.find_all('a'):
                            href = a.get('href', '')
                            if '/search?q=' in href:
                                text = a.get_text(separator=' ', strip=True)
                                if text and text not in seen and query.lower() != text.lower():
                                    seen.add(text)
                                    results.append({"rank": len(results) + 1, "keyword": text})

            results = [r for r in results if "click here" not in r["keyword"].lower()]
            results = results[:limit]

        except Exception as e:
            self.logger.error(f'Unexpected error occurred: {str(e)}')
            self.logger.error(traceback.format_exc())

        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass
            if xvfb_proc:
                xvfb_proc.terminate()
            self.logger.info(f"Scraping completed. Total results: {len(results)}")

        return results

    # ------------------------------------------------------------------ #
    #  스크롤                                                               #
    # ------------------------------------------------------------------ #

    def _scroll_down(self, driver: uc.Chrome, nloop: int = 1):
        scroll_position = 0
        try:
            for _ in range(nloop):
                # 스크롤 양과 대기 시간을 무작위로 설정
                scroll_position += random.randint(1000, 2000)
                driver.execute_script(f"window.scrollTo(0, {scroll_position})")
                time.sleep(random.uniform(0.1, 0.6))
                self.logger.info(f"Scrolled down to position: {scroll_position}")
        except WebDriverException as e:
            self.logger.error(f"Error during scroll: {e}")
            self.logger.error(traceback.format_exc())


if __name__ == '__main__':
    scraper = Scraper()
    result = scraper.scrape_google('hello')
    print(result)
