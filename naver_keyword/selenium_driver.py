from selenium import webdriver
from selenium.webdriver import ChromeOptions
from selenium.common.exceptions import (
    WebDriverException,
    TimeoutException,
    NoSuchElementException,
    SessionNotCreatedException
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os
import traceback
import logging

class SeleniumDriver:
    # 페이지 로드 타임아웃 (초)
    PAGE_LOAD_TIMEOUT = 30
    # 스크립트 실행 타임아웃 (초)
    SCRIPT_TIMEOUT = 30
    # 암묵적 대기 시간 (초)
    IMPLICIT_WAIT = 10
    
    def __init__(self, start_url='https://www.naver.com/'):
        self.driver = None
        self.start_url = start_url
        self.options = self._get_options()
        self.logger = logging.getLogger('uvicorn')

    def _get_options(self):
        options = ChromeOptions()
        options.add_argument('--headless')
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
        options.add_argument('--window-size=300,600')
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
        options.page_load_strategy = 'eager'  # faster DOM load
        
        prefs = {
            "profile.managed_default_content_settings.images": 2,  # Disable images
            "profile.default_content_setting_values.notifications": 2,  # Disable notifications
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False
        }
        options.add_experimental_option("prefs", prefs)
        return options

    def set_up(self):
        """드라이버 초기화 및 페이지 로드
        
        Raises:
            WebDriverException: 드라이버 초기화 실패 시
        """
        try:
            self.logger.info("[SELENIUM] Initializing Chrome driver...")
            self.driver = webdriver.Chrome(options=self.options)
            
            # 타임아웃 설정
            self.driver.set_page_load_timeout(self.PAGE_LOAD_TIMEOUT)
            self.driver.set_script_timeout(self.SCRIPT_TIMEOUT)
            self.driver.implicitly_wait(self.IMPLICIT_WAIT)
            
            self.logger.info(f"[SELENIUM] Loading page: {self.start_url}")
            self.driver.get(self.start_url)
            
            self.logger.info("[SELENIUM] Driver initialized successfully")
            
        except TimeoutException as e:
            error_msg = f"[SELENIUM] Timeout loading page: {e}"
            self.logger.error(error_msg)
            self._cleanup_driver()
            raise WebDriverException(error_msg) from e
            
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
                return self.driver.page_source
            except WebDriverException as e:
                self.logger.error(f"[SELENIUM] Error getting page source: {e}")
                return None
        return None

    def health_check(self) -> bool:
        """드라이버 상태 확인
        
        Returns:
            드라이버가 정상 작동 중이면 True, 아니면 False
        """
        if not self.driver:
            return False
        
        try:
            # 드라이버가 살아있는지 확인
            _ = self.driver.title
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
                # 스크롤 실행
                self.driver.execute_script(f"window.scrollBy(0, {scroll_increment});")
                
                # 대기
                time.sleep(delay)
                
                # 현재 스크롤 위치 로깅
                scroll_position = self.driver.execute_script("return window.pageYOffset;")
                self.logger.debug(
                    f"[SELENIUM] Scroll iteration {i+1}/{nloop}, "
                    f"position: {scroll_position}px"
                )
            
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

