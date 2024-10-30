from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, WebDriverException, TimeoutException
from selenium.webdriver.common.by import By

from driver_manager import DriverManager
import time

class Scraper:
  def __init__(self, driver, driver_manager:DriverManager) -> None:
    self.driver = driver
    self.driver_manager = driver_manager
    self.retry = 0
    self.succeed = False
    pass

  def scrape_naver_popular(self, keyword:str, delay:float=0):
    result = []
    url = f'https://search.naver.com/search.naver?sm=tab_hty.top&where=nexearch&query={keyword}'
    self.driver.get(url=url)
    wait = WebDriverWait(self.driver, 10)
    popular_contents = '인기 주제가 없습니다.'
    
    try:
      popular_elements = wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, 'fds-ugc-body-popular-topic-row')))
      popular_ele1 = popular_elements[0].text.split('\n')
      popular_ele2 = popular_elements[1].text.split('\n')
      popular_contents = []
      for i in range(len(popular_ele1)):
          try:
              popular_contents.append(popular_ele1[i])
              popular_contents.append(popular_ele2[i])
          except:
              pass
      self.succeed = True

    except NoSuchElementException:
      popular_contents = '인기 주제가 없습니다.'
      self.succeed = True

    except TimeoutException:
      self.retry_func(keyword=keyword, delay=delay)
      
    except WebDriverException as e:
      self.retry_func(keyword=keyword, delay=delay)

    except Exception as e:
      print('예기치 못한 오류', e)
      self.retry_func(keyword=keyword, delay=delay)
      
    finally:
      data = {
        'keyword':keyword,
        'popular_contents':popular_contents
      }
      return data, self.succeed
  
  def retry_func(self, keyword: str, delay: float = 0):
      if self.retry < 1:
        self.retry += 1
        return self.scrape_naver_popular(keyword=keyword, delay=delay)
      else:
        popular_contents = '인기 주제가 없습니다.'
        self.driver.refresh()
        self.succeed = False
        data = {
          'keyword':keyword,
          'popular_contents':popular_contents
        }
        return data, self.succeed