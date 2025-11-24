"""
Selenium 드라이버 풀 관리
매 요청마다 드라이버를 생성/삭제하지 않고 재사용하여 성능 향상
"""
import threading
import time
import logging
from typing import Optional
from contextlib import contextmanager
from selenium_driver import SeleniumDriver


class SeleniumDriverPool:
    """스레드별 Selenium 드라이버 풀 관리자
    
    각 워커 스레드마다 하나의 드라이버를 유지하고 재사용합니다.
    일정 횟수 사용 후 드라이버를 자동으로 재시작하여 메모리 누수를 방지합니다.
    """
    
    # 드라이버를 재시작하기 전 최대 사용 횟수
    MAX_USES_BEFORE_RESTART = 100
    # 드라이버 생성 실패 시 최대 재시도 횟수
    MAX_CREATION_RETRIES = 3
    
    def __init__(self):
        """드라이버 풀 초기화"""
        self.logger = logging.getLogger('uvicorn')
        
        # 스레드별 드라이버 저장소
        self._local = threading.local()
        
        # 전역 락 (드라이버 생성 시 동기화)
        self._lock = threading.Lock()
        
        # 통계
        self._stats = {
            'total_requests': 0,
            'driver_restarts': 0,
            'driver_errors': 0
        }
        self._stats_lock = threading.Lock()
        
        self.logger.info("[POOL] Selenium driver pool initialized")
    
    def _get_thread_id(self) -> str:
        """현재 스레드 ID 반환"""
        return f"thread-{threading.get_ident()}"
    
    def _initialize_driver(self, force_restart: bool = False) -> SeleniumDriver:
        """현재 스레드용 드라이버 초기화 또는 재시작
        
        Args:
            force_restart: True일 경우 기존 드라이버를 종료하고 새로 생성
            
        Returns:
            초기화된 SeleniumDriver 인스턴스
            
        Raises:
            Exception: 드라이버 생성 실패 시
        """
        thread_id = self._get_thread_id()
        
        # 기존 드라이버 정리
        if force_restart and hasattr(self._local, 'driver'):
            self.logger.info(f"[POOL] {thread_id}: Forcing driver restart")
            try:
                if self._local.driver:
                    self._local.driver.remove_driver()
            except Exception as e:
                self.logger.warning(f"[POOL] {thread_id}: Error removing old driver: {e}")
            finally:
                delattr(self._local, 'driver')
                delattr(self._local, 'use_count')
        
        # 새 드라이버 생성 (재시도 로직 포함)
        last_error = None
        for attempt in range(self.MAX_CREATION_RETRIES):
            try:
                self.logger.info(f"[POOL] {thread_id}: Creating new driver (attempt {attempt+1}/{self.MAX_CREATION_RETRIES})")
                
                # 기본 URL은 네이버로 설정 (나중에 get()으로 변경)
                driver = SeleniumDriver(start_url='https://www.naver.com/')
                driver.set_up()
                
                if not driver.health_check():
                    raise Exception("Driver health check failed after creation")
                
                self._local.driver = driver
                self._local.use_count = 0
                
                with self._stats_lock:
                    self._stats['driver_restarts'] += 1
                
                self.logger.info(f"[POOL] {thread_id}: Driver created successfully")
                return driver
                
            except Exception as e:
                last_error = e
                self.logger.error(f"[POOL] {thread_id}: Failed to create driver (attempt {attempt+1}): {e}")
                
                if attempt < self.MAX_CREATION_RETRIES - 1:
                    time.sleep(2 ** attempt)  # 지수 백오프
        
        # 모든 재시도 실패
        with self._stats_lock:
            self._stats['driver_errors'] += 1
        
        error_msg = f"Failed to create driver after {self.MAX_CREATION_RETRIES} attempts"
        if last_error:
            error_msg += f": {str(last_error)}"
        
        self.logger.error(f"[POOL] {thread_id}: {error_msg}")
        raise Exception(error_msg)
    
    def _get_or_create_driver(self) -> SeleniumDriver:
        """현재 스레드의 드라이버 반환 (없으면 생성)
        
        ⚠️ 중요: 이 함수는 새 요청이 시작되기 **전**에 호출됩니다.
        따라서 재시작이 필요한 경우에도 진행 중인 요청에는 영향을 주지 않습니다.
        
        실행 순서:
        1. 100번째 요청: use_count=99 → 기존 드라이버 사용 → 정상 완료 → use_count=100
        2. 101번째 요청: use_count=100 → 재시작 체크 → 새 드라이버 생성 → use_count=0
        
        Returns:
            SeleniumDriver 인스턴스
        """
        thread_id = self._get_thread_id()
        
        # 드라이버가 이미 존재하는지 확인
        if not hasattr(self._local, 'driver') or self._local.driver is None:
            self.logger.info(f"[POOL] {thread_id}: No driver found, creating new one")
            return self._initialize_driver(force_restart=False)
        
        # 사용 횟수 확인 (주기적 재시작)
        # ✅ 안전: 이전 요청은 이미 완료되었으며, 새 요청 시작 전에 재시작함
        if self._local.use_count >= self.MAX_USES_BEFORE_RESTART:
            self.logger.info(
                f"[POOL] {thread_id}: Driver used {self._local.use_count} times, "
                f"restarting before next request (previous request completed safely)"
            )
            return self._initialize_driver(force_restart=True)
        
        # 헬스체크
        if not self._local.driver.health_check():
            self.logger.warning(f"[POOL] {thread_id}: Driver health check failed, restarting")
            return self._initialize_driver(force_restart=True)
        
        # 기존 드라이버 반환
        return self._local.driver
    
    @contextmanager
    def get_driver(self, url: str):
        """드라이버를 컨텍스트 매니저로 제공
        
        ⚠️ 안전성 보장:
        - 드라이버 재시작은 이 함수 시작 시점에 체크됩니다
        - 따라서 요청 처리 중에는 절대 재시작되지 않습니다
        - 100번째 요청이 완료된 후, 101번째 요청 시작 전에 재시작됩니다
        
        사용 예:
            with pool.get_driver(url) as driver:
                driver.scroll_down(5)
                html = driver.get_page_source()
        
        Args:
            url: 로드할 URL
            
        Yields:
            SeleniumDriver 인스턴스
        """
        thread_id = self._get_thread_id()
        driver = None
        original_window = None
        new_window = None
        
        try:
            # 드라이버 가져오기 (재시작이 필요하면 여기서 처리됨)
            # ✅ 이전 요청은 이미 완료된 상태
            driver = self._get_or_create_driver()
            
            # 통계 업데이트
            with self._stats_lock:
                self._stats['total_requests'] += 1
            
            # 사용 횟수 증가 (이 요청 완료 후에 카운트됨)
            self._local.use_count += 1
            
            # 다음 재시작까지 남은 요청 수 계산
            remaining = self.MAX_USES_BEFORE_RESTART - self._local.use_count
            
            self.logger.info(
                f"[POOL] {thread_id}: Using driver "
                f"(use_count: {self._local.use_count}/{self.MAX_USES_BEFORE_RESTART}, "
                f"restart in {remaining} requests)"
            )
            
            # 새 탭 열기 (기존 탭에 영향 없이)
            original_window = driver.driver.current_window_handle
            driver.driver.execute_script("window.open('');")
            
            # 새 탭으로 전환
            new_window = driver.driver.window_handles[-1]
            driver.driver.switch_to.window(new_window)
            
            # URL 로드
            self.logger.info(f"[POOL] {thread_id}: Loading URL in new tab: {url}")
            driver.driver.get(url)
            
            # 드라이버를 사용자에게 제공
            yield driver
            
        except Exception as e:
            self.logger.error(f"[POOL] {thread_id}: Error using driver: {e}")
            
            # 에러 발생 시 드라이버를 재시작하도록 마킹
            if hasattr(self._local, 'use_count'):
                self._local.use_count = self.MAX_USES_BEFORE_RESTART
            
            raise
            
        finally:
            # 새 탭 닫기 (리소스 정리)
            try:
                if driver and driver.driver and new_window:
                    self.logger.debug(f"[POOL] {thread_id}: Closing new tab")
                    driver.driver.close()
                    
                    # 원래 탭으로 돌아가기
                    if original_window and original_window in driver.driver.window_handles:
                        driver.driver.switch_to.window(original_window)
                    elif len(driver.driver.window_handles) > 0:
                        # 원래 창이 없으면 첫 번째 창으로
                        driver.driver.switch_to.window(driver.driver.window_handles[0])
                        
            except Exception as e:
                self.logger.warning(f"[POOL] {thread_id}: Error closing tab: {e}")
                # 탭 닫기 실패 시 다음 요청에서 드라이버 재시작
                if hasattr(self._local, 'use_count'):
                    self._local.use_count = self.MAX_USES_BEFORE_RESTART
    
    def get_stats(self) -> dict:
        """풀 통계 반환"""
        with self._stats_lock:
            return self._stats.copy()
    
    def cleanup_all(self):
        """모든 드라이버 정리 (애플리케이션 종료 시)"""
        thread_id = self._get_thread_id()
        self.logger.info(f"[POOL] {thread_id}: Cleaning up all drivers")
        
        if hasattr(self._local, 'driver') and self._local.driver:
            try:
                self._local.driver.remove_driver()
            except Exception as e:
                self.logger.warning(f"[POOL] {thread_id}: Error during cleanup: {e}")
            finally:
                delattr(self._local, 'driver')
                if hasattr(self._local, 'use_count'):
                    delattr(self._local, 'use_count')
        
        self.logger.info(f"[POOL] {thread_id}: Cleanup completed")


# 전역 드라이버 풀 인스턴스 (앱 시작 시 한 번만 생성)
_driver_pool: Optional[SeleniumDriverPool] = None


def get_driver_pool() -> SeleniumDriverPool:
    """전역 드라이버 풀 인스턴스 반환"""
    global _driver_pool
    if _driver_pool is None:
        _driver_pool = SeleniumDriverPool()
    return _driver_pool


def cleanup_driver_pool():
    """전역 드라이버 풀 정리"""
    global _driver_pool
    if _driver_pool is not None:
        _driver_pool.cleanup_all()

