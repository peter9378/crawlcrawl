import logging
import json
import os
import re
import sys
from typing import Optional
import subprocess
import requests
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import urllib.parse
import traceback
import time
import random


_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
]

# playwright 사용 시 stealth 스크립트
_STEALTH_JS = """
if (!window.chrome) {
  window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){}, app: {} };
}
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
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
try {
  const _orig = window.navigator.permissions.query.bind(window.navigator.permissions);
  window.navigator.permissions.query = (p) =>
    p.name === 'notifications' ? Promise.resolve({ state: Notification.permission }) : _orig(p);
} catch(e) {}
try {
  const _get = WebGLRenderingContext.prototype.getParameter;
  WebGLRenderingContext.prototype.getParameter = function(p) {
    if (p === 37445) return 'Intel Inc.';
    if (p === 37446) return 'Intel Iris OpenGL Engine';
    return _get.call(this, p);
  };
} catch(e) {}
"""

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
    #  Fallback: Google Autocomplete API (HTTP only, no browser, no CAPTCHA)
    # ------------------------------------------------------------------ #

    def _scrape_via_autocomplete(self, query: str, limit: int) -> list:
        """
        Google의 공개 Autocomplete API를 사용.
        브라우저 없이 일반 HTTP 요청으로 동작하므로 GCP IP에서도 CAPTCHA 없이 사용 가능.
        엔드포인트 1: suggestqueries (안정적, 범용)
        엔드포인트 2: gws-wiz (더 많은 제안, 파싱 필요)
        """
        encoded_query = urllib.parse.quote(query)
        ua = random.choice(_USER_AGENTS)
        headers = {
            "User-Agent": ua,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.google.com/",
        }

        # 엔드포인트 1: suggestqueries (Firefox client — JSON 배열 반환)
        url1 = (
            f"https://suggestqueries.google.com/complete/search"
            f"?client=firefox&q={encoded_query}&hl=en&gl=us"
        )
        try:
            resp = requests.get(url1, headers=headers, timeout=10)
            resp.raise_for_status()
            data = json.loads(resp.text)
            # 형식: ["query", ["sug1", "sug2", ...], ...]
            suggestions = data[1] if len(data) > 1 else []
            if suggestions:
                results = [
                    {"rank": i + 1, "keyword": s}
                    for i, s in enumerate(suggestions[:limit])
                ]
                self.logger.info(f"[autocomplete/suggestqueries] got {len(results)} results")
                return results
        except Exception as e:
            self.logger.warning(f"[autocomplete/suggestqueries] failed: {e}")

        # 엔드포인트 2: chrome-omni (JSON 배열 반환, 더 다양한 제안)
        url2 = (
            f"https://suggestqueries.google.com/complete/search"
            f"?client=chrome&q={encoded_query}&hl=en&gl=us"
        )
        try:
            resp = requests.get(url2, headers=headers, timeout=10)
            resp.raise_for_status()
            data = json.loads(resp.text)
            suggestions = data[1] if len(data) > 1 else []
            if suggestions:
                results = [
                    {"rank": i + 1, "keyword": s}
                    for i, s in enumerate(suggestions[:limit])
                ]
                self.logger.info(f"[autocomplete/chrome] got {len(results)} results")
                return results
        except Exception as e:
            self.logger.warning(f"[autocomplete/chrome] failed: {e}")

        return []

    # ------------------------------------------------------------------ #
    #  Primary: playwright 브라우저                                       #
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

    def _human_type(self, page, selector: str, text: str):
        page.click(selector)
        time.sleep(random.uniform(0.2, 0.5))
        for char in text:
            page.keyboard.type(char)
            time.sleep(random.uniform(0.04, 0.16))

    def _move_mouse_randomly(self, page):
        try:
            vp = page.viewport_size or {"width": 1920, "height": 1080}
            for _ in range(random.randint(3, 6)):
                x = random.randint(100, vp["width"] - 100)
                y = random.randint(100, vp["height"] - 100)
                page.mouse.move(x, y)
                time.sleep(random.uniform(0.08, 0.3))
        except Exception:
            pass

    def _normalize_suggestion_text(self, text: str) -> str:
        text = re.sub(r"\s+", " ", text or "").strip()
        text = re.sub(r"\s*(?:Remove|삭제|검색어 삭제)\s*$", "", text, flags=re.IGNORECASE)
        return text.strip()

    def _extract_searchbox_suggestions(self, page, query: str, limit: int) -> list:
        """검색 결과 페이지 검색창 클릭 후 열린 드롭다운 추천 검색어를 파싱."""
        raw_suggestions = page.evaluate(
            """
            () => {
                const isVisible = (el) => {
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    return style.visibility !== 'hidden'
                        && style.display !== 'none'
                        && rect.width > 0
                        && rect.height > 0;
                };
                const textFrom = (el) => {
                    const preferred = el.querySelector(
                        '.wM6W7d span, .wM6W7d, .lnnVSe, [role="option"] span'
                    );
                    if (preferred && preferred.innerText) {
                        return preferred.innerText;
                    }
                    const aria = el.getAttribute('aria-label');
                    if (aria) {
                        return aria;
                    }
                    return el.innerText || el.textContent || '';
                };
                const selectors = [
                    'ul[role="listbox"] li',
                    'div[role="listbox"] [role="option"]',
                    'div[role="option"]',
                    'li.sbct',
                    '.aajZCb li',
                    '.erkvQe li',
                    '.wM6W7d'
                ];
                const nodes = [];
                for (const selector of selectors) {
                    for (const node of document.querySelectorAll(selector)) {
                        if (isVisible(node)) {
                            nodes.push(node);
                        }
                    }
                }
                return nodes.map(textFrom).filter(Boolean);
            }
            """
        )

        results = []
        seen = set()
        ignored = {
            "",
            query.lower(),
            "google search",
            "i'm feeling lucky",
            "search",
            "remove",
        }

        for raw_text in raw_suggestions:
            lines = [
                self._normalize_suggestion_text(line)
                for line in str(raw_text).splitlines()
            ]
            for text in lines:
                key = text.lower()
                if not text or key in ignored or "click here" in key:
                    continue
                if key not in seen:
                    seen.add(key)
                    results.append({"rank": len(results) + 1, "keyword": text})
                    break
            if len(results) >= limit:
                break

        return results

    def _scrape_via_browser(self, query: str, limit: int) -> list:
        """playwright로 Google 검색 후 검색창 드롭다운 추천 검색어를 파싱."""
        encoded_query = urllib.parse.quote(query)
        search_url = f"https://www.google.com/search?q={encoded_query}&gl=us&hl=en"
        results = []
        xvfb_proc = None

        try:
            headless = True
            if self._is_linux():
                xvfb_proc = self._start_xvfb()
                if xvfb_proc:
                    os.environ["DISPLAY"] = ":99"
                    headless = False
                    print("[pw] Xvfb started on :99")
                else:
                    print("[pw] Xvfb not found, running headless")

            locale_cfg = random.choice(_LOCALES)
            ua = random.choice(_USER_AGENTS)
            width = random.randint(1800, 1920)
            height = random.randint(900, 1080)

            with sync_playwright() as pw:
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

                browser = pw.chromium.launch(**launch_kwargs)
                context = browser.new_context(
                    viewport={"width": width, "height": height},
                    user_agent=ua,
                    locale="en-US",
                    timezone_id=locale_cfg["timezone"],
                    geolocation=locale_cfg["geo"],
                    permissions=["geolocation"],
                    extra_http_headers={
                        "Accept-Language": "en-US,en;q=0.9",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    },
                )
                context.add_init_script(_STEALTH_JS)
                page = context.new_page()

                page.goto("https://www.google.com/?gl=us&hl=en", wait_until="domcontentloaded", timeout=30000)
                time.sleep(random.uniform(1.5, 2.5))
                self._move_mouse_randomly(page)
                time.sleep(random.uniform(0.5, 1.0))

                try:
                    page.wait_for_selector('textarea[name="q"], input[name="q"]', timeout=8000)
                    search_selector = (
                        'textarea[name="q"]'
                        if page.query_selector('textarea[name="q"]')
                        else 'input[name="q"]'
                    )
                    self._human_type(page, search_selector, query)
                    time.sleep(random.uniform(0.4, 0.8))
                    page.keyboard.press("Enter")
                    page.wait_for_load_state("domcontentloaded", timeout=15000)
                    time.sleep(random.uniform(2.0, 3.0))
                except Exception as e:
                    self.logger.warning(f"[browser] search input failed: {e}. Using direct URL.")
                    page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
                    time.sleep(random.uniform(2.0, 3.0))

                if '/sorry/' in page.url:
                    self.logger.error(f"[browser] CAPTCHA detected: {page.url}")
                    context.close()
                    browser.close()
                    return results

                try:
                    page.wait_for_selector('textarea[name="q"], input[name="q"]', timeout=10000)
                    search_selector = (
                        'textarea[name="q"]'
                        if page.query_selector('textarea[name="q"]')
                        else 'input[name="q"]'
                    )
                    page.click(search_selector)
                    time.sleep(random.uniform(0.8, 1.4))
                    page.wait_for_selector(
                        'ul[role="listbox"], div[role="listbox"], div[role="option"], li.sbct, .aajZCb',
                        timeout=8000,
                    )
                except PlaywrightTimeoutError:
                    self.logger.warning("[browser] suggestion dropdown timeout, using current DOM.")
                except Exception as e:
                    self.logger.warning(f"[browser] suggestion dropdown failed: {e}")

                results = self._extract_searchbox_suggestions(page, query, limit)
                self.logger.info(f"[browser] dropdown suggestions: {len(results)} results")
                context.close()
                browser.close()

        except Exception as e:
            self.logger.error(f'[browser] Unexpected error: {str(e)}')
            self.logger.error(traceback.format_exc())
        finally:
            if xvfb_proc:
                xvfb_proc.terminate()

        return results

    def _scroll_down(self, page, nloop: int = 1):
        scroll_position = 0
        try:
            for _ in range(nloop):
                scroll_position += random.randint(800, 1500)
                page.evaluate(f"window.scrollTo(0, {scroll_position})")
                time.sleep(random.uniform(0.3, 0.7))
        except Exception as e:
            self.logger.error(f"[scroll] {e}")

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def scrape_google(self, query: str, limit: int = 30) -> list:
        print(f"[scraper] query={query}, limit={limit}")

        # 1차: 실제 Google 검색 페이지에서 검색창 드롭다운 추천어 수집
        results = self._scrape_via_browser(query, limit)
        if results:
            self.logger.info(f"[scraper] browser success: {len(results)} results")
            return results

        # 2차: 브라우저 경로 실패 시 Autocomplete API 폴백
        self.logger.warning("[scraper] browser returned empty, falling back to autocomplete")
        results = self._scrape_via_autocomplete(query, limit)
        self.logger.info(f"[scraper] autocomplete fallback: {len(results)} results")
        return results


if __name__ == '__main__':
    scraper = Scraper()
    result = scraper.scrape_google('coupang')
    print(result)
