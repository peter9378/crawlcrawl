from fastapi import FastAPI, HTTPException
from selenium import webdriver
from bs4 import BeautifulSoup
from urllib.parse import unquote
import subprocess
import platform
import logging
from datetime import datetime
import time

import asyncio
from concurrent.futures import ThreadPoolExecutor

import traceback
from requests.exceptions import RequestException

from scraper import Scraper

# # 현재 날짜를 가져옵니다.
# current_date = datetime.now().strftime('%Y-%m-%d')
# # 로그 파일 이름을 설정합니다.
# log_filename = f'app-{current_date}.log'
# logging.basicConfig(filename=log_filename, filemode='w', format='%(name)s - %(levelname)s - %(message)s', level=logging.INFO)

app = FastAPI()
executor = ThreadPoolExecutor(max_workers=4)
def get_os_info():
    os_info = platform.system()
    if os_info == 'Windows':
        return 'Windows'
    elif os_info == 'Linux':
        return 'Linux'
    elif os_info == 'Darwin':
        return 'Mac'
cur_os = get_os_info()
enable_chromes = []

@app.middleware("http")
async def log_requests(request, call_next):
    # Get the current logger
    logger = logging.getLogger('uvicorn')
    
    # Remove all handlers from the logger
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Get the current date and create a log file name
    current_date = datetime.now().strftime('%Y-%m-%d')
    log_filename = f'app-{current_date}.log'
    
    # Create a new handler with the new log file name
    handler = logging.FileHandler(log_filename, 'a')
    handler.setFormatter(logging.Formatter('%(name)s - %(levelname)s - %(message)s'))
    
    # Add the new handler to the logger
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    
    ip_address = request.client.host
    request_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    start_time = time.time()
    logger.info(f"Incoming request: {request.method} {request.url} from IP: {ip_address} at {request_time}")
    response = await call_next(request)
    end_time = time.time()
    duration_time = round(end_time - start_time, 2)  # 소수점 두 자리까지 반올림
    logger.info(f"{request.method} {request.url} from IP : {ip_address} at Outgoing response: {response.status_code} Duration : {duration_time} seconds")
    
    return response

def naver_task(keywords: str):
    try:
        scraper = Scraper()
        result = scraper.scrape_naver(keywords)
        return result
    except Exception as e:
        traceback.print_exc()
        print(f'naver_task error: {e}')
    finally:
    #     if scraper.driver != None:
    #         scraper.driver.quit()
        remove_enable_pid(scraper.driver)
        chrome_manage(cur_os)

@app.get("/search/naver")
async def search_naver(keywords: str):
    try:
        loop = asyncio.get_event_loop()
        keywords = unquote(keywords, encoding='utf-8')
        result = await loop.run_in_executor(executor, naver_task, keywords)

        return result
    except RequestException:
        asyncio.sleep(3)
        result = await loop.run_in_executor(executor, naver_task, keywords)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    
def naver_shopping_task(keywords: str):
    result = {
        'keyword': keywords,
        'result': '검색 결과가 없습니다.'
    }
    try:
        scraper = Scraper()
        get_enable_pid(scraper.driver)
        # result = scraper.scrape_navershopping(keywords)
        result = scraper.scrape_naver_shop_keyword(keywords)
    except Exception as e:
        traceback.print_exc()
        print(f'naver_shopping_task error: {e}')
    finally:
        # if scraper.driver != None:
        #     scraper.driver.quit()
        remove_enable_pid(scraper.driver)
        chrome_manage(cur_os)
        return result

@app.get("/search/navershopping")
async def search_naver_shopping(keywords: str):
    logger = logging.getLogger('uvicorn')
    result = {
        'keyword': keywords,
        'result': '검색 결과가 없습니다.'
    }
    try:
        loop = asyncio.get_event_loop()
        keywords = unquote(keywords, encoding='utf-8')
        result = await loop.run_in_executor(executor, naver_shopping_task, keywords)
        logger.info(f"keyword: {keywords} result: {result}")
    except RequestException:
        asyncio.sleep(3)
        result = await loop.run_in_executor(executor, naver_shopping_task, keywords)
        logger.warning(f"keyword: {keywords} result: {result} at RequestException")
    except Exception as e:
        logger.error(f"Error: {e} keyword : {keywords} at traceback: {traceback.print_exc()}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        return result

def get_enable_pid(driver):
    pid = driver.service.process.pid
    enable_chromes.append(pid)
def remove_enable_pid(driver):
    pid = driver.service.process.pid
    if pid in enable_chromes:
        enable_chromes.remove(pid)
    
def chrome_manage(os:str):
    if os == 'Windows':
        list_command = 'tasklist /FI "IMAGENAME eq chrome.exe"'
        process = subprocess.Popen(["powershell", list_command], stdout=subprocess.PIPE)
        output = process.communicate()[0].decode('utf-8')
        lines = output.strip().split('\n')

        current_pids = [line.split()[1] for line in lines[3:]]

        kill_pids = [pid for pid in current_pids if int(pid) not in enable_chromes]

        for pid in kill_pids:
            subprocess.call('taskkill /F /PID {}'.format(pid), shell=True)
    elif os == 'Linux' or os == 'Mac':
        list_command = 'pgrep -f "chrome"'
        process = subprocess.Popen(list_command, shell=True, stdout=subprocess.PIPE)
        output = process.communicate()[0].decode('utf-8')
        current_pids = output.strip().split('\n')

        kill_pids = [pid for pid in current_pids if int(pid) not in enable_chromes]

        for pid in kill_pids:
            subprocess.call('pkill -TERM -P {}'.format(pid), shell=True)
