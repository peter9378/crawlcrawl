from fastapi import FastAPI, HTTPException, Request
import logging
from datetime import datetime
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
import traceback
import atexit

from scraper import Scraper
from selenium_pool import get_driver_pool, cleanup_driver_pool

app = FastAPI(
    title="YouTube Scraper",
    description="유튜브 검색 결과 스크래핑 API - 드라이버 풀링으로 성능 최적화",
    version="2.0.0"
)

# ThreadPoolExecutor 설정 (8GB 메모리 안정을 위해 max_workers 제한)
executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="scraper_worker")

# 애플리케이션 시작 시 로거 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - [%(threadName)s] - %(message)s"
)
logger = logging.getLogger("uvicorn")

# 애플리케이션 종료 시 드라이버 풀 정리
@app.on_event("shutdown")
async def shutdown_event():
    """애플리케이션 종료 시 리소스 정리"""
    logger.info("Application shutting down, cleaning up driver pool...")
    cleanup_driver_pool()
    logger.info("Driver pool cleanup completed")

# 프로세스 종료 시에도 정리
atexit.register(cleanup_driver_pool)

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
    """유튜브 검색 작업 (동기 함수)
    
    Args:
        keyword: 검색 키워드
        limit: 검색 결과 개수
        
    Returns:
        검색 결과 딕셔너리
    """
    logger.info(f"[WORKER] Starting list_task for: {keyword}, limit: {limit}")
    result = {
        'keyword': keyword,
        'result': []
    }
    try:
        scraper = Scraper()
        result_data = scraper.get_list(keyword, limit)
        result = {
            'keyword': keyword,
            'result': result_data
        }
        logger.info(f"[WORKER] Completed list_task for: {keyword}, found {len(result_data)} results")
    except Exception as e:
        traceback.print_exc()
        logger.error(f"[WORKER] Exception in list_task: {e}")
    return result

@app.get(
    "/search/list",
    summary="유튜브 검색 결과 스크래핑",
    description="유튜브 검색 결과를 스크래핑합니다. 드라이버 풀을 사용하여 성능을 최적화했습니다.",
    response_model=None
)
async def search_list(keywords: str, limit: int = 20):
    """유튜브 검색 결과 스크래핑 엔드포인트
    
    Args:
        keywords: 검색 키워드
        limit: 검색 결과 개수 (기본값: 20)
        
    Returns:
        {'keyword': str, 'result': [동영상 정보들...]}
        
    Raises:
        HTTPException: 입력 검증 실패 또는 스크래핑 실패 시
    """
    logger.info(f"[API] Received request - keywords: {keywords}, limit: {limit}")

    # 입력 검증
    keywords = keywords.strip()
    if not keywords:
        logger.error("[API] Empty keyword received.")
        raise HTTPException(status_code=400, detail="Keyword cannot be empty.")

    if limit <= 0:
        logger.error("[API] Invalid limit received.")
        raise HTTPException(status_code=400, detail="Limit must be greater than 0.")

    try:
        loop = asyncio.get_running_loop()
        # 최대 20분(1200초)까지 대기
        result = await asyncio.wait_for(
            loop.run_in_executor(executor, list_task, keywords, limit),
            timeout=1200
        )
        logger.info(f"[API] Successfully completed search for {keywords}")
    except asyncio.TimeoutError:
        logger.error(f"[API] Task timed out for keyword: {keywords}")
        raise HTTPException(status_code=504, detail="The operation took too long and timed out.")
    except Exception as e:
        logger.error(f"[API] Error: {e}, keyword: {keywords}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal Server Error")

    return result

@app.get(
    "/health",
    summary="헬스체크",
    description="서비스 상태 확인"
)
async def health_check():
    """서비스 헬스체크 엔드포인트"""
    return {
        "status": "healthy",
        "service": "dyoutube_scraper",
        "version": "2.0.0",
        "note": "Using Selenium driver pool for better performance"
    }

@app.get(
    "/stats",
    summary="드라이버 풀 통계",
    description="Selenium 드라이버 풀 사용 통계 확인"
)
async def get_stats():
    """드라이버 풀 통계 엔드포인트"""
    pool = get_driver_pool()
    stats = pool.get_stats()
    
    return {
        "driver_pool_stats": stats,
        "description": {
            "total_requests": "총 Selenium 요청 수",
            "driver_restarts": "드라이버 재시작 횟수",
            "driver_errors": "드라이버 에러 발생 횟수"
        }
    }

@app.get(
    "/",
    summary="API 정보",
    description="API 기본 정보"
)
async def root():
    """루트 엔드포인트"""
    return {
        "service": "YouTube Scraper API",
        "version": "2.0.0",
        "endpoints": {
            "search": "/search/list?keywords={keyword}&limit={limit}",
            "health": "/health",
            "stats": "/stats"
        },
        "features": [
            "🚀 Selenium 드라이버 풀 사용 (성능 향상)",
            "🔄 자동 드라이버 재시작 (메모리 누수 방지)",
            "⏱️ 타임아웃 설정으로 무한 대기 방지",
            "🧹 리소스 안전 정리 보장"
        ],
        "performance": {
            "driver_pooling": "매 요청마다 Chrome을 열지 않고 재사용",
            "first_request": "3-10초 (드라이버 생성 포함)",
            "subsequent_requests": "더 빠른 응답 (드라이버 재사용)",
            "auto_restart": "100개 요청마다 드라이버 자동 재시작"
        },
        "note": "첫 요청은 드라이버 생성으로 느릴 수 있지만, 이후 요청은 더 빠릅니다!"
    }

