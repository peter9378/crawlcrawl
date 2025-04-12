from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import logging
import os
import time
from datetime import datetime, timedelta
import traceback
from selenium_driver import SeleniumDriver

# 설정
QUERY = '%EB%8D%B0%EB%B9%84%EB%A7%88%EC%9D%B4%EC%96%B4'
START_URL = f'https://www.youtube.com/results?search_query={QUERY}'          # 시작하려는 웹사이트의 URL로 변경하세요
OUTPUT_DIR = 'page_sources'                    # 페이지 소스를 저장할 디렉토리 이름


# 저장 디렉토리 생성
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

with SeleniumDriver(start_url=START_URL) as selenium_context:
    driver = selenium_context.driver
    driver.get(START_URL)
    time.sleep(3)  # 페이지 로드 대기

    # 현재 페이지의 HTML 소스 가져오기
    page_source = driver.page_source

    # 파일 경로 설정
    file_path = os.path.join(OUTPUT_DIR, f'debi.txt')

    # 파일로 저장
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(page_source)

driver.quit()
print('크롤링 종료.')

