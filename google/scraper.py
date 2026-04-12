from bs4 import BeautifulSoup
import logging
import os
import re
import sys
from typing import Optional
import subprocess
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import urllib.parse
import traceback
import time
import random


# ── 스텔스 스크립트 ──────────────────────────────────────────────────────────
# playwright는 기본적으로 navigator.webdriver를 노출하지 않지만,
# 추가적인 fingerprint 탐지 포인트를 모두 차단한다.
_STEALTH_JS = """
// Chrome 런타임 스푸핑
if (!window.chrome) {
  window.chrome = {
    runtime: {},
    loadTimes: function() {},
    csi: function() {},
    app: {},
  };
}

// 플러그인 스푸핑 (빈 배열은 봇 시그널)
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

// 언어 스푸핑
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });

// Permissions API 패치
try {
  const _orig = window.navigator.permissions.query.bind(window.navigator.permissions);
  window.navigator.permissions.query = (p) =>
    p.name === 'notifications'
      ? Promise.resolve({ state: Notification.permission })
      : _orig(p);
} catch(e) {}

// WebGL 렌더러 스푸핑 (headless 탐지 방지)
try {
  const _get = WebGLRenderingContext.prototype.getParameter;
  WebGLRenderingContext.prototype.getParameter = function(p) {
    if (p === 37445) return 'Intel Inc.';
    if (p === 37446) return 'Intel Iris OpenGL Engine';
    return _get.call(this, p);
  };
} catch(e) {}

// 화면 색심도 스푸핑
try { Object.defineProperty(screen, 'colorDepth', { get: () => 24 }); } catch(e) {}
"""

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
]

# 미국 주요 도시 timezone/geolocation 풀
_LOCALES = [
    {"timezone": "America/New_York",    "geo": {"longitude": -74.006,  "latitude": 40.713}},
    {"timezone": "America/Chicago",     "geo": {"longitude": -87.629,  "latitude": 41.878}},
    {"timezone": "America/Los_Angeles", "geo": {"longitude": -118.244, "latitude": 34.052}},
    {"timezone": "America/Denver",      "geo": {"longitude": -104.991, "latitude": 39.739}},
]


