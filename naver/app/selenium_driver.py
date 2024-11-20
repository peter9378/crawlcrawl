from selenium import webdriver
from selenium.webdriver import ChromeOptions
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
import os

class SeleniumDriver:
    def __init__(self, start_url='https://www.youtube.com/'):
        self.driver = None
        self.start_url = start_url
        self.options = self._get_options()
        self.set_up()

    def _get_options(self):
        options = ChromeOptions()
        options.add_argument('--headless')
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
        options.add_argument('--window-size=1920x1080')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-features=SearchProviderFirstRun')
        options.add_argument('--disable-geolocation')
        options.page_load_strategy = 'eager'  # Load only the DOM content, which is faster
        return options

    def set_up(self):
        try:
            self.driver = webdriver.Chrome(options=self.options)
            self.driver.get(self.start_url)
        except WebDriverException as e:
            print(f"Error setting up the driver: {e}")
            self.driver = None

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
        time.sleep(2.5)  # Consider reducing or removing the sleep if unnecessary
        self.set_up()

if __name__ == "__main__":
    selenium_driver = SeleniumDriver()
    if selenium_driver.health_check():
        print("Driver is healthy and running.")
        html_content = selenium_driver.get_page_source()
        print("Page source retrieved.")
    else:
        print("Driver setup failed.")
    selenium_driver.remove_driver()

