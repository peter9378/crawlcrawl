from fastapi import FastAPI, HTTPException
from selenium import webdriver
from bs4 import BeautifulSoup
from urllib.parse import unquote
import platform
import subprocess
import logging
from datetime import datetime
import time

import asyncio
from concurrent.futures import ThreadPoolExecutor

import traceback
from requests.exceptions import RequestException

from scraper import Scraper

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


def list_task(keyword: str, limit: int = 100):
    result = {
        'keyword' : keyword,
        'result'  : []
    }
    try:
        scraper = Scraper()
        result = scraper.get_list(keyword, limit)
        result = {
            'keyword': keyword,
            'result': result
        }
    except Exception as e:
        traceback.print_exc()
    finally:
        return result
@app.get("/search/list")
async def search_list(keywords: str, limit: int = 3):
    logger = logging.getLogger('uvicorn')
    result = {
        'keyword' : keywords,
        'result'  : []
    }
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(executor, list_task, keywords, limit)
        logger.info(f"List result: {result}")
    except Exception as e:
        logger.error(f"Error: {e} keyword : {keywords} at traceback: {traceback.print_exc()}")
        traceback.print_exc()
    finally:
        return result
def video_task(videoid: str):
    logger = logging.getLogger('uvicorn')
    video_url = f"https://www.youtube.com/watch?v={videoid}"
    try:
        scraper = Scraper()
        result = scraper.get_video_detail(video_url)
        logger.info(f"Video result: {result}")
    except Exception as e:
        logger.error(f"Error: {e} videoid : {videoid} at traceback: {traceback.print_exc()}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        scraper.driver.quit()
        return result
@app.get("/search/video")
async def search_video(videoid: str):
    logger = logging.getLogger('uvicorn')
    result = {
        'videoid': videoid,
        'result': '검색 결과가 없습니다.'
    }
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(executor, video_task, videoid)
    except Exception as e:
        logger.error(f"Error: {e} videoid : {videoid} at traceback: {traceback.print_exc()}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        return result

def shorts_task(videoid: str):
    logger = logging.getLogger('uvicorn')
    shorts_url = f"https://www.youtube.com/shorts/{videoid}"
    try:
        scraper = Scraper()
        result = scraper.get_shorts_detail(shorts_url)
        logger.info(f"Shorts result: {result}")
    except Exception as e:
        logger.error(f"Error: {e} videoid : {videoid} at traceback: {traceback.print_exc()}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        scraper.driver.quit()
        return result
@app.get("/search/shorts")
async def search_shorts(videoid: str):
    logger = logging.getLogger('uvicorn')
    result = {
        'videoid': videoid,
        'result': '검색 결과가 없습니다.'
    }
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(executor, shorts_task, videoid)
    except Exception as e:
        logger.error(f"Error: {e} videoid : {videoid} at traceback: {traceback.print_exc()}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        return result


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

# -----------------------not---used------------------------------

# def youtube_task(keyword: str, limit: int = 100):
#     try:
#         scraper = Scraper()
#         result = scraper.scrape_youtube(keyword, limit)
#         return result
#     except Exception as e:
#         traceback.print_exc()
#         print(f'youtube_task error: {e}')
#     finally:
#         scraper.driver.quit()

# @app.get("/search/youtube")
# async def search_youtube(keywords: str, limit : int = 100):
#     logger = logging.getLogger('uvicorn')
#     result = {
#         'keyword': keywords,
#         'result': '검색 결과가 없습니다.'
#     }
#     try:
#         loop = asyncio.get_event_loop()
#         keyword = unquote(keywords, encoding='utf-8')
#         result = await loop.run_in_executor(executor, youtube_task, keyword, limit)
#     except RequestException:
#         asyncio.sleep(3)
#         result = await loop.run_in_executor(executor, youtube_task, keyword, limit)
#     except Exception as e:
#         logger.error(f"Error: {e} keyword : {keyword} at traceback: {traceback.print_exc()}")
#         raise HTTPException(status_code=500, detail=str(e))
#     finally:
#         return result
