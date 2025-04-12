from fastapi import FastAPI, HTTPException
from scraper import Scraper
import re
from urllib.parse import unquote
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
import threading
import traceback
from requests.exceptions import RequestException
import logging

app = FastAPI()

executor = ThreadPoolExecutor(max_workers=4)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

def naver_related(keywords: str):
    result = {
        'keyword': keywords,
        'result': []
    }
    try:
        scraper = Scraper()
        # keywords = re.sub(r'[^a-zA-Z0-9 ]', '', keywords)
        result = scraper.scrape_naver_related(query=keywords)
        
    except Exception as e:
        traceback.print_exc()
    finally:
        return result

def naver_popular(keywords: str):
    result = {
        'keyword': keywords,
        'result': []
    }
    try:
        scraper = Scraper()
        # keywords = re.sub(r'[^a-zA-Z0-9 ]', '', keywords)
        result = scraper.scrape_naver_popular(query=keywords)
        
    except Exception as e:
        traceback.print_exc()
    finally:
        return result

def naver_together(keywords: str):
    result = {
        'keyword': keywords,
        'result': []
    }
    try:
        scraper = Scraper()
        # keywords = re.sub(r'[^a-zA-Z0-9 ]', '', keywords)
        result = scraper.scrape_naver_together(query=keywords)
        
    except Exception as e:
        traceback.print_exc()
    finally:
        return result

@app.get("/search/naver_related")
async def related(keywords: str):
    logger = logging.getLogger('uvicorn')
    print(f"연관검색어 keywords: {keywords}")
    result = {
        'keyword': keywords,
        'result': []
    }
    
    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(executor, naver_related, keywords)
    except Exception as e:
        logger.error(f"Error: {e} keyword : {keywords} at traceback: {traceback.print_exc()}")
        traceback.print_exc()
    finally:
        return result

@app.get("/search/naver_popular")
async def popular(keywords: str):
    logger = logging.getLogger('uvicorn')
    print(f"인기주제 keywords: {keywords}")
    result = {
        'keyword': keywords,
        'result': []
    }
    
    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(executor, naver_popular, keywords)
    except Exception as e:
        logger.error(f"Error: {e} keyword : {keywords} at traceback: {traceback.print_exc()}")
        traceback.print_exc()
    finally:
        return result
    
@app.get("/search/naver_together")
async def together(keywords: str):
    logger = logging.getLogger('uvicorn')
    print(f"함께찾은 keywords: {keywords}")
    result = {
        'keyword': keywords,
        'result': []
    }
    
    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(executor, naver_together, keywords)
    except Exception as e:
        logger.error(f"Error: {e} keyword : {keywords} at traceback: {traceback.print_exc()}")
        traceback.print_exc()
    finally:
        return result

if __name__ == '__main__':
    print(popular(keywords='제일기획'))
