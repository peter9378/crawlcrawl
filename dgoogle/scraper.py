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
# 봇 탐지 회피를 위한 navigator/WebGL/permissions/plugins fingerprint 위장.
_STEALTH_JS = """
// navigator.webdriver 제거 — 가장 흔한 자동화 탐지 포인트
try { Object.defineProperty(navigator, 'webdriver', { get: () => undefined }); } catch(e) {}

// chrome runtime 모킹
if (!window.chrome) {
  window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){}, app: {} };
}

// plugins / mimeTypes - 일반 사용자 환경처럼
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

// 언어/하드웨어 수치들을 자연스러운 값으로
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
try { Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 }); } catch(e) {}
try { Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 }); } catch(e) {}
try { Object.defineProperty(navigator, 'maxTouchPoints', { get: () => 0 }); } catch(e) {}
try { Object.defineProperty(navigator, 'platform', { get: () => 'Linux x86_64' }); } catch(e) {}

// permissions API: notifications 쿼리 시 자동화 표식이 노출되는 케이스 우회
try {
  const _orig = window.navigator.permissions.query.bind(window.navigator.permissions);
  window.navigator.permissions.query = (p) =>
    p.name === 'notifications' ? Promise.resolve({ state: Notification.permission }) : _orig(p);
} catch(e) {}

// WebGL vendor/renderer 위장 (UNMASKED_VENDOR_WEBGL=37445, UNMASKED_RENDERER_WEBGL=37446)
try {
  const _get = WebGLRenderingContext.prototype.getParameter;
  WebGLRenderingContext.prototype.getParameter = function(p) {
    if (p === 37445) return 'Intel Inc.';
    if (p === 37446) return 'Intel Iris OpenGL Engine';
    return _get.call(this, p);
  };
} catch(e) {}
try {
  const _get2 = WebGL2RenderingContext.prototype.getParameter;
  WebGL2RenderingContext.prototype.getParameter = function(p) {
    if (p === 37445) return 'Intel Inc.';
    if (p === 37446) return 'Intel Iris OpenGL Engine';
    return _get2.call(this, p);
  };
} catch(e) {}
"""

# 의도적으로 비워둠.
# 이전에는 timezone/geolocation을 미국 도시들로 무작위 override 했었는데,
# 한국 IP에서 그렇게 하면 IP와 timezone이 mismatch 되어 봇 탐지의 강한 신호가 된다.
# 자연스러운 신호를 위해 timezone/geolocation은 OS/IP 기본값을 그대로 쓴다.
# (GCP US 리전에서 돌면 IP가 미국이므로 자연스럽게 미국 영문 결과를 받는다.)


