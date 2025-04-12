from selenium import webdriver
from selenium.webdriver import ChromeOptions
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
import os
import random

class SeleniumDriver:
    def __init__(self, start_url='https://www.youtube.com/'):
        self.driver = None
        self.start_url = start_url
        self.options = self._get_options()

    def _get_options(self):
        options = ChromeOptions()
        options.add_argument('--headless')
        
        # 더 자연스러운 User-Agent 설정
        user_agents = [
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
        ]
        options.add_argument(f"user-agent={random.choice(user_agents)}")
        
        # 더 자연스러운 윈도우 크기 설정
        window_sizes = ['1920,1080', '1366,768', '1440,900']
        options.add_argument(f'--window-size={random.choice(window_sizes)}')
        
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-sync')
        options.add_argument('--safebrowsing-disable-auto-update')
        options.add_argument('--disable-domain-reliability')
        options.add_argument('--disable-component-extensions-with-background-pages')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-notifications')
        options.add_argument('--disable-popup-blocking')
        options.add_argument('--disable-translate')
        options.add_argument('--disable-renderer-backgrounding')
        options.add_argument('--disable-device-discovery-notifications')
        options.add_argument('--mute-audio')
        options.add_argument('--disable-features=SearchProviderFirstRun')
        options.add_argument('--disable-geolocation')
        options.add_argument('--disable-blink-features=AutomationControlled')  # 자동화 감지 방지
        options.add_experimental_option("excludeSwitches", ["enable-automation"])  # 자동화 감지 방지
        options.add_experimental_option('useAutomationExtension', False)  # 자동화 감지 방지
        
        # 페이지 로드 전략 설정
        options.page_load_strategy = 'normal'  # 더 자연스러운 로딩을 위해 normal로 변경

        prefs = {
            "profile.managed_default_content_settings.images": 1,  # 이미지 활성화
            "profile.default_content_setting_values.notifications": 2,
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,
            "profile.default_content_settings.popups": 0,
            "profile.default_content_settings.geolocation": 2,
            "profile.default_content_settings.media_stream": 2,
        }
        options.add_experimental_option("prefs", prefs)
        return options

    def set_up(self):
         try:
             self.driver = webdriver.Chrome(options=self.options)
             # 자동화 감지 방지를 위한 추가 설정
             self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
             self.driver.get(self.start_url)
         except WebDriverException as e:
             print(f"Error setting up the driver: {e}")
             self.driver = None

    def __enter__(self):
        self.set_up()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.remove_driver()

    def get_page_source(self):
        if self.driver:
            return self.driver.page_source
        return None

    def health_check(self):
        return self.driver is not None

    def remove_driver(self):
        if self.driver:
            self.driver.quit()
            self.driver = None

    def restart_driver(self):
        self.remove_driver()
        time.sleep(random.uniform(2.0, 4.0))  # 랜덤한 대기 시간 추가
        self.set_up()

