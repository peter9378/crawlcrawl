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

# playwright 사용 시 stealth 스크립트.
# 헤드리스/자동화 탐지에 사용되는 알려진 fingerprint 들을 일반 사용자처럼 위장한다.
# (참고: puppeteer-extra-plugin-stealth, playwright-stealth 의 핵심 패치들을 포팅)
_STEALTH_JS = r"""
(() => {
  // navigator.webdriver 제거 — 자동화 탐지 1순위
  try { Object.defineProperty(navigator, 'webdriver', { get: () => undefined }); } catch(e) {}

  // chrome.* 객체 위장 (Chromium에는 기본 존재, headless 에선 비어있음 → 봇 시그널)
  if (!window.chrome) { window.chrome = {}; }
  try {
    window.chrome.runtime = window.chrome.runtime || {
      OnInstalledReason: { CHROME_UPDATE: 'chrome_update', INSTALL: 'install', SHARED_MODULE_UPDATE: 'shared_module_update', UPDATE: 'update' },
      OnRestartRequiredReason: { APP_UPDATE: 'app_update', OS_UPDATE: 'os_update', PERIODIC: 'periodic' },
      PlatformArch: { ARM: 'arm', ARM64: 'arm64', MIPS: 'mips', MIPS64: 'mips64', X86_32: 'x86-32', X86_64: 'x86-64' },
      PlatformOs: { ANDROID: 'android', CROS: 'cros', LINUX: 'linux', MAC: 'mac', OPENBSD: 'openbsd', WIN: 'win' },
      RequestUpdateCheckStatus: { NO_UPDATE: 'no_update', THROTTLED: 'throttled', UPDATE_AVAILABLE: 'update_available' }
    };
    window.chrome.app = window.chrome.app || { isInstalled: false, InstallState: { DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' }, RunningState: { CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' } };
    window.chrome.loadTimes = window.chrome.loadTimes || function(){ return { commitLoadTime: 0, connectionInfo: 'http/1.1', finishDocumentLoadTime: 0, finishLoadTime: 0, firstPaintAfterLoadTime: 0, firstPaintTime: 0, navigationType: 'Other', npnNegotiatedProtocol: 'unknown', requestTime: 0, startLoadTime: 0, wasAlternateProtocolAvailable: false, wasFetchedViaSpdy: false, wasNpnNegotiated: false }; };
    window.chrome.csi = window.chrome.csi || function(){ return { onloadT: Date.now(), pageT: 0, startE: Date.now(), tran: 15 }; };
  } catch(e) {}

  // plugins / mimeTypes 일반 사용자 환경처럼
  try {
    Object.defineProperty(navigator, 'plugins', {
      get: () => {
        const arr = [
          { name: 'PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
          { name: 'Chrome PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
          { name: 'Chromium PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
          { name: 'Microsoft Edge PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
          { name: 'WebKit built-in PDF', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
        ];
        arr.__proto__ = PluginArray.prototype;
        return arr;
      }
    });
  } catch(e) {}

  // 언어/하드웨어 수치를 자연스러운 값으로
  try { Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] }); } catch(e) {}
  try { Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 }); } catch(e) {}
  try { Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 }); } catch(e) {}
  try { Object.defineProperty(navigator, 'maxTouchPoints', { get: () => 0 }); } catch(e) {}
  try { Object.defineProperty(navigator, 'platform', { get: () => 'Linux x86_64' }); } catch(e) {}

  // permissions API: 'notifications' 쿼리 시 prompt/denied 일관성 유지
  try {
    const _orig = window.navigator.permissions.query.bind(window.navigator.permissions);
    window.navigator.permissions.query = (p) =>
      p && p.name === 'notifications'
        ? Promise.resolve({ state: Notification.permission })
        : _orig(p);
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

  // Battery API — headless 환경에서 비어있는 케이스 위장
  try {
    if (!navigator.getBattery) {
      Object.defineProperty(navigator, 'getBattery', {
        value: () => Promise.resolve({ charging: true, chargingTime: 0, dischargingTime: Infinity, level: 1, addEventListener: () => {}, removeEventListener: () => {} })
      });
    }
  } catch(e) {}

  // Network connection — headless 에서 종종 undefined
  try {
    if (!navigator.connection) {
      Object.defineProperty(navigator, 'connection', {
        get: () => ({ downlink: 10, effectiveType: '4g', rtt: 50, saveData: false, type: 'wifi' })
      });
    }
  } catch(e) {}

  // iframe contentWindow 자동화 탐지 우회
  try {
    const desc = Object.getOwnPropertyDescriptor(HTMLIFrameElement.prototype, 'contentWindow');
    if (desc && desc.get) {
      Object.defineProperty(HTMLIFrameElement.prototype, 'contentWindow', {
        get: function() {
          const w = desc.get.call(this);
          try { Object.defineProperty(w.navigator, 'webdriver', { get: () => undefined }); } catch(e) {}
          return w;
        }
      });
    }
  } catch(e) {}

  // Notification.permission 일관성 (granted 가 자동화 시그널이 되는 경우가 있음)
  try {
    if (Notification && Notification.permission === 'denied') {
      Object.defineProperty(Notification, 'permission', { get: () => 'default' });
    }
  } catch(e) {}

  // outerWidth / outerHeight — headless 에서 0 인 경우가 있음
  try {
    if (window.outerWidth === 0) {
      Object.defineProperty(window, 'outerWidth', { get: () => window.innerWidth });
      Object.defineProperty(window, 'outerHeight', { get: () => window.innerHeight });
    }
  } catch(e) {}
})();
"""

