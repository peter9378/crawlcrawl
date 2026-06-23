import asyncio
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, HTTPException, Query, Request

from scraper import YouTubeCrawler


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - [%(threadName)s] - %(message)s",
)
logger = logging.getLogger("uvicorn")

app = FastAPI(
    title="Good Crawler",
    description="Minimal DrissionPage YouTube search crawler",
    version="0.1.0",
)

# Minimal servers should run one browser job at a time.
executor = ThreadPoolExecutor(
    max_workers=int(os.getenv("CRAWLER_MAX_WORKERS", "1")),
    thread_name_prefix="crawler_worker",
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started = time.time()
    response = await call_next(request)
    logger.info(
        "%s %s status=%s duration=%.2fs",
        request.method,
        request.url.path,
        response.status_code,
        time.time() - started,
    )
    return response


@app.get("/health")
async def health():
    return {"status": "ok"}


def crawl_sync(query: str, limit: int):
    crawler = YouTubeCrawler()
    return crawler.search(query=query, limit=limit)


@app.get("/search/youtube")
async def search_youtube(
    query: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=30),
):
    query = query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="query is required")

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(executor, crawl_sync, query, limit)
