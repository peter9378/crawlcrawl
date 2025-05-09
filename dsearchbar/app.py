from fastapi import FastAPI, HTTPException, Request
import logging
from datetime import datetime
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
import traceback

from scraper import Scraper

app = FastAPI()
executor = ThreadPoolExecutor(max_workers=4)

# 애플리케이션 시작 시 로거 설정
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("uvicorn")

@app.middleware("http")
async def log_requests(request: Request, call_next):
    ip_address = request.client.host
    start_time = time.time()

    response = await call_next(request)

    duration_time = round(time.time() - start_time, 2)
    logger.info(
        f"{request.method} {request.url.path} from IP: {ip_address} "
        f"Status: {response.status_code} Duration: {duration_time} seconds"
    )

    return response

@app.get("/test")
async def test():
    return {"result": "test success"}

def youtube_task(keyword: str):
    result = {
        'keyword': keyword,
        'result': []
    }
    try:
        scraper = Scraper()
        result_data = scraper.get_list(keyword)
        result = {
            'keyword': keyword,
            'result': result_data
        }
    except Exception as e:
        traceback.print_exc()
        logger.error(f"Exception in list_task: {e}")
    return result

def coupang_task(keyword: str):
    result = {
        'keyword': keyword,
        'result': []
    }
    try:
        scraper = Scraper()
        result_data = scraper.get_coupang_list(keyword)
        result = {
            'keyword': keyword,
            'result': result_data
        }
    except Exception as e:
        traceback.print_exc()
        logger.error(f"Exception in coupang_task: {e}")
    return result

@app.get("/search/youtube")
async def search_youtube(keywords: str):
    logger.info(f"Requested keywords: {keywords}")

    # 입력 검증
    keywords = keywords.strip()
    if not keywords:
        logger.error("Empty keyword received.")
        raise HTTPException(status_code=400, detail="Keyword cannot be empty.")

    try:
        loop = asyncio.get_running_loop()
        # 최대 20분(1200초)까지 대기
        result = await asyncio.wait_for(
            loop.run_in_executor(executor, youtube_task, keywords),
            timeout=1200
        )
        logger.info(f"List result for {keywords}: {result}")
    except asyncio.TimeoutError:
        logger.error(f"Task timed out for keyword: {keywords}")
        raise HTTPException(status_code=504, detail="The operation took too long and timed out.")
    except Exception as e:
        logger.error(f"Error: {e}, keyword: {keywords}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal Server Error")

    return result

@app.get("/search/coupang")
async def search_coupang(keywords: str):
    logger.info(f"Requested keywords for Coupang: {keywords}")

    # 입력 검증
    keywords = keywords.strip()
    if not keywords:
        logger.error("Empty keyword received for Coupang search.")
        raise HTTPException(status_code=400, detail="Keyword cannot be empty.")

    try:
        loop = asyncio.get_running_loop()
        # 최대 20분(1200초)까지 대기
        result = await asyncio.wait_for(
            loop.run_in_executor(executor, coupang_task, keywords),
            timeout=1200
        )
        logger.info(f"Coupang list result for {keywords}: {result}")
    except asyncio.TimeoutError:
        logger.error(f"Coupang task timed out for keyword: {keywords}")
        raise HTTPException(status_code=504, detail="The operation took too long and timed out.")
    except Exception as e:
        logger.error(f"Error in Coupang search: {e}, keyword: {keywords}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal Server Error")

    return result