# 의도적으로 비워둠.
# 이전에는 timezone/geolocation을 미국 도시들로 무작위 override 했었는데,
# 한국 IP에서 그렇게 하면 IP와 timezone이 mismatch 되어 봇 탐지의 강한 신호가 된다.
# 자연스러운 신호를 위해 timezone/geolocation은 OS/IP 기본값을 그대로 쓴다.
# (GCP US 리전에서 돌면 IP가 미국이므로 자연스럽게 미국 영문 결과를 받는다.)


class Scraper:
    _CHROME_PATHS = [
        # google-chrome-stable .deb 가 설치하는 실제 바이너리. /usr/bin/google-chrome
        # 심볼릭 링크가 alternatives 시스템 누락 등으로 안 만들어지는 경우에도 매칭된다.
        "/opt/google/chrome/google-chrome",
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

    # 워밍업 marker 파일. profile 에 워밍업 흔적이 없으면 첫 호출 시 자연스러운
    # 사용자 세션을 흉내내 google.com 에 잠시 머무르고 더미 검색을 한 번 실행한다.
    # 이렇게 만들어진 NID/SID/AEC 등 cookie 들이 이후 본 검색에서 봇 점수를 낮춘다.
    _WARMUP_MARKER = "warmup_done"

    # 워밍업이 CAPTCHA 로 막힌 시점. 한번 막혔으면 일정 시간 동안 다시 시도하지 않는다
    # (반복 시도해 봐야 같은 IP 평판이라 또 CAPTCHA, 시간만 낭비).
    _warmup_blocked_until: float = 0.0
    _WARMUP_BLOCK_SECONDS = 300.0  # 5분

    # CAPTCHA 가 한 번 잡히면 같은 호출 안에서의 retry 도 스킵 (의미 없음).
    _captcha_blocked_until: float = 0.0
    _CAPTCHA_BLOCK_SECONDS = 60.0  # 1분

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

    def _warmup_if_needed(self, page) -> None:
        """profile 디렉토리에 warmup marker 가 없으면 자연스러운 첫 세션을 흉내낸다.

        목적: 빈 cookie jar 상태에서 곧바로 검색을 시도하면 Google 이 "이 IP의 새 익명
        사용자가 갑자기 검색"하는 패턴으로 인식해 CAPTCHA 점수를 높인다. 따라서 첫 컨테
        이너 호출에서:
          1) google.com 에 진입해서 약간 머무르고 (마우스 움직임)
          2) 평범한 더미 검색 ('weather' 등) 을 한 번 정상 수행
          3) marker 파일을 남겨 다음 호출부터는 skip
        이렇게 하면 NID/SID/AEC 같은 cookie 가 정상 흐름으로 누적되고
        Google 입장에서는 "기존 활동 사용자가 다음 검색을 하는" 자연스러운 패턴이 된다.
        """
        marker_path = os.path.join(self._PROFILE_DIR, self._WARMUP_MARKER)
        if os.path.exists(marker_path):
            return

        # 직전에 워밍업이 CAPTCHA 로 막혔으면 cooldown 동안 skip.
        if time.time() < Scraper._warmup_blocked_until:
            self.logger.info(
                "[browser] warmup skipped (recently blocked by CAPTCHA, "
                f"cooldown {Scraper._warmup_blocked_until - time.time():.0f}s)"
            )
            return

        self.logger.info("[browser] warmup: profile is fresh, doing a natural first session")
        try:
            page.goto(
                "https://www.google.com",
                wait_until="domcontentloaded",
                timeout=30000,
            )
            time.sleep(random.uniform(2.0, 3.5))
            self._move_mouse_randomly(page)
            time.sleep(random.uniform(0.8, 1.6))

            if self._is_captcha(page.url):
                self.logger.warning(
                    "[browser] warmup: CAPTCHA on home, attempting CapSolver"
                )
                if not self._solve_captcha(page) or self._is_captcha(page.url):
                    self.logger.warning(
                        "[browser] warmup home CAPTCHA solve failed; cooldown"
                    )
                    Scraper._warmup_blocked_until = (
                        time.time() + self._WARMUP_BLOCK_SECONDS
                    )
                    return

            try:
                page.wait_for_selector(
                    'textarea[name="q"], input[name="q"]:not([type="hidden"])',
                    timeout=8000,
                )
                sel = (
                    'textarea[name="q"]'
                    if page.query_selector('textarea[name="q"]')
                    else 'input[name="q"]:not([type="hidden"])'
                )
                self._paste_text(page, sel, "weather today")
                time.sleep(random.uniform(0.5, 1.0))
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
                time.sleep(random.uniform(2.0, 3.0))
                if self._is_captcha(page.url):
                    self.logger.warning(
                        f"[browser] warmup CAPTCHA after submit ({page.url}); "
                        "attempting CapSolver"
                    )
                    if not self._solve_captcha(page) or self._is_captcha(page.url):
                        self.logger.warning(
                            "[browser] warmup CAPTCHA solve failed; cooldown"
                        )
                        Scraper._warmup_blocked_until = (
                            time.time() + self._WARMUP_BLOCK_SECONDS
                        )
                        return
                # 짧게 머무르며 사용자 같은 행동
                self._move_mouse_randomly(page)
                time.sleep(random.uniform(1.0, 2.0))
            except Exception as e:
                self.logger.warning(f"[browser] warmup search failed: {e}")
                return

            # 워밍업 성공 → marker 작성
            try:
                with open(marker_path, "w") as f:
                    f.write(str(int(time.time())))
                self.logger.info("[browser] warmup completed and marker saved")
            except Exception as e:
                self.logger.warning(f"[browser] failed to write warmup marker: {e}")

        except Exception as e:
            self.logger.warning(f"[browser] warmup phase failed: {e}")

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

    def _solve_captcha(self, page) -> bool:
        """CapSolver 로 Google /sorry/ 페이지의 reCAPTCHA 를 풀고 통과시킨다.

        흐름:
          1) 환경변수 CAPSOLVER_API_KEY 확인 (없으면 false 반환)
          2) 페이지에서 reCAPTCHA sitekey 추출 ([data-sitekey] 또는 iframe src 의 k= 파라미터)
          3) CapSolver API 에 ReCaptchaV2TaskProxyless 작업 등록 → token 수신
             (실패 시 ReCaptchaV2EnterpriseTaskProxyless 로 한 번 더 시도)
          4) 페이지의 textarea[name=g-recaptcha-response] 에 token 주입
          5) 등록된 reCAPTCHA callback 이 있으면 호출, 없으면 form.submit()
          6) navigation 후 url 이 /sorry/ 가 아니면 통과 성공
        성공 시 True, 실패 시 False.
        """
        api_key = os.environ.get("CAPSOLVER_API_KEY")
        if not api_key:
            self.logger.error(
                "[captcha] CAPSOLVER_API_KEY env not set — cannot solve captcha. "
                "Set it on the container, e.g. -e CAPSOLVER_API_KEY=CAP-xxx"
            )
            return False

        try:
            import capsolver  # type: ignore  # noqa: I001
        except Exception as e:
            self.logger.error(f"[captcha] capsolver package not available: {e}")
            return False
        capsolver.api_key = api_key

        sorry_url = page.url
        try:
            sitekey = page.evaluate(
                """
                () => {
                    const direct = document.querySelector('[data-sitekey]');
                    if (direct) {
                        const k = direct.getAttribute('data-sitekey');
                        if (k) return k;
                    }
                    const iframes = Array.from(document.querySelectorAll('iframe'));
                    for (const f of iframes) {
                        const src = f.src || '';
                        const m = src.match(/[?&]k=([^&]+)/);
                        if (m) return m[1];
                    }
                    return null;
                }
                """
            )
        except Exception as e:
            self.logger.error(f"[captcha] sitekey extraction failed: {e}")
            return False

        if not sitekey:
            self.logger.error(
                f"[captcha] no recaptcha sitekey on page url={sorry_url}"
            )
            return False
        self.logger.info(
            f"[captcha] solving via CapSolver, sitekey={sitekey[:10]}..., url={sorry_url}"
        )

        token: Optional[str] = None
        last_err: Optional[str] = None
        for task_type in (
            "ReCaptchaV2TaskProxyless",
            "ReCaptchaV2EnterpriseTaskProxyless",
        ):
            try:
                solution = capsolver.solve(
                    {
                        "type": task_type,
                        "websiteURL": sorry_url,
                        "websiteKey": sitekey,
                    }
                )
                token = (
                    solution.get("gRecaptchaResponse")
                    if isinstance(solution, dict)
                    else None
                )
                if token:
                    self.logger.info(
                        f"[captcha] CapSolver returned token via {task_type} (len={len(token)})"
                    )
                    break
                last_err = f"{task_type}: empty token in response={solution}"
            except Exception as e:
                last_err = f"{task_type}: {e}"
                self.logger.warning(f"[captcha] {task_type} failed: {e}")

        if not token:
            self.logger.error(f"[captcha] CapSolver failed — last_err={last_err}")
            return False

        # 토큰 주입 + 폼 제출
        try:
            page.evaluate(
                """
                (token) => {
                    document.querySelectorAll('textarea[name="g-recaptcha-response"]').forEach(t => {
                        t.style.display = '';
                        t.value = token;
                        t.innerText = token;
                    });
                    // 이름이 다른 fallback (g-recaptcha-response-XX 등)
                    document.querySelectorAll('textarea[name^="g-recaptcha-response"]').forEach(t => {
                        t.value = token;
                    });
                    // 등록된 reCAPTCHA callback 호출 (있으면)
                    try {
                        if (typeof ___grecaptcha_cfg !== 'undefined' && ___grecaptcha_cfg.clients) {
                            for (const client of Object.values(___grecaptcha_cfg.clients)) {
                                for (const item of Object.values(client)) {
                                    if (item && typeof item === 'object') {
                                        for (const v of Object.values(item)) {
                                            if (v && typeof v === 'object' && typeof v.callback === 'function') {
                                                try { v.callback(token); } catch(e) {}
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    } catch(e) {}
                }
                """,
                token,
            )
            # callback 이 navigation 을 트리거하지 않는 경우 form.submit() 으로 강제 제출
            try:
                with page.expect_navigation(
                    wait_until="domcontentloaded", timeout=15000
                ):
                    page.evaluate(
                        """
                        () => {
                            const f = document.querySelector('form');
                            if (f) f.submit();
                        }
                        """
                    )
            except PlaywrightTimeoutError:
                # callback 이 이미 navigation 시킨 경우엔 이 wait 가 timeout 됨 — OK
                pass

            time.sleep(random.uniform(1.5, 2.5))
            if self._is_captcha(page.url):
                self.logger.error(
                    f"[captcha] still on /sorry/ after token submission: {page.url}"
                )
                return False
            self.logger.info(f"[captcha] solved, redirected to {page.url}")
            return True
        except Exception as e:
            self.logger.error(f"[captcha] token submission failed: {e}")
            return False

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
                        # Client Hints 헤더 — 실제 Chrome 이 보내는 값을 명시해서 헤더 누락이 봇 시그널이 되지 않게.
                        "sec-ch-ua": '"Chromium";v="135", "Not-A.Brand";v="24", "Google Chrome";v="135"',
                        "sec-ch-ua-mobile": "?0",
                        "sec-ch-ua-platform": '"Linux"',
                    },
                    # playwright 가 기본으로 추가하는 --enable-automation 플래그를 제거.
                    # 이 플래그는 Chrome 의 navigator.webdriver=true 를 강제하고 자동화 광고 신호가 된다.
                    ignore_default_args=["--enable-automation"],
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
                        "--no-first-run",
                        "--no-default-browser-check",
                        "--password-store=basic",
                        "--use-mock-keychain",
                        "--disable-features=IsolateOrigins,site-per-process",
                        "--lang=en-US",
                        f"--window-size={width},{height}",
                    ],
                )

                # Proxy 환경변수 hook — DGOOGLE_PROXY_SERVER 가 설정돼 있으면 사용.
                # 예: DGOOGLE_PROXY_SERVER=http://scraperapi:KEY@proxy.scraperapi.com:8001
                # ScraperAPI / Zyte / BrightData 같은 residential proxy 도입 시 코드 수정 없이 켤 수 있다.
                proxy_server = os.environ.get("DGOOGLE_PROXY_SERVER")
                if proxy_server:
                    proxy_cfg = {"server": proxy_server}
                    if os.environ.get("DGOOGLE_PROXY_USERNAME"):
                        proxy_cfg["username"] = os.environ["DGOOGLE_PROXY_USERNAME"]
                    if os.environ.get("DGOOGLE_PROXY_PASSWORD"):
                        proxy_cfg["password"] = os.environ["DGOOGLE_PROXY_PASSWORD"]
                    launch_kwargs["proxy"] = proxy_cfg
                    self.logger.info(f"[browser] using proxy: {proxy_server}")

                if chrome_path:
                    launch_kwargs["executable_path"] = chrome_path

                context = pw.chromium.launch_persistent_context(**launch_kwargs)
                context.add_init_script(_STEALTH_JS)
                page = (
                    context.pages[0]
                    if context.pages
                    else context.new_page()
                )

                # 0단계: 영속 profile 이 fresh 한 경우(=NID/SID 등 cookie 미 누적) 자연스러운
                # 첫 세션을 흉내내 cookie 평판을 만든 뒤 본 검색에 들어간다.
                # 두 번째 호출부터는 marker 가 있어 즉시 통과.
                self._warmup_if_needed(page)

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

                # 4단계: SERP 도달 검증.
                # CAPTCHA 면 CapSolver 로 풀어 통과 시도. 실패해도 직접 URL fallback 은 두지 않는다.
                if self._is_captcha(page.url):
                    self.logger.warning(
                        f"[browser] CAPTCHA after submit: {page.url}, attempting CapSolver"
                    )
                    self._dump_debug_artifacts(page, query, "captcha_before_solve")
                    if self._solve_captcha(page):
                        # 풀이 성공: redirect 가 SERP 가 아닐 수도 있어(다시 홈 등) 한 번 더 검증
                        time.sleep(random.uniform(1.0, 2.0))
                        if self._is_captcha(page.url):
                            self.logger.error(
                                f"[browser] solve returned True but still CAPTCHA: {page.url}"
                            )
                            Scraper._captcha_blocked_until = (
                                time.time() + self._CAPTCHA_BLOCK_SECONDS
                            )
                            context.close()
                            return results
                        self.logger.info(
                            f"[browser] CAPTCHA solved, post-solve url={page.url}"
                        )
                    else:
                        self.logger.error("[browser] CapSolver could not solve CAPTCHA")
                        self._dump_debug_artifacts(page, query, "captcha_solve_failed")
                        Scraper._captcha_blocked_until = (
                            time.time() + self._CAPTCHA_BLOCK_SECONDS
                        )
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
                # 단순 click 보다 hover→click 시퀀스가 자연스러우며 dropdown 트리거도 더 안정적.
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
                    locator = page.locator(serp_selector).first
                    try:
                        locator.scroll_into_view_if_needed(timeout=2000)
                    except Exception:
                        pass
                    try:
                        locator.hover(timeout=2000)
                        time.sleep(random.uniform(0.15, 0.35))
                    except Exception:
                        pass
                    locator.click(force=True, timeout=5000)
                    clicked = True

                    # dropdown listbox 가 attached 될 때까지 최대 1.5s 대기.
                    # 사용자 피드백상 단순 sleep 0.4-0.8s 만으로 dropdown 이 늦게 떠 놓치는 케이스가 있음.
                    try:
                        page.wait_for_selector(
                            'ul[role="listbox"], div[role="listbox"], '
                            'li[data-attrid="AutocompletePrediction"]',
                            timeout=1500,
                            state="attached",
                        )
                        self.logger.info("[browser] dropdown listbox attached")
                    except PlaywrightTimeoutError:
                        self.logger.warning(
                            "[browser] dropdown listbox not attached within 1.5s; "
                            "will still try DOM extract"
                        )
                    # 추가 안정 대기 (애니메이션 후 텍스트 fully rendered 까지)
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
        """SERP dropdown 추천어를 브라우저로 수집한다.

        autocomplete API fallback 은 의도적으로 호출하지 않는다 — SERP dropdown 과
        본질이 다른 데이터(단순 자동완성 추천)라 사용자 요구사항을 만족시키지 못한다.
        CAPTCHA 가 발동하면 CAPSOLVER_API_KEY 가 설정된 경우 CapSolver 로 풀이를 시도한다.
        풀이도 실패하면 빈 리스트를 반환한다 (잘못된 데이터를 주느니 빈 응답이 낫다).
        """
        print(f"[scraper] query={query}, limit={limit}")

        if time.time() < Scraper._captcha_blocked_until:
            cd = Scraper._captcha_blocked_until - time.time()
            self.logger.warning(
                f"[scraper] CAPTCHA cooldown active ({cd:.0f}s left), returning empty"
            )
            return []

        # 1차: 브라우저로 SERP dropdown 추천 수집.
        # CAPTCHA 가 잡히면 _scrape_via_browser 안에서 CapSolver 로 자동 풀이 시도.
        # 실패 시 cooldown 마커가 켜져 두 번째 attempt 는 자동 skip 된다.
        for attempt in (1, 2):
            results = self._scrape_via_browser(query, limit)
            if results:
                self.logger.info(
                    f"[scraper] browser success (attempt {attempt}): {len(results)} results "
                    f"keywords={[r['keyword'] for r in results]}"
                )
                return results
            if attempt == 1 and time.time() >= Scraper._captcha_blocked_until:
                backoff = random.uniform(5.0, 8.0)
                self.logger.warning(
                    f"[scraper] browser attempt 1 returned empty, retrying after {backoff:.1f}s"
                )
                time.sleep(backoff)
            else:
                break

        self.logger.error(
            "[scraper] browser path failed (CAPTCHA solve failed or extraction empty); "
            "returning empty list. Set CAPSOLVER_API_KEY env if not already, or check "
            "docker logs for [captcha] entries to diagnose."
        )
        return []


if __name__ == '__main__':
    scraper = Scraper()
    result = scraper.scrape_google('coupang')
    print(result)
