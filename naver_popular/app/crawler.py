from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from selenium.common.exceptions import WebDriverException

from selenium.webdriver.common.by import By
import chromedriver_autoinstaller


import sys
import time
import os

class Crawler():
    def __init__(self) -> None:

        self.driver = None
        pass

    def Set_Browser(self):
        chromedriver_autoinstaller.install()
        # chromedriver_path = '../chromedriver'
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-infobars')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-extensions')
        options.add_argument('--temp-profile')
        options.add_argument('--disable-features=SearchProviderFirstRun')
        options.add_argument('--disable-geolocation')

        if self.driver == None:
            self.driver = webdriver.Chrome(options=options)
        else:
            self.driver.quit()
            self.driver = webdriver.Chrome(options=options)

    def Search_Naver_Popular(self, keyword:str, delay:float):
        url = f'https://search.naver.com/search.naver?sm=tab_hty.top&where=nexearch&query={keyword}'
        self.driver.get(url=url)
        try:
            wait = WebDriverWait(self.driver, 10)
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

            data = {
                'keyword':keyword,
                'popular_contents':popular_contents
            }
        except WebDriverException as e:
            self.Search_Naver_Popular(keyword=keyword, delay=0)
        except Exception as e:
            popular_contents = '인기 주제가 없습니다.'
            data = {
                'keyword':keyword,
                'popular_contents':popular_contents
            }
        return data, True