from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

import sys
import time


class Crawler():
    def __init__(self) -> None:
        
        self.driver = None
        pass

    def Set_Browser(self):
        chromedriver_path = './chromedriver.exe'
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-infobars')
        options.add_argument('no-sandbox')
        options.add_argument('--disable-extensions')
        options.add_argument('--temp-profile')
        options.add_argument('--disable-features=SearchProviderFirstRun')
        options.add_argument('--disable-geolocation')

        if self.driver == None:
            self.driver = webdriver.Chrome(options=options)
        else:
            self.driver.quit()
            self.driver = webdriver.Chrome(options=options)
            
    def Search_Naver(self, keyword:str, delay:float):
        result = []
        url = f'https://search.naver.com/search.naver?sm=tab_hty.top&where=nexearch&query={keyword}'
        self.driver.get(url=url)
        wait = WebDriverWait(self.driver, 5)
        try:
            target = self.driver.find_element(By.CLASS_NAME, 'lst_related_srch')
            wait.until(
                EC.presence_of_all_elements_located((By.CLASS_NAME, 'tit'))
            )
            elements = target.find_elements(By.CLASS_NAME, 'tit')
            for ele in elements:
                result.append(ele.text)

            data ={
                'keyword':keyword,
                'result':result,
            }
        except Exception as e:
            result = '관련검색어가 없습니다.'
            data = {
                'keyword':keyword,
                'result':result,
            }
        return data, True
    
    def Search_Naver_Popular(self, keyword:str, delay:float):
        url = f'https://search.naver.com/search.naver?sm=tab_hty.top&where=nexearch&query={keyword}'
        self.driver.get(url=url)
        wait = WebDriverWait(self.driver, 5)
        try:
            popular_elements = wait.until(
                EC.presence_of_all_elements_located((By.CLASS_NAME, 'fds-ugc-body-popular-topic-row'))
            )
            # popular_elements = self.driver.find_elements(By.CLASS_NAME, 'fds-ugc-body-popular-topic-row')
            popular_ele1 = popular_elements[0].text.split('\n')
            popular_ele2 = popular_elements[1].text.split('\n')
            popular_contents = []
            for i in range(len(popular_ele1)):
                try:
                    popular_contents.append(popular_ele1[i])
                    popular_contents.append(popular_ele2[i])
                except:
                    pass
            
            data = {
                'keyword':keyword,
                'popular_contents':popular_contents
            }
        except Exception as e:
            popular_contents = '인기 주제가 없습니다.'
            data = {
                'keyword':keyword,
                'popular_contents':popular_contents
            }
        return data, True
    
    def Search_Google(self, keyword:str, delay:float):
        url = f'https://www.google.com/search?q={keyword}'
        self.driver.get(url)
        succesed = False
        try:
            elements = self.driver.find_elements(By.CLASS_NAME, 's75CSd')
            result = []
            for element in elements:
                result.append(element.text)
            succesed = True
                
        except NoSuchElementException:
            result = ['관련검색어가 없습니다.']
            succesed = False

        except Exception as e:
            print(f'예상치 못한 오류가 발생했습니다. 오류코드 : {sys.exc_info.__name__}')
            result = ['관련검색어가 없습니다.']
            succesed = False
        
        finally:
            json_result = {
                'keyword':keyword,
                'result':result
            }
            return json_result, succesed
        
    def Search_NaverShopping(self, keyword, delay:float):
        result = []
        url = f'https://msearch.shopping.naver.com/search/all?query={keyword}&prevQuery={keyword}'
        self.driver.get(url=url)
        time.sleep(delay)
        try:
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            targets = soup.find_all(class_='intentKeyword_list_pannel__thfp_')
            result = []
            for target in targets:
                a_tags = target.find_all('a')
                for tag in a_tags:
                    result.append(tag.text)

            data ={
                'keyword':keyword,
                'result':result,
            }
        except Exception as e:
            print(e)
            data ={
                'keyword':keyword,
                'result':"관련 검색어가 없습니다.",
            }
        

        return data, True
    

