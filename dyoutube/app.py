from fastapi import FastAPI, HTTPException, Request
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

# 애플리케이션 시작 시 로거 설정
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("uvicorn")
process_lock = asyncio.Lock()

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

def list_task(keyword: str, limit: int = 3):
    result = {
        'keyword': keyword,
        'result': []
    }
    try:
        scraper = Scraper()
        # 이 함수가 최대 20분 정도 걸릴 수 있다고 가정
        result_data = scraper.get_list(keyword, limit)
        result = {
            'keyword': keyword,
            'result': result_data
        }
    except Exception as e:
        traceback.print_exc()
        # 필요하다면 로깅 추가
        logger.error(f"Exception in list_task: {e}")
    return result

@app.get("/search/list")
async def search_list(keywords: str, limit: int = 20):
    logger.info(f"Requested keywords: {keywords}, limit: {limit}")

    async with process_lock:
        try:
            loop = asyncio.get_running_loop()
            # 최대 20분(1200초)까지 대기
            result = await asyncio.wait_for(
                loop.run_in_executor(executor, list_task, keywords, limit),
                timeout=1200
            )
            logger.info(f"List result for {keywords}: {result}")
        except asyncio.TimeoutError:
            logger.error(f"Task timed out for keyword: {keywords}")
            raise HTTPException(status_code=504, detail="The operation took too long and timed out.")
        except Exception as e:
            logger.error(f"Error: {e} keyword: {keywords}")
            traceback.print_exc()
            raise HTTPException(status_code=500, detail="Internal Server Error")

        return result

