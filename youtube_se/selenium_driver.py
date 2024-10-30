from selenium import webdriver
from selenium.webdriver import ChromeOptions as Options
import time

class SeleniumDriver:
    def __init__(self):
        self.driver = None

    def set_up(self):
        options = Options()
        options.add_argument('--headless')
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
        options.add_argument('--window-size=1920x1080')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-infobars')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-extensions')
        options.add_argument('--temp-profile')
        options.add_argument('--disable-features=SearchProviderFirstRun')
        options.add_argument('--disable-geolocation')
        self.driver = webdriver.Chrome(options=options)

        self.driver.get('https://www.youtube.com/')
        return self.driver

    def health_check(self):
        if self.driver:
            return True
        else:
            return False

    def remove_driver(self):
        self.driver.quit()
        self.driver = None

    def restart_driver(self, driver):
        driver.quit()
        time.sleep(2.5)
        driver = SeleniumDriver().set_up()
        return driver

