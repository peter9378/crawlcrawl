from fastapi import FastAPI, HTTPException, Request
import logging
from datetime import datetime
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
import traceback
import atexit

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from scraper import Scraper
from selenium_pool import get_driver_pool, cleanup_driver_pool

app = FastAPI(
    title="YouTube Suggestion Scraper",
    description="유튜브 검색어 추천 스크래핑 API",
    version="1.0.0"
)

# ThreadPoolExecutor 설정
executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="scraper_worker")

# 로거 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - [%(threadName)s] - %(message)s"
)
logger = logging.getLogger("uvicorn")

# 종료 시 정리
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutting down, cleaning up driver pool...")
    cleanup_driver_pool()
    logger.info("Driver pool cleanup completed")

atexit.register(cleanup_driver_pool)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    ip_address = request.client.host
    start_time = time.time()
    response = await call_next(request)
    duration_time = round(time.time() - start_time, 2)
    logger.info(f"{request.method} {request.url.path} from IP: {ip_address} Status: {response.status_code} Duration: {duration_time}s")
    return response

# Scraper 인스턴스 생성 (필요하다면 전역으로 사용하거나 요청마다 생성)
# 여기서는 요청마다 Scraper를 생성하는 것이 일반적이지 않지만, 
# Scraper 클래스가 내부적으로 driver pool을 사용하므로 상태를 가지지 않는다면 괜찮음.
# 다만 Scraper 클래스 내부 구현을 보니 특별한 상태를 유지하지 않으므로, 
# 메서드를 정적(static)으로 호출하거나 매번 가볍게 인스턴스화 해도 됨.
# 하지만 효율성을 위해 전역 인스턴스를 하나 두거나, 
# get_suggestions 로직이 pool context manager를 사용하므로 
# 함수 내부에서 Scraper().get_suggestions(keyword)를 호출하면 됨.

def get_suggestions_sync(keyword: str):
    logger.info(f"[WORKER] Starting get_suggestions_sync for keyword: {keyword}")
    scraper = Scraper()
    try:
        suggestions = scraper.get_suggestions(keyword)
        return scraper.get_suggestions(keyword)
    except Exception as e:
        logger.error(f"[WORKER] Error in suggestion logic: {e}")
        # scraper.py 내부에서 로깅하고 있으므로 여기선 re-raise하거나 빈 리스트 반환
        raise e

@app.get("/search/suggestions")
async def search_suggestions(keyword: str):
    """
    Search suggestions for a given keyword.
    Example: /search/suggestions?keyword=속건조
    """
    if not keyword:
        raise HTTPException(status_code=400, detail="Keyword is required")
        
    try:
        loop = asyncio.get_running_loop()
        # ThreadPoolExecutor를 사용하여 동기 함수를 비동기로 실행
        result = await loop.run_in_executor(executor, get_suggestions_sync, keyword)
        return result
    except Exception as e:
        logger.error(f"API Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
