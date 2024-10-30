from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, WebDriverException, TimeoutException
from selenium.webdriver.common.by import By

from selenium_driver import SeleniumDriver

import sys
import time
import traceback

class Scraper:
  def __init__(self):
    # Initialize any necessary variables or objects here
    driver_instance = SeleniumDriver()
    self.driver = driver_instance.set_up()
    self.retry = 0
    pass

  def scrape_google(self, keyword:str, delay:float=0):
    # Implement your scraping logic here
    url = f'https://www.google.com/search?q={keyword}'
    self.driver.get(url)
    succesed = False
    wait = WebDriverWait(self.driver, 10)
    result = []
    try:
        self.scroll_down(self.driver)
        parents = wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, 'AJLUJb')))
        elements = []
        try:
            elements = self.driver.find_elements(By.CLASS_NAME, 'b2Rnsc')
            for element in elements:
                result.append(element.text)
            succesed = True
        except:
            pass
        if len(elements) == 0:
            for parent in parents:
                temp_ele = parent.find_elements(By.CSS_SELECTOR, ':scope > div')
                elements.extend(temp_ele)
            if len(elements) != 0:
                for element in elements:
                    result.append(element.text)
                succesed = True

    except NoSuchElementException:
        result = ['관련검색어가 없습니다.']
        succesed = False

    except TimeoutException:
        try:
            elements = wait.until(
                EC.presence_of_all_elements_located((By.CLASS_NAME, 'b2Rnsc'))
            )
            result = []
            for element in elements:
                result.append(element.text)
            succesed = True
        except:
            result = ['관련검색어가 없습니다.']
        print(f'{keyword} Timeout')

    except WebDriverException:
        traceback.print_exc()
        print("WebDriverException")
        result = ['관련검색어가 없습니다.']
        self.retry()

    except Exception as e:
        print(f'예상치 못한 오류가 발생했습니다. 오류코드 : {sys.exc_info.__name__}')
        result = ['관련검색어가 없습니다.']
        succesed = False
    
    finally:
        json_result = {
            'keyword':keyword,
            'result':result
        }
        self.driver.quit()
        print(json_result)
        return json_result, succesed
    
  def scroll_down(self, driver:webdriver.Chrome):
    driver.execute_script('window.scrollTo(0, document.body.scrollHeight);')
  def retry(self):
    self.driver = self.driver_manager.restart_driver(self.driver)
    self.retry = 0

if __name__ == '__main__':
    # Test your scraper here
    scraper = Scraper()
    result, succesed = scraper.scrape_google('바시티 자켓 바지')
    print(result)

