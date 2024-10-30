from fastapi import FastAPI, HTTPException
from driver_manager import DriverManager
from scraper import Scraper
import re
from urllib.parse import unquote
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
import psutil
import threading
import traceback
from requests.exceptions import RequestException

app = FastAPI()

executor = ThreadPoolExecutor(max_workers=4)

response_count = 0

def google_task(keywords: str):
    result = {
        'keyword': keywords,
        'result': '검색 결과가 없습니다.'
    }
    try:
        scraper = Scraper()
        # keywords = re.sub(r'[^a-zA-Z0-9 ]', '', keywords)
        driver_pid = scraper.driver.service.process.pid

        result = scraper.scrape_google(keyword=keywords, delay=0.5)
        
    except Exception as e:
        result = scraper.scrape_google(keyword=keywords, delay=0.5)
    finally:
        kill_browser(driver_pid)
        return result
    
def kill_browser(pid):
    try:
        driver_process = psutil.Process(pid)
    except psutil.NoSuchProcess:
        print(f'Process {pid} not found')
        return
    except Exception as e:
        traceback.print_exc()
        print(e)
    children = driver_process.children(recursive=True)
    for child in children:
        try:
            print(f'Terminating process {child.pid} ({child.name()})')
            child.terminate()
            child.wait(timeout=3)
        except psutil.NoSuchProcess:
            continue
        except psutil.TimeoutExpired:
            print(f'Force killing process {child.pid} ({child.name()})')
            child.kill()
    
    driver_process.kill()


@app.get("/search/google")
async def search_google(keywords: str):
    result = {
        'keyword': keywords,
        'result': '검색 결과가 없습니다.'
    }
    loop = asyncio.get_event_loop()
    try:
        keywords = unquote(keywords, encoding='utf-8')
        result = await loop.run_in_executor(executor, google_task, keywords)
    except RequestException:
        asyncio.sleep(3)
        result = await loop.run_in_executor(executor, google_task, keywords)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        return result
    
if __name__ == '__main__':
    print(search_google(keywords='제일기획'))
