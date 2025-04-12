from fastapi import FastAPI, HTTPException
from scraper import Scraper
import re
from urllib.parse import unquote
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
import traceback
from requests.exceptions import RequestException
import logging

app = FastAPI()

executor = ThreadPoolExecutor(max_workers=4)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

def naver_blog_task(keywords: str, limit: int = 10):
    result = {
        'keyword': keywords,
        'result': []
    }
    try:
        scraper = Scraper()
        # keywords = re.sub(r'[^a-zA-Z0-9 ]', '', keywords)
        result = scraper.scrape_naver_blog(query=keywords, limit=limit)
        
    except Exception as e:
        traceback.print_exc()
    finally:
        return result

def naver_cafe_task(keywords: str, limit: int = 10):
    result = {
        'keyword': keywords,
        'result': []
    }
    try:
        scraper = Scraper()
        # keywords = re.sub(r'[^a-zA-Z0-9 ]', '', keywords)
        result = scraper.scrape_naver_cafe(query=keywords, limit=limit)
        
    except Exception as e:
        traceback.print_exc()
    finally:
        return result
    
@app.get("/search/naver_blog")
async def search_google(keywords: str, limit: int = 10):
    logger = logging.getLogger('uvicorn')
    print(f"keywords: {keywords}, limit: {limit}")
    result = {
        'keyword': keywords,
        'result': []
    }
    
    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(executor, naver_blog_task, keywords, limit)
    except Exception as e:
        logger.error(f"Error: {e} keyword : {keywords} at traceback: {traceback.print_exc()}")
        traceback.print_exc()
    finally:
        return result

@app.get("/search/naver_cafe")
async def search_google(keywords: str, limit: int = 10):
    logger = logging.getLogger('uvicorn')
    print(f"keywords: {keywords}, limit: {limit}")
    result = {
        'keyword': keywords,
        'result': []
    }
    
    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(executor, naver_cafe_task, keywords, limit)
    except Exception as e:
        logger.error(f"Error: {e} keyword : {keywords} at traceback: {traceback.print_exc()}")
        traceback.print_exc()
    finally:
        return result
    
if __name__ == '__main__':
    print(search_google(keywords='제일기획'))
