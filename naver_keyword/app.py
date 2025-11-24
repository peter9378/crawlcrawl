from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from scraper import Scraper, ScraperException
from selenium_pool import get_driver_pool, cleanup_driver_pool
import re
from urllib.parse import unquote
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
import threading
import traceback
from requests.exceptions import RequestException
import logging
from typing import Dict, Any
import atexit

app = FastAPI(
    title="Naver Keyword Scraper",
    description="네이버 키워드 스크래핑 API - 안정성, 재시도 로직, 속도 최적화 (모든 엔드포인트 Selenium 사용)",
    version="2.1.1"
)

# ThreadPoolExecutor 설정 (CPU 코어 * 2)
executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="scraper_worker")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - [%(threadName)s] - %(message)s"
)

logger = logging.getLogger('uvicorn')

# 애플리케이션 종료 시 드라이버 풀 정리
@app.on_event("shutdown")
async def shutdown_event():
    """애플리케이션 종료 시 리소스 정리"""
    logger.info("Application shutting down, cleaning up driver pool...")
    cleanup_driver_pool()
    logger.info("Driver pool cleanup completed")

# 프로세스 종료 시에도 정리
atexit.register(cleanup_driver_pool)

def naver_related(keywords: str) -> Dict[str, Any]:
    """연관검색어 스크래핑 (동기 함수)
    
    Args:
        keywords: 검색 키워드
        
    Returns:
        스크래핑 결과 딕셔너리
        
    Raises:
        ScraperException: 스크래핑 실패 시
    """
    logger.info(f"[WORKER] Starting naver_related for: {keywords}")
    scraper = Scraper()
    result = scraper.scrape_naver_related(query=keywords)
    logger.info(f"[WORKER] Completed naver_related for: {keywords}, found {len(result['result'])} results")
    return result

def naver_popular(keywords: str) -> Dict[str, Any]:
    """인기주제 스크래핑 (동기 함수)
    
    Args:
        keywords: 검색 키워드
        
    Returns:
        스크래핑 결과 딕셔너리
        
    Raises:
        ScraperException: 스크래핑 실패 시
    """
    logger.info(f"[WORKER] Starting naver_popular for: {keywords}")
    scraper = Scraper()
    result = scraper.scrape_naver_popular(query=keywords)
    logger.info(f"[WORKER] Completed naver_popular for: {keywords}, found {len(result['result'])} results")
    return result

def naver_together(keywords: str) -> Dict[str, Any]:
    """함께찾은 키워드 스크래핑 (동기 함수)
    
    Args:
        keywords: 검색 키워드
        
    Returns:
        스크래핑 결과 딕셔너리
        
    Raises:
        ScraperException: 스크래핑 실패 시
    """
    logger.info(f"[WORKER] Starting naver_together for: {keywords}")
    scraper = Scraper()
    result = scraper.scrape_naver_together(query=keywords)
    logger.info(f"[WORKER] Completed naver_together for: {keywords}, found {len(result['result'])} results")
    return result

@app.get(
    "/search/naver_related",
    summary="네이버 연관검색어 스크래핑",
    description="네이버 검색 연관검색어를 스크래핑합니다. 실패 시 HTTP 500 에러를 반환합니다.",
    response_model=None
)
async def related(keywords: str):
    """네이버 연관검색어 스크래핑 엔드포인트
    
    Args:
        keywords: 검색 키워드
        
    Returns:
        {'keyword': str, 'result': [{'rank': int, 'keyword': str}, ...]}
        
    Raises:
        HTTPException: 스크래핑 실패 시 500 에러
    """
    logger.info(f"[API] Received request for naver_related: {keywords}")
    
    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(executor, naver_related, keywords)
        logger.info(f"[API] Successfully completed naver_related: {keywords}")
        return result
        
    except ScraperException as e:
        error_msg = f"Scraping failed for keyword '{keywords}': {str(e)}"
        logger.error(f"[API] {error_msg}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "scraping_failed",
                "message": error_msg,
                "keyword": keywords
            }
        )
        
    except Exception as e:
        error_msg = f"Unexpected error for keyword '{keywords}': {str(e)}"
        logger.error(f"[API] {error_msg}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "internal_error",
                "message": error_msg,
                "keyword": keywords
            }
        )

