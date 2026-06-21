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
from urllib.parse import urlparse

CHROMEDRIVER_PATH = os.environ.get('CHROMEDRIVER_PATH', '/usr/local/bin/chromedriver')


def _chrome_service() -> Service:
    if os.path.isfile(CHROMEDRIVER_PATH):
        return Service(executable_path=CHROMEDRIVER_PATH)
    return Service()


class SeleniumDriver:
    # 페이지 로드 타임아웃 (초)
    PAGE_LOAD_TIMEOUT = int(os.environ.get('SELENIUM_PAGE_LOAD_TIMEOUT', '20'))
    # 스크립트 실행 타임아웃 (초)
    SCRIPT_TIMEOUT = int(os.environ.get('SELENIUM_SCRIPT_TIMEOUT', '5'))
    # 명시적 페이지 준비 대기 시간 (초)
    DOCUMENT_READY_TIMEOUT = float(os.environ.get('SELENIUM_DOCUMENT_READY_TIMEOUT', '10'))
    # URL 전환 후 동적 DOM이 채워질 최소 대기 시간 (초)
    PAGE_STABILIZE_DELAY = float(os.environ.get('SELENIUM_PAGE_STABILIZE_DELAY', '2.5'))
    # YouTube SPA hydration을 위해 기본적으로 페이지 로딩을 강제 중단하지 않는다.
    STOP_LOADING_AFTER_NAVIGATE = os.environ.get('SELENIUM_STOP_LOADING_AFTER_NAVIGATE', 'false').lower() == 'true'
    # YouTube는 DOM.getOuterHTML이 renderer/network 상태에 묶여 길게 block될 수 있어 URL 기반 검증을 기본 사용한다.
    FAST_VALIDATE_YOUTUBE = os.environ.get('SELENIUM_FAST_VALIDATE_YOUTUBE', 'true').lower() == 'true'
    # 빈 문서로 간주할 최소 HTML 길이
    MIN_PAGE_SOURCE_LENGTH = 100
    # 암묵적 대기 시간 (초)
    IMPLICIT_WAIT = 10
    
    def __init__(self, start_url='about:blank'):
        self.driver = None
        self.start_url = start_url
        self.options = self._get_options()
        self.logger = logging.getLogger('uvicorn')

    def _get_options(self):
        options = ChromeOptions()
        # Set binary location if it exists (e.g. inside Docker) to prevent Selenium Manager from downloading it
        if os.path.isfile('/usr/bin/google-chrome'):
            options.binary_location = '/usr/bin/google-chrome'
        options.add_argument('--headless=new')
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-software-rasterizer')
        options.add_argument('--disable-features=VizDisplayCompositor')
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
        options.add_argument('--disable-gpu-sandbox')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.page_load_strategy = 'none'  # driver.get 대기 대신 load_url에서 명시적으로 검증
        
        prefs = {
            "profile.managed_default_content_settings.images": 2,  # Disable images
            "profile.default_content_setting_values.notifications": 2,  # Disable notifications
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False
        }
        options.add_experimental_option("prefs", prefs)
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        return options

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
            self.driver.execute_cdp_cmd("Page.enable", {})
            self.driver.execute_cdp_cmd("DOM.enable", {})
            self.driver.execute_cdp_cmd("Network.enable", {})
            self.driver.execute_cdp_cmd("Network.setBlockedURLs", {
                "urls": [
                    "*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp", "*.svg",
                    "*.ico", "*.woff", "*.woff2", "*.ttf", "*.otf",
                    "*.mp4", "*.webm", "*.avi", "*.mov"
                ]
            })
            self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
            })
        except WebDriverException as e:
            self.logger.warning(f"[SELENIUM] Could not configure CDP options: {e}")

    def load_url(self, url: str):
        """URL을 로드하고 최소한의 문서 준비 상태를 검증합니다."""
        if not self.driver:
            error_msg = "[SELENIUM] Driver is not initialized, cannot load URL"
            self.logger.error(error_msg)
            raise WebDriverException(error_msg)

        try:
            self.logger.info(f"[SELENIUM] Loading target URL: {url}")
            self._navigate_with_cdp(url)
            self._wait_for_document_ready(url)
            time.sleep(self.PAGE_STABILIZE_DELAY)
            if self.STOP_LOADING_AFTER_NAVIGATE:
                self._stop_loading()
            if self._should_fast_validate(url):
                self._validate_current_url(url)
            else:
                self._validate_page_source(url)
            self.logger.info("[SELENIUM] Target URL loaded successfully")

        except TimeoutException as e:
            self._stop_loading()
            error_msg = f"[SELENIUM] Timed out loading target URL: {url}"
            self.logger.warning(error_msg)
            raise WebDriverException(error_msg) from e

        except WebDriverException:
            self._stop_loading()
            raise

    def _navigate_with_cdp(self, url: str):
        """일반 driver.get 대기 대신 CDP navigation으로 빠르게 전환합니다."""
        try:
            self.driver.execute_cdp_cmd("Page.navigate", {"url": url})
        except WebDriverException as e:
            error_msg = f"[SELENIUM] CDP navigation failed for {url}: {e}"
            self.logger.warning(error_msg)
            raise WebDriverException(error_msg) from e

    def _wait_for_document_ready(self, url: str):
        """JS 실행 없이 URL이 실제 페이지로 전환될 때까지 대기"""
        deadline = time.monotonic() + self.DOCUMENT_READY_TIMEOUT
        last_url = "unavailable"

        while time.monotonic() < deadline:
            last_url = self._safe_current_url()
            if last_url != "about:blank" and last_url.startswith(("http://", "https://")):
                return
            time.sleep(0.25)

        raise TimeoutException(
            f"Document URL did not change for {url}; current_url={last_url}"
        )

    def _validate_page_source(self, url: str):
        """빈 문서나 about:blank를 성공 로드로 취급하지 않도록 검증"""
        current_url = self._safe_current_url()
        html_content = self.get_page_source() or ""

        if current_url == "about:blank" or len(html_content) < self.MIN_PAGE_SOURCE_LENGTH:
            raise WebDriverException(
                f"[SELENIUM] Loaded document is empty or too short for {url}; "
                f"current_url={current_url}, source_length={len(html_content)}"
            )

        self.logger.info(
            f"[SELENIUM] Loaded document validated: "
            f"current_url={current_url}, source_length={len(html_content)}"
        )

    def _should_fast_validate(self, url: str) -> bool:
        if not self.FAST_VALIDATE_YOUTUBE:
            return False

        try:
            hostname = urlparse(url).hostname or ""
        except Exception:
            return False

        return hostname == "youtube.com" or hostname.endswith(".youtube.com")

    def _validate_current_url(self, url: str):
        """YouTube SPA용 경량 검증. 전체 HTML 추출은 renderer 대기 때문에 피한다."""
        current_url = self._safe_current_url()
        if current_url == "about:blank" or not current_url.startswith(("http://", "https://")):
            raise WebDriverException(
                f"[SELENIUM] Loaded document URL is invalid for {url}; current_url={current_url}"
            )

        self.logger.info(
            f"[SELENIUM] Loaded document URL validated: current_url={current_url}"
        )

    def _stop_loading(self):
        """실패한 페이지 로드를 중단해 renderer가 다음 요청을 잡아두지 않도록 함"""
        if not self.driver:
            return

        try:
            self.driver.execute_cdp_cmd("Page.stopLoading", {})
        except Exception as e:
            self.logger.debug(f"[SELENIUM] Could not stop page load: {e}")

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
