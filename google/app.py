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
import logging

app = FastAPI()

executor = ThreadPoolExecutor(max_workers=4)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

def google_task(keywords: str, limit: int = 10):
    result = {
        'keyword': keywords,
        'result': []
    }
    try:
        scraper = Scraper()
        # keywords = re.sub(r'[^a-zA-Z0-9 ]', '', keywords)
        result = scraper.scrape_google(query=keywords, limit=limit)
        
    except Exception as e:
        traceback.print_exc()
    finally:
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
async def search_google(keywords: str, limit: int = 10):
    logger = logging.getLogger('uvicorn')
    print(f"keywords: {keywords}, limit: {limit}")
    result = {
        'keyword': keywords,
        'result': []
    }
    
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(executor, google_task, keywords, limit)
    except Exception as e:
        logger.error(f"Error: {e} keyword : {keywords} at traceback: {traceback.print_exc()}")
        traceback.print_exc()
    finally:
        return result
    
if __name__ == '__main__':
    print(search_google(keywords='제일기획'))
