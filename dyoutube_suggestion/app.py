from fastapi import FastAPI, HTTPException, Request
import logging
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
import os

from scraper import Scraper

app = FastAPI(
    title="YouTube Suggestion Scraper",
    description="유튜브 검색어 추천 스크래핑 API",
    version="1.0.0"
)

# Browser crawling uses significant container resources, so keep it serial by default.
executor = ThreadPoolExecutor(
    max_workers=int(os.getenv("SCRAPER_MAX_WORKERS", "1")),
    thread_name_prefix="scraper_worker"
)

# 로거 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - [%(threadName)s] - %(message)s"
)
logger = logging.getLogger("uvicorn")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutting down")

@app.middleware("http")
async def log_requests(request: Request, call_next):
    ip_address = request.client.host
    start_time = time.time()
    response = await call_next(request)
    duration_time = round(time.time() - start_time, 2)
    logger.info(f"{request.method} {request.url.path} from IP: {ip_address} Status: {response.status_code} Duration: {duration_time}s")
    return response

def get_suggestions_sync(keyword: str):
    logger.info(f"[WORKER] Starting get_suggestions_sync for keyword: {keyword}")
    scraper = Scraper()
    try:
        suggestions = scraper.get_suggestions(keyword)
        return suggestions
    except Exception as e:
        logger.error(f"[WORKER] Error in suggestion logic: {e}")
        return {
            "keyword": keyword,
            "result": [],
            "error": "internal_error",
            "detail": str(e)[:500],
        }

@app.get("/search/suggestions")
async def search_suggestions(keyword: str):
    """
    Search suggestions for a given keyword.
    Example: /search/suggestions?keyword=속건조
    """
    keyword = (keyword or "").strip()
    if not keyword:
        raise HTTPException(status_code=400, detail="Keyword is required")
        
    try:
        loop = asyncio.get_running_loop()
        # ThreadPoolExecutor를 사용하여 동기 함수를 비동기로 실행
        result = await loop.run_in_executor(executor, get_suggestions_sync, keyword)
        return result
    except Exception as e:
        logger.error(f"API Error: {e}")
        return {
            "keyword": keyword,
            "result": [],
            "error": "api_error",
            "detail": str(e)[:500],
        }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
