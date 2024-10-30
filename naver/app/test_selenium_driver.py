import threading
import time
import unittest
from selenium.webdriver.remote.webdriver import WebDriver

from google.app.selenium_driver import SeleniumDriver

class SeleniumDriverTest(unittest.TestCase):
    def setUp(self):
        self.driver = None
        self.selenium_driver = SeleniumDriver()

    def tearDown(self):
        if self.driver:
            self.driver.quit()

    def test_multithreading(self):
        # Create multiple threads
        num_threads = 5
        threads = []
        for i in range(num_threads):
            port_number = 9515 + i
            thread = threading.Thread(target=self.run_selenium_driver, args=(port_number,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to finish
        for thread in threads:
            thread.join()

    def run_selenium_driver(self, port):
        # Create a new instance of SeleniumDriver
        driver = self.selenium_driver.set_up(port=port)

        # Perform some actions with the driver
        driver.get("https://www.naver.com")
        time.sleep(1)
        title = driver.title

        # Assert the expected result
        self.assertEqual("NAVER", title)

        # Remove the driver
        # self.selenium_driver.remove_driver()

if __name__ == "__main__":
    unittest.main()