from bs4 import BeautifulSoup
import logging
import os
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


# 봇 탐지 우회를 위한 스텔스 JS 스크립트
# navigator.webdriver, plugins, languages, WebGL, permissions API 등 스푸핑
_STEALTH_JS = """
// webdriver 프로퍼티 완전히 숨기기
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});

// Chrome 런타임 스푸핑 (headless에서는 존재하지 않음)
if (!window.chrome) {
  window.chrome = {
    runtime: {},
    loadTimes: function() {},
    csi: function() {},
    app: {},
  };
}

// 플러그인 스푸핑 (빈 플러그인 목록은 봇 시그널)
try {
  Object.defineProperty(navigator, 'plugins', {
    get: () => {
      const arr = [
        { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
        { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
        { name: 'Native Client', filename: 'internal-nacl-plugin', description: '' },
      ];
      arr.__proto__ = PluginArray.prototype;
      return arr;
    }
  });
} catch(e) {}

// 언어 설정 스푸핑
Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});

// Permissions API 패치 (알림 권한 쿼리 처리)
try {
  const _origPermQuery = window.navigator.permissions.query.bind(window.navigator.permissions);
  window.navigator.permissions.query = (params) =>
    params.name === 'notifications'
      ? Promise.resolve({state: Notification.permission})
      : _origPermQuery(params);
} catch(e) {}

// WebGL 렌더러 정보 스푸핑 (headless 탐지 방지)
try {
  const _getParam = WebGLRenderingContext.prototype.getParameter;
  WebGLRenderingContext.prototype.getParameter = function(p) {
    if (p === 37445) return 'Intel Inc.';
    if (p === 37446) return 'Intel Iris OpenGL Engine';
    return _getParam.call(this, p);
  };
} catch(e) {}

// hairlineFeature 탐지 방지
try {
  Object.defineProperty(screen, 'colorDepth', {get: () => 24});
} catch(e) {}
"""


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

    # 최신 Chrome User-Agent 풀 (Linux/Windows 혼합으로 GCP 서버 특성 희석)
    _USER_AGENTS = [
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
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

    def _create_driver(self, headless: bool = False) -> uc.Chrome:
        options = uc.ChromeOptions()

        # 윈도우 사이즈 무작위화
        width = random.randint(1800, 1920)
        height = random.randint(900, 1080)
        options.add_argument(f'--window-size={width},{height}')

        if headless:
            options.add_argument('--headless=new')

        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--mute-audio')
        options.add_argument('--disable-notifications')
        options.add_argument('--disable-popup-blocking')
        options.add_argument('--disable-geolocation')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-software-rasterizer')
        options.add_argument('--disable-extensions')
        options.add_argument('--lang=en-US')
        options.add_argument('--accept-lang=en-US,en;q=0.9')

        # User-Agent 명시적 설정 (undetected_chromedriver와 호환되는 방식)
        ua = random.choice(self._USER_AGENTS)
        options.add_argument(f'--user-agent={ua}')
        print(f"[uc] Using User-Agent: {ua}")

        # 주의: add_experimental_option("prefs", ...) 는 undetected_chromedriver와
        # 충돌하여 봇 탐지를 유발할 수 있으므로 제거함
        # 이미지 비활성화도 제거 — 봇 특징적 행동으로 탐지됨

        kwargs = dict(options=options, use_subprocess=True)
        if self._chrome_version:
            kwargs["version_main"] = self._chrome_version

        _orig_ctx = ssl._create_default_https_context
        ssl._create_default_https_context = ssl._create_unverified_context
        try:
            driver = uc.Chrome(**kwargs)
        finally:
            ssl._create_default_https_context = _orig_ctx

        # 강화된 스텔스 스크립트 주입 (모든 페이지 로드 전에 실행)
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": _STEALTH_JS}
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
            time.sleep(1.5)  # Xvfb 초기화 대기
            return proc
        except FileNotFoundError:
            return None

    # ------------------------------------------------------------------ #
    #  자연스러운 사용자 행동 시뮬레이션                                      #
    # ------------------------------------------------------------------ #

    def _human_type(self, element, text: str):
        """실제 사람처럼 한 글자씩 랜덤 딜레이를 두고 타이핑."""
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(0.04, 0.18))

    def _move_mouse_randomly(self, driver: uc.Chrome):
        """페이지 로드 직후 마우스를 화면 내 여러 위치로 자연스럽게 이동."""
        try:
            body = driver.find_element(By.TAG_NAME, "body")
            actions = ActionChains(driver)
            for _ in range(random.randint(2, 5)):
                x = random.randint(-400, 400)
                y = random.randint(-200, 200)
                actions.move_to_element_with_offset(body, x, y)
                actions.pause(random.uniform(0.1, 0.4))
            actions.perform()
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    #  메인 스크래핑                                                         #
    # ------------------------------------------------------------------ #

    def scrape_google(self, query: str, limit: int = 30):
        encoded_query = urllib.parse.quote(query)
        search_url = f"https://www.google.com/search?q={encoded_query}&gl=us&hl=en"
        results = []
        driver = None
        xvfb_proc = None
        headless = False

        try:
            print(f"start crawling google with undetected_chromedriver for query: {query}")

            # Linux 서버: Xvfb 가상 디스플레이 위에서 Chrome을 headless 없이 실행
            # headless 모드보다 탐지 가능성이 낮음
            if self._is_linux():
                xvfb_proc = self._start_xvfb()
                if xvfb_proc:
                    os.environ["DISPLAY"] = ":99"
                    print("[uc] Xvfb virtual display started on :99")
                else:
                    # Xvfb 없으면 headless=new 로 fallback
                    headless = True
                    print("[uc] Xvfb not found, falling back to --headless=new")

            driver = self._create_driver(headless=headless)

            # 구글 홈페이지를 먼저 방문 (직접 검색 URL 접속 시 봇 탐지 확률 높음)
            home_url = "https://www.google.com/?gl=us&hl=en"
            driver.get(home_url)
            time.sleep(random.uniform(2.0, 3.5))

            # 페이지 로드 후 자연스러운 마우스 이동
            self._move_mouse_randomly(driver)
            time.sleep(random.uniform(0.5, 1.2))

            try:
                search_box = WebDriverWait(driver, 8).until(
                    EC.element_to_be_clickable((By.NAME, "q"))
                )
                # 검색창으로 마우스 이동 후 클릭
                actions = ActionChains(driver)
                actions.move_to_element(search_box)
                actions.pause(random.uniform(0.3, 0.7))
                actions.click()
                actions.pause(random.uniform(0.3, 0.6))
                actions.perform()

                # 한 글자씩 자연스럽게 타이핑
                self._human_type(search_box, query)
                time.sleep(random.uniform(0.5, 1.0))
                search_box.send_keys(Keys.RETURN)
                self.logger.info("Successfully typed the query and pressed ENTER on homepage.")

                # 결과 페이지 전환 대기
                time.sleep(random.uniform(2.5, 4.0))

            except Exception as e:
                self.logger.warning(f"Failed to use type-and-search: {e}. Falling back to direct URL.")
                driver.get(search_url)
                time.sleep(random.uniform(2.5, 4.0))

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
                scroll_position += random.randint(1000, 2000)
                driver.execute_script(f"window.scrollTo(0, {scroll_position})")
                time.sleep(random.uniform(0.3, 0.8))
                self.logger.info(f"Scrolled down to position: {scroll_position}")
        except WebDriverException as e:
            self.logger.error(f"Error during scroll: {e}")
            self.logger.error(traceback.format_exc())


if __name__ == '__main__':
    scraper = Scraper()
    result = scraper.scrape_google('hello')
    print(result)