class Scraper:
    _CHROME_PATHS = [
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
    ]

    # 모든 호출에서 동일한 fingerprint를 쓰도록 클래스 단위로 1회만 결정한다.
    # 같은 user_data_dir(영속 프로필)에 매번 다른 UA로 들어오면 봇 시그널이 된다.
    _FIXED_UA: Optional[str] = None
    _FIXED_VIEWPORT: Optional[dict] = None

    # 영속 프로필 디렉토리. 컨테이너 lifecycle 동안 cookies/local storage가 누적되어
    # Google이 "기존 사용자"로 인식 → CAPTCHA 빈도가 줄어든다.
    # 환경변수로 override 가능 (예: docker volume mount 시).
    _PROFILE_DIR = os.environ.get("DGOOGLE_PROFILE_DIR", "/tmp/dgoogle_profile")

    def __init__(self):
        self.logger = logging.getLogger('uvicorn')
        # standalone(예: python3 -c "...") 실행 시 uvicorn 로거에 핸들러가 없어
        # INFO/WARNING이 콘솔에 안 찍히는 문제가 있다. 핸들러가 없으면 stderr 핸들러를 붙인다.
        if not self.logger.handlers and not self.logger.parent.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(
                logging.Formatter("%(levelname)s:  %(message)s")
            )
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
            self.logger.propagate = False

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
                self.logger.info(
                    f"[autocomplete/suggestqueries] got {len(results)} results"
                )
                self.logger.info(
                    f"[autocomplete/suggestqueries] keywords={[r['keyword'] for r in results]}"
                )
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
                self.logger.info(
                    f"[autocomplete/chrome] keywords={[r['keyword'] for r in results]}"
                )
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

    def _paste_text(self, page, selector: str, text: str):
        """검색창에 한 번에 값을 채운다 (복사-붙여넣기 효과).

        page.fill 은 native value setter 호출 + input/change 이벤트 dispatch 까지
        처리하므로, 한 글자씩 타이핑하는 _human_type 대비 query 길이에 비례하던
        타이핑 시간을 거의 0 으로 줄일 수 있다.
        Google 홈페이지에서는 어차피 자동완성 dropdown을 보지 않고 곧바로 submit
        하기 때문에 keystroke event 가 필요 없다.
        """
        page.click(selector)
        time.sleep(random.uniform(0.1, 0.25))
        page.fill(selector, text)

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

    @staticmethod
    def _is_captcha(url: str) -> bool:
        """Google CAPTCHA / 'sorry' 인터스티셜 페이지 여부."""
        if not url:
            return False
        return "/sorry/" in url or url.startswith("https://www.google.com/sorry")

    @staticmethod
    def _safe_title(page) -> str:
        try:
            t = page.title() or ""
        except Exception:
            return "?"
        return t[:120]

    def _dump_debug_artifacts(self, page, query: str, tag: str) -> None:
        """검색창을 못 찾는 등 실패 상황에서 HTML/스크린샷을 /tmp에 저장.
        나중에 어떤 페이지가 떴는지 오프라인으로 분석할 수 있도록 한다."""
        try:
            ts = int(time.time())
            safe_query = re.sub(r"[^a-zA-Z0-9]+", "_", query)[:40]
            base = f"/tmp/dgoogle_{tag}_{safe_query}_{ts}"
            html_path = f"{base}.html"
            png_path = f"{base}.png"
            try:
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(page.content())
            except Exception as e:
                self.logger.warning(f"[browser/debug] html dump failed: {e}")
                html_path = None
            try:
                page.screenshot(path=png_path, full_page=True)
            except Exception as e:
                self.logger.warning(f"[browser/debug] screenshot failed: {e}")
                png_path = None
            self.logger.warning(
                f"[browser/debug] saved tag={tag} url={page.url} "
                f"html={html_path} png={png_path}"
            )
        except Exception as e:
            self.logger.warning(f"[browser/debug] dump completely failed: {e}")

    def _extract_searchbox_suggestions(self, page, query: str, limit: int) -> list:
        """검색 결과 페이지 검색창 클릭 후 열린 드롭다운 추천 검색어를 파싱.

        주 셀렉터는 li[data-attrid="AutocompletePrediction"]의 data-entityname 속성.
        이 속성은 <b> 강조 태그가 제거된 클린한 추천 검색어 텍스트를 담고 있다.
        """
        extraction = page.evaluate(
            """
            () => {
                // 1차: AutocompletePrediction li의 data-entityname (가장 안정적)
                const predicted = document.querySelectorAll(
                    'li[data-attrid="AutocompletePrediction"][data-entityname]'
                );
                const primary = [];
                for (const item of predicted) {
                    const name = item.getAttribute('data-entityname');
                    if (name && name.trim()) {
                        primary.push(name.trim());
                    }
                }
                if (primary.length > 0) {
                    return {source: 'data-entityname', items: primary};
                }

                // 2차 폴백: 실제 보이는 listbox 옵션의 aria-label / innerText
                const isVisible = (el) => {
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    return style.visibility !== 'hidden'
                        && style.display !== 'none'
                        && rect.width > 0
                        && rect.height > 0;
                };
                const textFrom = (el) => {
                    const labelled = el.querySelector('[aria-label]');
                    if (labelled) {
                        const aria = labelled.getAttribute('aria-label');
                        if (aria) return aria;
                    }
                    const preferred = el.querySelector('.wM6W7d span, .wM6W7d, .lnnVSe');
                    if (preferred && preferred.innerText) return preferred.innerText;
                    return el.innerText || el.textContent || '';
                };
                const fallbackSelectors = [
                    'ul[role="listbox"] li[role="option"]',
                    'ul[role="listbox"] li',
                    'div[role="listbox"] [role="option"]',
                    'li.sbct',
                ];
                for (const selector of fallbackSelectors) {
                    const items = [];
                    for (const node of document.querySelectorAll(selector)) {
                        if (!isVisible(node)) continue;
                        const text = textFrom(node);
                        if (text) items.push(text);
                    }
                    if (items.length > 0) {
                        return {source: `fallback:${selector}`, items: items};
                    }
                }
                return {source: 'none', items: []};
            }
            """
        )

        source = extraction.get("source", "none") if isinstance(extraction, dict) else "none"
        raw_suggestions = (
            extraction.get("items", []) if isinstance(extraction, dict) else []
        )
        self.logger.info(
            f"[browser/extract] source={source}, raw={len(raw_suggestions)} items"
        )
        if raw_suggestions:
            preview = [str(s)[:80] for s in raw_suggestions[: min(10, len(raw_suggestions))]]
            self.logger.info(f"[browser/extract] raw_preview={preview}")

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

        skipped_dup = 0
        skipped_ignored = 0
        for raw_text in raw_suggestions:
            lines = [
                self._normalize_suggestion_text(line)
                for line in str(raw_text).splitlines()
            ]
            picked = False
            for text in lines:
                key = text.lower()
                if not text or key in ignored or "click here" in key:
                    skipped_ignored += 1
                    continue
                if key in seen:
                    skipped_dup += 1
                    continue
                seen.add(key)
                results.append({"rank": len(results) + 1, "keyword": text})
                picked = True
                break
            if not picked and lines:
                # 모든 라인이 ignored/dup으로 걸러진 경우는 위에서 카운트됨
                pass
            if len(results) >= limit:
                break

        self.logger.info(
            f"[browser/extract] kept={len(results)}, "
            f"skipped_dup={skipped_dup}, skipped_ignored={skipped_ignored}"
        )
        return results

    def _scrape_via_browser(self, query: str, limit: int) -> list:
        """playwright로 Google 홈페이지 → 검색 → SERP 검색창 클릭 → 드롭다운 추천 파싱.

        의도적으로 직접 SERP URL로 goto하지 않는다. 직접 URL 진입은 자주 /sorry/ CAPTCHA를
        트리거하기 때문에, 항상 홈페이지에서 타이핑 후 검색 버튼 클릭으로 자연스럽게 SERP에
        진입한다. US locale + English 우선은 다음 3가지로 강제한다.
          1) /ncr (No Country Redirect) 선방문으로 google.com이 .co.kr 등으로 리다이렉트되지 않게
          2) ?gl=us&hl=en 쿼리 파라미터
          3) Accept-Language 헤더, locale="en-US"
        """
        results = []
        xvfb_proc = None

        try:
            # 가능하면 항상 headed 모드로 동작시킨다.
            # headless 환경은 navigator/WebGL/font fingerprint 등으로 봇 탐지가 강해
            # /sorry/ CAPTCHA 빈도가 훨씬 높다.
            #   - Linux: 실제 디스플레이가 없는 서버이므로 Xvfb 가상 디스플레이 위에서 headed 실행.
            #     Xvfb를 못 띄우면 어쩔 수 없이 headless로 폴백.
            #   - macOS/Windows: 디스플레이가 있으므로 그냥 headed (실제 창이 뜸).
            headless = False
            if self._is_linux():
                xvfb_proc = self._start_xvfb()
                if xvfb_proc:
                    os.environ["DISPLAY"] = ":99"
                    print("[pw] Xvfb started on :99 (headed via Xvfb)")
                else:
                    headless = True
                    print("[pw] Xvfb not found, falling back to headless")
            else:
                print("[pw] Running headed (non-Linux, native display)")

            # UA / viewport는 클래스 단위로 고정. 같은 영속 profile에서 매 요청마다
            # UA가 바뀌면 그 자체가 봇 시그널이 된다.
            if Scraper._FIXED_UA is None:
                Scraper._FIXED_UA = random.choice(_USER_AGENTS)
            if Scraper._FIXED_VIEWPORT is None:
                Scraper._FIXED_VIEWPORT = {
                    "width": random.randint(1800, 1920),
                    "height": random.randint(900, 1080),
                }
            ua = Scraper._FIXED_UA
            width = Scraper._FIXED_VIEWPORT["width"]
            height = Scraper._FIXED_VIEWPORT["height"]

            os.makedirs(self._PROFILE_DIR, exist_ok=True)

            with sync_playwright() as pw:
                chrome_path = self._find_chrome()
                # launch_persistent_context: browser와 context를 한 번에 생성하면서
                # user_data_dir(영속 profile) 사용. cookies/localStorage/cache가 누적되어
                # Google이 "기존 사용자"로 인식 → CAPTCHA 점수 ↓.
                launch_kwargs = dict(
                    user_data_dir=self._PROFILE_DIR,
                    headless=headless,
                    user_agent=ua,
                    viewport={"width": width, "height": height},
                    locale="en-US",
                    extra_http_headers={
                        "Accept-Language": "en-US,en;q=0.9",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    },
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
                        # 첫 실행 안내 / 기본 브라우저 체크 / OS keyring 접근 비활성화
                        "--no-first-run",
                        "--no-default-browser-check",
                        "--password-store=basic",
                        "--use-mock-keychain",
                        "--disable-features=IsolateOrigins,site-per-process",
                        "--lang=en-US",
                        f"--window-size={width},{height}",
                    ],
                )
                if chrome_path:
                    launch_kwargs["executable_path"] = chrome_path

                context = pw.chromium.launch_persistent_context(**launch_kwargs)
                context.add_init_script(_STEALTH_JS)
                page = (
                    context.pages[0]
                    if context.pages
                    else context.new_page()
                )

                # 1단계: 그냥 https://www.google.com 으로 접속.
                # /ncr 사전방문, ?gl=us&hl=en 파라미터 강제 등은 모두 봇 탐지 신호로 작용해서
                # /sorry/ CAPTCHA 트리거 가능성을 높인다. 단순하게 google.com 만 방문한다.
                # US locale + English 결과는 IP(가급적 GCP 미국 리전) + Accept-Language 헤더가 책임진다.
                page.goto(
                    "https://www.google.com",
                    wait_until="domcontentloaded",
                    timeout=30000,
                )
                time.sleep(random.uniform(1.5, 2.5))
                self._move_mouse_randomly(page)
                time.sleep(random.uniform(0.5, 1.0))

                if self._is_captcha(page.url):
                    self.logger.error(f"[browser] CAPTCHA on homepage: {page.url}")
                    self._dump_debug_artifacts(page, query, "captcha_home")
                    context.close()
                    return results

                self.logger.info(
                    f"[browser] home url={page.url}, title={self._safe_title(page)!r}"
                )

                # 2단계: 홈페이지에서 사람처럼 타이핑.
                try:
                    page.wait_for_selector(
                        'textarea[name="q"], input[name="q"]:not([type="hidden"])',
                        timeout=10000,
                    )
                    type_selector = (
                        'textarea[name="q"]'
                        if page.query_selector('textarea[name="q"]')
                        else 'input[name="q"]:not([type="hidden"])'
                    )
                    self._paste_text(page, type_selector, query)
                    time.sleep(random.uniform(0.4, 0.8))
                except Exception as e:
                    self.logger.error(
                        f"[browser] homepage typing failed: {e}"
                    )
                    self._dump_debug_artifacts(page, query, "no_home_input")
                    context.close()
                    return results

                # 3단계: "Google Search" 버튼 클릭으로 submit.
                #   - Enter 키는 자동화 환경에서 종종 navigation을 트리거하지 못한다.
                #   - btnK는 일반 submit 버튼이라 JS 훅과 무관하게 form 제출이 보장된다.
                #   - 홈페이지엔 btnK 버튼이 두 개(visible/hidden) 있을 수 있어 visible 한 개만 클릭.
                navigated = False
                try:
                    with page.expect_navigation(
                        wait_until="domcontentloaded", timeout=15000
                    ):
                        page.evaluate(
                            """
                            () => {
                                const btns = Array.from(document.querySelectorAll(
                                    'input[name="btnK"], button[name="btnK"]'
                                ));
                                const visible = btns.find(b => {
                                    const r = b.getBoundingClientRect();
                                    return r.width > 0 && r.height > 0;
                                });
                                if (visible) { visible.click(); return; }
                                const f = document.querySelector(
                                    'form[role="search"], form[action*="/search"]'
                                );
                                if (f) f.submit();
                            }
                            """
                        )
                    navigated = True
                except PlaywrightTimeoutError:
                    # btnK 클릭/submit으로도 안 되면 마지막 수단으로 Enter 시도
                    self.logger.warning(
                        "[browser] btnK click did not navigate, trying Enter key"
                    )
                    try:
                        with page.expect_navigation(
                            wait_until="domcontentloaded", timeout=12000
                        ):
                            page.press(type_selector, "Enter")
                        navigated = True
                    except PlaywrightTimeoutError:
                        self.logger.error(
                            "[browser] could not submit search from homepage"
                        )

                if not navigated:
                    self._dump_debug_artifacts(page, query, "no_navigation")
                    context.close()
                    return results

                time.sleep(random.uniform(1.5, 2.5))

                # 4단계: SERP 도달 검증. 직접 URL goto 폴백은 의도적으로 두지 않는다 —
                # CAPTCHA를 강하게 트리거하기 때문. SERP에 못 갔으면 깔끔히 포기.
                if self._is_captcha(page.url):
                    self.logger.error(f"[browser] CAPTCHA after submit: {page.url}")
                    self._dump_debug_artifacts(page, query, "captcha_after_submit")
                    context.close()
                    return results

                if "/search" not in page.url:
                    self.logger.error(
                        f"[browser] not on SERP after submit: url={page.url}"
                    )
                    self._dump_debug_artifacts(page, query, "no_serp")
                    context.close()
                    return results

                self.logger.info(
                    f"[browser] post-search url={page.url}, title={self._safe_title(page)!r}"
                )

                # 5단계: SERP 검색창 클릭으로 드롭다운 추천 트리거.
                # input[type="hidden"]은 CAPTCHA 토큰일 수 있으므로 명시 제외.
                clicked = False
                try:
                    page.wait_for_selector(
                        'textarea[name="q"], input[name="q"]:not([type="hidden"])',
                        timeout=10000,
                        state="attached",
                    )
                    serp_selector = (
                        'textarea[name="q"]'
                        if page.query_selector('textarea[name="q"]')
                        else 'input[name="q"]:not([type="hidden"])'
                    )
                    page.click(serp_selector, force=True)
                    clicked = True
                    time.sleep(random.uniform(0.4, 0.8))
                except PlaywrightTimeoutError:
                    self.logger.warning(
                        f"[browser] SERP search box not found within 10s on url={page.url}"
                    )
                    self._dump_debug_artifacts(page, query, "no_searchbox")
                except Exception as e:
                    self.logger.warning(f"[browser] SERP search box click failed: {e}")
                    self._dump_debug_artifacts(page, query, "click_failed")

                if not clicked:
                    self.logger.warning(
                        "[browser] giving up search box click; will still try DOM extract"
                    )

                results = self._extract_searchbox_suggestions(page, query, limit)
                self.logger.info(
                    f"[browser] dropdown suggestions: {len(results)} results"
                )
                if results:
                    keywords = [r["keyword"] for r in results]
                    self.logger.info(f"[browser] keywords={keywords}")
                else:
                    self.logger.warning(
                        f"[browser] no suggestions extracted for query={query!r}"
                    )
                context.close()

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
            self.logger.info(
                f"[scraper] browser success: {len(results)} results "
                f"keywords={[r['keyword'] for r in results]}"
            )
            return results

        # 2차: 브라우저 경로 실패 시 Autocomplete API 폴백
        self.logger.warning("[scraper] browser returned empty, falling back to autocomplete")
        results = self._scrape_via_autocomplete(query, limit)
        self.logger.info(
            f"[scraper] autocomplete fallback: {len(results)} results "
            f"keywords={[r['keyword'] for r in results]}"
        )
        return results


if __name__ == '__main__':
    scraper = Scraper()
    result = scraper.scrape_google('coupang')
    print(result)