@app.get(
    "/search/naver_popular",
    summary="네이버 인기주제 스크래핑",
    description="네이버 검색 인기주제를 스크래핑합니다. 실패 시 HTTP 500 에러를 반환합니다.",
    response_model=None
)
async def popular(keywords: str):
    """네이버 인기주제 스크래핑 엔드포인트
    
    Args:
        keywords: 검색 키워드
        
    Returns:
        {'keyword': str, 'result': [{'rank': int, 'keyword': str}, ...]}
        
    Raises:
        HTTPException: 스크래핑 실패 시 500 에러
    """
    logger.info(f"[API] Received request for naver_popular: {keywords}")
    
    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(executor, naver_popular, keywords)
        logger.info(f"[API] Successfully completed naver_popular: {keywords}")
        return result
        
    except ScraperException as e:
        error_msg = f"Scraping failed for keyword '{keywords}': {str(e)}"
        logger.error(f"[API] {error_msg}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "scraping_failed",
                "message": error_msg,
                "keyword": keywords
            }
        )
        
    except Exception as e:
        error_msg = f"Unexpected error for keyword '{keywords}': {str(e)}"
        logger.error(f"[API] {error_msg}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "internal_error",
                "message": error_msg,
                "keyword": keywords
            }
        )
    
@app.get(
    "/search/naver_together",
    summary="네이버 함께찾은 키워드 스크래핑",
    description="네이버 검색 함께찾은 키워드를 스크래핑합니다 (Selenium 사용). 실패 시 HTTP 500 에러를 반환합니다.",
    response_model=None
)
async def together(keywords: str):
    """네이버 함께찾은 키워드 스크래핑 엔드포인트
    
    Args:
        keywords: 검색 키워드
        
    Returns:
        {'keyword': str, 'result': [{'rank': int, 'keyword': str}, ...]}
        
    Raises:
        HTTPException: 스크래핑 실패 시 500 에러
    """
    logger.info(f"[API] Received request for naver_together: {keywords}")
    
    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(executor, naver_together, keywords)
        logger.info(f"[API] Successfully completed naver_together: {keywords}")
        return result
        
    except ScraperException as e:
        error_msg = f"Scraping failed for keyword '{keywords}': {str(e)}"
        logger.error(f"[API] {error_msg}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "scraping_failed",
                "message": error_msg,
                "keyword": keywords
            }
        )
        
    except Exception as e:
        error_msg = f"Unexpected error for keyword '{keywords}': {str(e)}"
        logger.error(f"[API] {error_msg}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "internal_error",
                "message": error_msg,
                "keyword": keywords
            }
        )

@app.get(
    "/health",
    summary="헬스체크",
    description="서비스 상태 확인"
)
async def health_check():
    """서비스 헬스체크 엔드포인트"""
    return {
        "status": "healthy",
        "service": "naver_keyword_scraper",
        "version": "2.1.1",
        "note": "All endpoints use Selenium driver pool"
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
        "service": "Naver Keyword Scraper API",
        "version": "2.1.1",
        "endpoints": {
            "related": "/search/naver_related?keywords={keyword}",
            "popular": "/search/naver_popular?keywords={keyword}",
            "together": "/search/naver_together?keywords={keyword}",
            "health": "/health",
            "stats": "/stats"
        },
        "features": [
            "🚀 모든 엔드포인트 Selenium 드라이버 풀 사용",
            "🔄 강력한 재시도 로직 (지수 백오프)",
            "⏱️ 타임아웃 설정으로 무한 대기 방지",
            "🔧 세션 복구 기능",
            "🚨 명확한 에러 응답 (HTTP 500)",
            "🧹 리소스 안전 정리 보장",
            "♻️ 드라이버 자동 재시작 (메모리 누수 방지)"
        ],
        "performance": {
            "all_endpoints": "연관검색어, 인기주제, 함께찾은 키워드 모두 Selenium 사용",
            "driver_pooling": "매 요청마다 Chrome을 열지 않고 재사용",
            "first_request": "3-10초 (드라이버 생성 포함)",
            "subsequent_requests": "2-3초 (드라이버 재사용)",
            "auto_restart": "100개 요청마다 드라이버 자동 재시작"
        },
        "note": "첫 요청은 드라이버 생성으로 느릴 수 있지만, 이후 요청은 매우 빠릅니다!"
    }

if __name__ == '__main__':
    # 테스트용
    import asyncio
    result = asyncio.run(popular(keywords='제일기획'))
    print(result)
