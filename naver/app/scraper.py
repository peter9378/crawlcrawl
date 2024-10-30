from selenium.webdriver import Chrome
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, WebDriverException, TimeoutException
from selenium.webdriver.common.by import By

from selenium_driver import SeleniumDriver
import time
from bs4 import BeautifulSoup
import json


class Scraper:
  def __init__(self):
    # Initialize any necessary variables or objects here
    self.driver = SeleniumDriver().set_up()
    self.retry = 0
    pass

  def scrape_naver(self, keyword:str, delay:float=0.25):
    # Implement your scraping logic here
    result = []
    url = f'https://search.naver.com/search.naver?sm=tab_hty.top&where=nexearch&query={keyword}'
    try:
      self.driver.get(url=url)
      wait = WebDriverWait(self.driver, 10)
      target = self.driver.find_element(By.CLASS_NAME, 'lst_related_srch')
      wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, 'tit')))
      elements = target.find_elements(By.CLASS_NAME, 'tit')
      for ele in elements:
        if ele.text != '':
          result.append(ele.text)
    except NoSuchElementException:
      result = '관련검색어가 없습니다.'
    except TimeoutException:
      self.driver.refresh()
      self.retry += 1
      if self.retry < 1:
        self.driver = SeleniumDriver().restart_driver(self.driver)
        return self.scrape_naver(keyword=keyword, delay=delay)
      else:
        result = '관련검색어가 없습니다.'

        # 종료 함수 수정
        self.driver = SeleniumDriver().restart_driver(self.driver)
        self.retry = 0
    except WebDriverException:
      self.retry += 1
      if self.retry < 1:
        self.driver = SeleniumDriver().restart_driver(self.driver)
        return self.scrape_naver(keyword=keyword, delay=delay)
      else:
        result = '관련검색어가 없습니다.'

        # 종료 함수 수정
        self.driver = SeleniumDriver().restart_driver(self.driver)
        self.retry = 0
    finally:
      self.driver.quit()
    data = {
        'keyword': keyword,
        'result': result,
    }
    json_data = json.dumps(data, ensure_ascii=False)
    print(json_data)
    return json_data

  def scrape_navershopping(self, keyword:str, delay:float=0.25):
    url = f'https://msearch.shopping.naver.com/search/all?query={keyword}&prevQuery={keyword}'
    # https://m.search.naver.com/search.naver?where=nexearch&sm=top_hty&fbm=0&ie=utf8&query=%EB%96%A1%EB%B3%B6%EC%9D%B4
    self.driver.get(url=url)
    time.sleep(delay)
    wait = WebDriverWait(self.driver, 10)

    try:
      wait.until(EC.presence_of_all_elements_located((By.ID, 'taglist')))
      page_source = self.driver.page_source
      soup = BeautifulSoup(page_source, 'html.parser')
      targets = soup.select('.intentKeyword_list_panel__thfp_ a')
      result = [tag.text for target in targets for tag in target.find_all('a')]

      if len(result) <= 0:
        temp_ul = soup.select_one('#taglist div ul')
        li_tags = temp_ul.find_all('li')
        result = [li.text for li in li_tags]

      data = {
        'keyword': keyword,
        'result': result,
      }
    except TimeoutException:
      result = '관련검색어가 없습니다.'
      data = {
          'keyword': keyword,
          'result': result,
      }
    except WebDriverException:
      result = '관련검색어가 없습니다.'
      data = {
          'keyword': keyword,
          'result': result,
      }

    except Exception as e:
      print(e)
      data = {
          'keyword': keyword,
          'result': '관련 검색어가 없습니다.',
      }
    json_data = json.dumps(data, ensure_ascii=False)
    print(json_data)

    return json_data
  
  def scrape_naver_shop_keyword(self, keywords:str, delay:float=0.25):
    url = f'https://m.search.naver.com/search.naver?where=nexearch&sm=top_hty&fbm=0&ie=utf8&query={keywords}'
    self.driver.get(url=url)

    soup = BeautifulSoup(self.driver.page_source, 'html.parser')
    try:
      result = '관련 검색어가 없습니다.'
      items = soup.find_all(class_='keyword_item')
      result = [item.text for item in items]
      data = {
          'keyword': keywords,
          'result': result,
      }
      return data
    except Exception as e:
      print(e)
      data = {
          'keyword': keywords,
          'result': '관련 검색어가 없습니다.',
      }
      return data
    finally:
      self.driver.quit()



if __name__ == '__main__':
  # Example usage:
  scraper = Scraper()
  # scraper.scrape_naver(keyword='제일기획', delay=0.5)
  # scraper.scrape_navershopping(keyword='제일기획', delay=0.5)
  # scraper.scrape_navershopping(keyword='초콜릿', delay=0.5)
  print(scraper.scrape_naver_shop_keyword(keywords='갈비탕', delay=0.5))