class Scraper:
    _CHROME_PATHS = [
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
    ]

    def __init__(self):
        self.logger = logging.getLogger('uvicorn')

    # ------------------------------------------------------------------ #
    #  Xvfb 가상 디스플레이 (Linux 전용)                                    #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _is_linux() -> bool:
        return sys.platform.startswith("linux")

    @staticmethod
    def _start_xvfb() -> Optional[subprocess.Popen]:
        try:
            proc = subprocess.Popen(
                ["Xvfb", ":99", "-screen", "0", "1920x1080x24", "-ac"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(1.5)
            return proc
        except FileNotFoundError:
            return None

    # ------------------------------------------------------------------ #
    #  자연스러운 사용자 행동                                                #
    # ------------------------------------------------------------------ #

    def _human_type(self, page, selector: str, text: str):
        """실제 사람처럼 한 글자씩 랜덤 딜레이를 두고 타이핑."""
        page.click(selector)
        time.sleep(random.uniform(0.2, 0.5))
        for char in text:
            page.keyboard.type(char)
            time.sleep(random.uniform(0.04, 0.16))

    def _move_mouse_randomly(self, page):
        """페이지 내 여러 위치로 마우스를 자연스럽게 이동."""
        try:
            vp = page.viewport_size or {"width": 1920, "height": 1080}
            for _ in range(random.randint(3, 6)):
                x = random.randint(100, vp["width"] - 100)
                y = random.randint(100, vp["height"] - 100)
                page.mouse.move(x, y)
                time.sleep(random.uniform(0.08, 0.3))
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    #  메인 스크래핑                                                         #
    # ------------------------------------------------------------------ #

    def scrape_google(self, query: str, limit: int = 30):
        encoded_query = urllib.parse.quote(query)
        search_url = f"https://www.google.com/search?q={encoded_query}&gl=us&hl=en"
        results = []
        xvfb_proc = None

        try:
            print(f"start crawling google with playwright for query: {query}")

            # Linux 서버: Xvfb 가상 디스플레이 위에서 headless=False 실행
            headless = True
            if self._is_linux():
                xvfb_proc = self._start_xvfb()
                if xvfb_proc:
                    os.environ["DISPLAY"] = ":99"
                    headless = False
                    print("[pw] Xvfb virtual display started on :99")
                else:
                    print("[pw] Xvfb not found, running headless")

            locale_cfg = random.choice(_LOCALES)
            ua = random.choice(_USER_AGENTS)
            width = random.randint(1800, 1920)
            height = random.randint(900, 1080)

            print(f"[pw] headless={headless}, ua={ua[:40]}..., timezone={locale_cfg['timezone']}")

            with sync_playwright() as pw:
                # 설치된 Chrome 우선 사용, 없으면 playwright 번들 Chromium 사용
                chrome_path = self._find_chrome()
                launch_kwargs = dict(
                    headless=headless,
                    args=[
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                        "--mute-audio",
                        "--disable-notifications",
                        "--disable-popup-blocking",
                        "--disable-geolocation",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-software-rasterizer",
                        "--disable-extensions",
                        "--lang=en-US",
                        f"--window-size={width},{height}",
                    ],
                )
                if chrome_path:
                    launch_kwargs["executable_path"] = chrome_path
                    print(f"[pw] Using Chrome: {chrome_path}")

                browser = pw.chromium.launch(**launch_kwargs)

                context = browser.new_context(
                    viewport={"width": width, "height": height},
                    user_agent=ua,
                    locale="en-US",
                    timezone_id=locale_cfg["timezone"],
                    geolocation=locale_cfg["geo"],
                    permissions=["geolocation"],
                    # Accept-Language 헤더 강제 설정
                    extra_http_headers={
                        "Accept-Language": "en-US,en;q=0.9",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    },
                )

                # 모든 페이지에 스텔스 스크립트 주입
                context.add_init_script(_STEALTH_JS)

                page = context.new_page()

                # 구글 홈 방문
                home_url = "https://www.google.com/?gl=us&hl=en"
                page.goto(home_url, wait_until="domcontentloaded", timeout=30000)
                time.sleep(random.uniform(1.5, 2.5))

                # 자연스러운 마우스 이동
                self._move_mouse_randomly(page)
                time.sleep(random.uniform(0.5, 1.0))

                try:
                    # 검색창 클릭 후 자연스러운 타이핑
                    page.wait_for_selector('textarea[name="q"], input[name="q"]', timeout=8000)
                    search_selector = 'textarea[name="q"]' if page.query_selector('textarea[name="q"]') else 'input[name="q"]'

                    self._human_type(page, search_selector, query)
                    time.sleep(random.uniform(0.4, 0.8))
                    page.keyboard.press("Enter")
                    self.logger.info("Typed query and pressed Enter.")

                    page.wait_for_load_state("domcontentloaded", timeout=15000)
                    time.sleep(random.uniform(2.0, 3.0))

                except Exception as e:
                    self.logger.warning(f"Homepage search failed: {e}. Falling back to direct URL.")
                    page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
                    time.sleep(random.uniform(2.0, 3.0))

                # CAPTCHA 탐지
                current_url = page.url
                if '/sorry/' in current_url:
                    self.logger.error(f"Google CAPTCHA detected! current_url={current_url}")
                    context.close()
                    browser.close()
                    return results

                # 스크롤로 lazy-load 트리거
                self._scroll_down(page, nloop=3)

                # #bres 대기
                try:
                    page.wait_for_selector("#bres", timeout=10000)
                    time.sleep(0.5)
                except PlaywrightTimeoutError:
                    self.logger.warning("Timeout waiting for #bres, using current DOM.")

                # CAPTCHA 재확인
                current_url = page.url
                if '/sorry/' in current_url:
                    self.logger.error(f"Google CAPTCHA detected! current_url={current_url}")
                    context.close()
                    browser.close()
                    return results

                html_content = page.content()
                context.close()
                browser.close()

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
            if xvfb_proc:
                xvfb_proc.terminate()
            self.logger.info(f"Scraping completed. Total results: {len(results)}")

        return results

    # ------------------------------------------------------------------ #
    #  스크롤                                                               #
    # ------------------------------------------------------------------ #

    def _scroll_down(self, page, nloop: int = 1):
        scroll_position = 0
        try:
            for _ in range(nloop):
                scroll_position += random.randint(800, 1500)
                page.evaluate(f"window.scrollTo(0, {scroll_position})")
                time.sleep(random.uniform(0.3, 0.7))
                self.logger.info(f"Scrolled to position: {scroll_position}")
        except Exception as e:
            self.logger.error(f"Error during scroll: {e}")

    # ------------------------------------------------------------------ #
    #  Chrome 경로 탐색                                                     #
    # ------------------------------------------------------------------ #

    def _find_chrome(self) -> Optional[str]:
        for path in self._CHROME_PATHS:
            if os.path.isfile(path):
                return path
        for cmd in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
            try:
                path = subprocess.check_output(
                    ["which", cmd], stderr=subprocess.DEVNULL, timeout=3
                ).decode().strip()
                if path and os.path.isfile(path):
                    return path
            except Exception:
                pass
        return None


if __name__ == '__main__':
    scraper = Scraper()
    result = scraper.scrape_google('hello')
    print(result)
