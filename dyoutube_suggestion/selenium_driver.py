from selenium import webdriver
from selenium.webdriver import ChromeOptions
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import (
    WebDriverException,
    TimeoutException,
    SessionNotCreatedException
)
import time
import os
import traceback
import logging

CHROMEDRIVER_PATH = os.environ.get('CHROMEDRIVER_PATH', '/usr/local/bin/chromedriver')
YOUTUBE_HOSTS = ("www.youtube.com", "youtube.com", "m.youtube.com")


def _chrome_service() -> Service:
    if os.path.isfile(CHROMEDRIVER_PATH):
        return Service(executable_path=CHROMEDRIVER_PATH)
    return Service()


class SeleniumDriver:
    # 페이지 로드 타임아웃 (초)
    PAGE_LOAD_TIMEOUT = int(os.environ.get('SELENIUM_PAGE_LOAD_TIMEOUT', '25'))
    # 스크립트 실행 타임아웃 (초)
    SCRIPT_TIMEOUT = int(os.environ.get('SELENIUM_SCRIPT_TIMEOUT', '10'))
    # 명시적 페이지 준비 대기 시간 (초)
    DOCUMENT_READY_TIMEOUT = float(os.environ.get('SELENIUM_DOCUMENT_READY_TIMEOUT', '6'))
    # URL 전환 후 동적 DOM이 채워질 최소 대기 시간 (초)
    PAGE_STABILIZE_DELAY = float(os.environ.get('SELENIUM_PAGE_STABILIZE_DELAY', '1.5'))
    # YouTube 앱 shell이 렌더링될 때까지 기다리는 시간 (초)
    YOUTUBE_INTERACTIVE_TIMEOUT = float(os.environ.get('SELENIUM_YOUTUBE_INTERACTIVE_TIMEOUT', '30'))
    # 네트워크/DNS 일시 실패 시 URL 로드 재시도 횟수
    NAVIGATION_RETRIES = int(os.environ.get('SELENIUM_NAVIGATION_RETRIES', '2'))
    NAVIGATION_RETRY_DELAY = float(os.environ.get('SELENIUM_NAVIGATION_RETRY_DELAY', '2.0'))
    # 빈 문서로 간주할 최소 HTML 길이
    MIN_PAGE_SOURCE_LENGTH = 100
    # 암묵적 대기 시간 (초)
    IMPLICIT_WAIT = 10
    
    def __init__(self, start_url='about:blank'):
        self.driver = None
        self.start_url = start_url
        self.logger = logging.getLogger('uvicorn')
        self.options = self._get_options()

    def _get_options(self):
        options = ChromeOptions()
        options.add_argument('--headless')
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-sync')
        #options.add_argument('--disable-background-networking')
        options.add_argument('--safebrowsing-disable-auto-update')
        options.add_argument('--disable-domain-reliability')
        options.add_argument('--disable-component-extensions-with-background-pages')
        options.add_argument('--incognito')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-notifications')
        options.add_argument('--disable-popup-blocking')
        options.add_argument('--disable-translate')
        #options.add_argument('--disable-background-timer-throttling')
        options.add_argument('--disable-renderer-backgrounding')
        options.add_argument('--disable-device-discovery-notifications')
        options.add_argument('--mute-audio')
        options.add_argument('--blink-settings=imagesEnabled=false')  # Disable images
        options.add_argument('--disable-features=SearchProviderFirstRun')
        options.add_argument('--disable-geolocation')
        options.add_argument('--disable-quic')
        options.add_argument('--dns-prefetch-disable')
        host_resolver_rules = self._build_host_resolver_rules()
        if host_resolver_rules:
            options.add_argument(f'--host-resolver-rules={host_resolver_rules}')
            self.logger.info(f"[SELENIUM] Applying Chrome host resolver rules: {host_resolver_rules}")
        options.page_load_strategy = 'eager'
        
        prefs = {
            "profile.managed_default_content_settings.images": 2,  # Disable images
            "profile.default_content_setting_values.notifications": 2,  # Disable notifications
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False
        }
        options.add_experimental_option("prefs", prefs)
        return options

    def _build_host_resolver_rules(self):
        if os.environ.get("YOUTUBE_DISABLE_HOST_RESOLVER_RULES") == "1":
            return ""

        explicit_rules = os.environ.get("YOUTUBE_HOST_RESOLVER_RULES")
        if explicit_rules:
            return explicit_rules

        ip = os.environ.get("YOUTUBE_HOST_IP", "").strip()
        if not ip:
            return ""

        rules = [f"MAP {host} {ip}" for host in YOUTUBE_HOSTS]
        rules.append("EXCLUDE localhost")
        rules.append("EXCLUDE 127.0.0.1")
        return ",".join(rules)

    def set_up(self):
        """드라이버 초기화 및 페이지 로드
        
        Raises:
            WebDriverException: 드라이버 초기화 실패 시
        """
        try:
            self.logger.info("[SELENIUM] Initializing Chrome driver...")
            self.driver = webdriver.Chrome(service=_chrome_service(), options=self.options)
            
            # 타임아웃 설정
            self.driver.set_page_load_timeout(self.PAGE_LOAD_TIMEOUT)
            self.driver.set_script_timeout(self.SCRIPT_TIMEOUT)
            self.driver.implicitly_wait(self.IMPLICIT_WAIT)
            self._configure_cdp()
            
            self.logger.info(f"[SELENIUM] Loading page: {self.start_url}")
            self.driver.get(self.start_url)
            
            self.logger.info("[SELENIUM] Driver initialized successfully")
            
        except TimeoutException as e:
            self.logger.warning(f"[SELENIUM] Timeout loading initial page (ignored): {e}")
            self.logger.info("[SELENIUM] Driver initialized despite timeout")
            
        except SessionNotCreatedException as e:
            error_msg = f"[SELENIUM] Failed to create session: {e}"
            self.logger.error(error_msg)
            self._cleanup_driver()
            raise WebDriverException(error_msg) from e
            
        except WebDriverException as e:
            error_msg = f"[SELENIUM] Error setting up the driver: {e}"
            self.logger.error(error_msg)
            self.logger.error(traceback.format_exc())
            self._cleanup_driver()
            raise
            
        except Exception as e:
            error_msg = f"[SELENIUM] Unexpected error during setup: {e}"
            self.logger.error(error_msg)
            self.logger.error(traceback.format_exc())
            self._cleanup_driver()
            raise WebDriverException(error_msg) from e
    
    def _cleanup_driver(self):
        """드라이버 정리 (내부 용도)"""
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                self.logger.warning(f"[SELENIUM] Error during driver cleanup: {e}")
            finally:
                self.driver = None

    def __enter__(self):
        self.set_up()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """컨텍스트 매니저 종료 시 드라이버 정리"""
        self.remove_driver()
        
        # 예외가 발생한 경우 로깅
        if exc_type is not None:
            self.logger.error(
                f"[SELENIUM] Exception in context: {exc_type.__name__}: {exc_val}"
            )
        
        # False를 반환하여 예외를 전파
        return False

    def get_page_source(self) -> str:
        """현재 페이지 소스 반환
        
        Returns:
            HTML 페이지 소스 또는 None
        """
        if self.driver:
            try:
                root = self.driver.execute_cdp_cmd("DOM.getDocument", {
                    "depth": 0,
                    "pierce": True
                })
                root_id = root.get("root", {}).get("nodeId")
                if root_id:
                    html = self.driver.execute_cdp_cmd("DOM.getOuterHTML", {
                        "nodeId": root_id
                    })
                    outer_html = html.get("outerHTML")
                    if outer_html:
                        return outer_html
            except WebDriverException as e:
                self.logger.warning(f"[SELENIUM] Error getting page source via CDP: {e}")

            try:
                return self.driver.page_source
            except WebDriverException as e:
                self.logger.error(f"[SELENIUM] Error getting page source: {e}")
        return None

    def _configure_cdp(self):
        """Chrome DevTools Protocol 기반 설정을 적용합니다."""
        try:
            self.driver.execute_cdp_cmd("Network.enable", {})
            self.driver.execute_cdp_cmd("Network.setBlockedURLs", {
                "urls": [
                    "*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp", "*.svg",
                    "*.ico", "*.woff", "*.woff2", "*.ttf", "*.otf",
                    "*.mp4", "*.webm", "*.avi", "*.mov"
                ]
            })
            self.driver.execute_cdp_cmd("Network.setCookie", {
                "name": "PREF",
                "value": "hl=ko&gl=KR",
                "domain": ".youtube.com",
                "path": "/",
                "url": "https://www.youtube.com/"
            })
        except WebDriverException as e:
            self.logger.warning(f"[SELENIUM] Could not configure CDP options: {e}")

    def load_url(self, url: str):
        """URL을 로드하고 최소한의 문서 준비 상태를 검증합니다."""
        if not self.driver:
            error_msg = "[SELENIUM] Driver is not initialized, cannot load URL"
            self.logger.error(error_msg)
            raise WebDriverException(error_msg)

        last_error = None
        for attempt in range(1, self.NAVIGATION_RETRIES + 1):
            try:
                self.logger.info(
                    f"[SELENIUM] Loading target URL: {url} "
                    f"(attempt {attempt}/{self.NAVIGATION_RETRIES})"
                )
                try:
                    self.driver.get(url)
                except TimeoutException as e:
                    self.logger.warning(f"[SELENIUM] driver.get timed out, validating rendered page: {e}")
                    self._stop_loading()
                self._wait_for_document_ready(url)
                if "youtube.com" in url:
                    self._wait_for_youtube_interactive(url)
                else:
                    time.sleep(self.PAGE_STABILIZE_DELAY)
                    self._stop_loading()
                self._validate_page_source(url)
                self.logger.info("[SELENIUM] Target URL loaded successfully")
                return

            except (TimeoutException, WebDriverException) as e:
                last_error = e
                self._stop_loading()
                self.logger.warning(
                    f"[SELENIUM] Target URL load attempt {attempt}/{self.NAVIGATION_RETRIES} failed: {e}"
                )
                if attempt < self.NAVIGATION_RETRIES:
                    self.logger.info("[SELENIUM] Restarting driver before next target URL attempt")
                    self.restart_driver()
                    time.sleep(self.NAVIGATION_RETRY_DELAY * attempt)

        error_msg = f"[SELENIUM] Failed to load target URL after {self.NAVIGATION_RETRIES} attempts: {url}"
        self.logger.warning(error_msg)
        raise WebDriverException(error_msg) from last_error

    def _wait_for_document_ready(self, url: str):
        """JS 실행 없이 URL이 실제 검색 페이지로 전환될 때까지 대기"""
        deadline = time.monotonic() + self.DOCUMENT_READY_TIMEOUT
        last_url = "unavailable"

        while time.monotonic() < deadline:
            last_url = self._safe_current_url()
            state = self._get_page_state()
            if self._is_chrome_error_state(state):
                raise WebDriverException(
                    f"[SELENIUM] Chrome error page while loading {url}: {state}"
                )
            if last_url != "about:blank" and last_url.startswith(("http://", "https://")):
                return
            time.sleep(0.25)

        raise TimeoutException(
            f"Document URL did not change for {url}; current_url={last_url}"
        )

    def _wait_for_youtube_interactive(self, url: str):
        """YouTube SPA가 검색창을 렌더링할 때까지 기다립니다."""
        deadline = time.monotonic() + self.YOUTUBE_INTERACTIVE_TIMEOUT
        last_state = None
        last_error = None

        while time.monotonic() < deadline:
            try:
                state = self.driver.execute_script(
                    """
                    var inputs = Array.from(document.querySelectorAll(
                        'input[name="search_query"], input#search, input.ytSearchboxComponentInput, ytd-searchbox input, yt-searchbox input'
                    ));
                    var visibleInput = inputs.find(function(el) {
                        var rect = el.getBoundingClientRect();
                        return rect.width > 0 && rect.height > 0;
                    });
                    var bodyText = (document.body && document.body.innerText || '').replace(/\\s+/g, ' ').trim();
                    return {
                        href: location.href,
                        readyState: document.readyState,
                        title: document.title || '',
                        ytdApp: !!document.querySelector('ytd-app'),
                        inputCount: inputs.length,
                        visibleInput: !!visibleInput,
                        bodyPreview: bodyText.slice(0, 220)
                    };
                    """
                )
                last_state = state
                if self._is_chrome_error_state(state):
                    raise WebDriverException(
                        f"[SELENIUM] Chrome error page while loading {url}: {state}"
                    )
                if state and state.get("visibleInput"):
                    self.logger.info(f"[SELENIUM] YouTube search input rendered: {state}")
                    return
            except WebDriverException as e:
                last_error = e
                raise
            except Exception as e:
                last_error = e

            time.sleep(0.5)

        if last_error:
            self.logger.warning(
                f"[SELENIUM] YouTube interactive wait ended with error "
                f"({type(last_error).__name__}) for {url}; last_state={last_state}"
            )
        else:
            self.logger.warning(
                f"[SELENIUM] YouTube search input was not rendered before timeout for {url}; "
                f"last_state={last_state}"
            )
        raise TimeoutException(
            f"YouTube search input was not rendered for {url}; last_state={last_state}"
        )

    def _validate_page_source(self, url: str):
        """빈 문서나 about:blank를 성공 로드로 취급하지 않도록 검증"""
        deadline = time.monotonic() + self.DOCUMENT_READY_TIMEOUT
        state = self._get_page_state()
        current_url = state.get("href") or self._safe_current_url()
        html_content = self.get_page_source() or ""

        while (
            current_url != "about:blank"
            and len(html_content) < self.MIN_PAGE_SOURCE_LENGTH
            and time.monotonic() < deadline
        ):
            time.sleep(0.5)
            state = self._get_page_state()
            current_url = state.get("href") or self._safe_current_url()
            html_content = self.get_page_source() or ""

        if self._is_chrome_error_state(state):
            raise WebDriverException(
                f"[SELENIUM] Chrome error page after loading {url}: {state}"
            )

        if current_url == "about:blank":
            raise WebDriverException(
                f"[SELENIUM] Loaded document is empty or too short for {url}; "
                f"current_url={current_url}, source_length={len(html_content)}"
            )

        if len(html_content) < self.MIN_PAGE_SOURCE_LENGTH:
            self.logger.warning(
                f"[SELENIUM] Loaded document source is still short; continuing for dynamic page: "
                f"current_url={current_url}, source_length={len(html_content)}"
            )
            return

        self.logger.info(
            f"[SELENIUM] Loaded document validated: "
            f"current_url={current_url}, source_length={len(html_content)}"
        )

    def _stop_loading(self):
        """실패한 페이지 로드를 중단해 renderer가 다음 요청을 잡아두지 않도록 함"""
        if not self.driver:
            return

        try:
            self.driver.execute_cdp_cmd("Page.stopLoading", {})
        except Exception as e:
            self.logger.debug(f"[SELENIUM] Could not stop page load: {e}")

    def _reset_to_blank_quietly(self):
        try:
            self.reset_to_blank()
        except Exception as e:
            self.logger.debug(f"[SELENIUM] Could not reset before retry: {e}")

    def reset_to_blank(self):
        """다음 요청 전 브라우저 상태를 가볍게 초기화합니다."""
        if not self.driver:
            return

        try:
            self.driver.execute_cdp_cmd("Page.navigate", {"url": "about:blank"})
            self._stop_loading()
        except WebDriverException as e:
            self.logger.warning(f"[SELENIUM] Error resetting to about:blank: {e}")
            raise

    def _safe_current_url(self) -> str:
        try:
            return self.driver.current_url if self.driver else "no-driver"
        except Exception:
            return "unavailable"

    def _get_page_state(self) -> dict:
        if not self.driver:
            return {"href": "no-driver", "bodyPreview": ""}

        try:
            return self.driver.execute_script(
                """
                var bodyText = (document.body && document.body.innerText || '').replace(/\\s+/g, ' ').trim();
                return {
                    href: location.href,
                    readyState: document.readyState,
                    title: document.title || '',
                    bodyPreview: bodyText.slice(0, 260)
                };
                """
            ) or {}
        except Exception as e:
            return {
                "href": self._safe_current_url(),
                "bodyPreview": "",
                "error": type(e).__name__
            }

    def _is_chrome_error_state(self, state: dict) -> bool:
        if not state:
            return False

        href = str(state.get("href") or "")
        body = str(state.get("bodyPreview") or "")
        title = str(state.get("title") or "")
        text = f"{href} {title} {body}"
        error_markers = (
            "chrome-error://",
            "ERR_NAME_NOT_RESOLVED",
            "ERR_INTERNET_DISCONNECTED",
            "ERR_CONNECTION_TIMED_OUT",
            "ERR_CONNECTION_CLOSED",
            "ERR_TUNNEL_CONNECTION_FAILED",
            "DNS_PROBE",
            "This site can't be reached",
            "This site can’t be reached",
            "server IP address could not be found",
        )
        return any(marker in text for marker in error_markers)

    def health_check(self) -> bool:
        """드라이버 상태 확인
        
        Returns:
            드라이버가 정상 작동 중이면 True, 아니면 False
        """
        if not self.driver:
            return False
        
        try:
            self.driver.execute_cdp_cmd("Browser.getVersion", {})
            return True
        except WebDriverException:
            return False

    def remove_driver(self):
        """드라이버 종료 및 정리"""
        if self.driver:
            try:
                self.logger.info("[SELENIUM] Shutting down driver...")
                self.driver.quit()
                self.logger.info("[SELENIUM] Driver shut down successfully")
            except WebDriverException as e:
                self.logger.warning(f"[SELENIUM] Error during driver shutdown: {e}")
            except Exception as e:
                self.logger.warning(f"[SELENIUM] Unexpected error during shutdown: {e}")
            finally:
                self.driver = None

    def restart_driver(self):
        """드라이버 재시작
        
        Raises:
            WebDriverException: 재시작 실패 시
        """
        self.logger.info("[SELENIUM] Restarting driver...")
        self.remove_driver()
        time.sleep(2.5)
        self.set_up()
        self.logger.info("[SELENIUM] Driver restarted successfully")

    def scroll_down(self, nloop: int = 1, scroll_increment: int = 300, delay: float = 1.0):
        """페이지 스크롤
        
        Args:
            nloop: 스크롤 반복 횟수
            scroll_increment: 한 번에 스크롤할 픽셀 수
            delay: 스크롤 간 대기 시간 (초)
            
        Raises:
            WebDriverException: 스크롤 실패 시
        """
        if not self.driver:
            error_msg = "[SELENIUM] Driver is not initialized, cannot scroll"
            self.logger.error(error_msg)
            raise WebDriverException(error_msg)
        
        try:
            self.logger.info(f"[SELENIUM] Scrolling {nloop} times, {scroll_increment}px each")
            
            for i in range(nloop):
                self.driver.execute_cdp_cmd("Input.dispatchMouseEvent", {
                    "type": "mouseWheel",
                    "x": 960,
                    "y": 540,
                    "deltaX": 0,
                    "deltaY": scroll_increment
                })
                time.sleep(delay)
            
            self._stop_loading()
            self.logger.info(f"[SELENIUM] Scrolling completed successfully")
            
        except WebDriverException as e:
            error_msg = f"[SELENIUM] Error during scroll: {e}"
            self.logger.error(error_msg)
            self.logger.error(traceback.format_exc())
            raise WebDriverException(error_msg) from e
        
        except Exception as e:
            error_msg = f"[SELENIUM] Unexpected error during scroll: {e}"
            self.logger.error(error_msg)
            self.logger.error(traceback.format_exc())
            raise WebDriverException(error_msg) from e
