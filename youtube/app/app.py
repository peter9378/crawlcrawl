from fastapi import FastAPI
from crawler import Crawler
from api import Scraper
from concurrent.futures import ThreadPoolExecutor
import asyncio

import re
import time
import logging
from datetime import datetime

app = FastAPI()
executor = ThreadPoolExecutor(max_workers=4)

def youtube_task(keyword:str, limit:int):
    keyword = keyword.split(',')
    result = []
    scraper = Scraper()
    for index, keyword in enumerate(keyword):
        data = {
            'keyword':keyword,
            'result':scraper.search_list(keyword=keyword, limit=limit)
        }
        # print(f'{index}   {data}')
        result.append(data)
    if len(result) == 0 :
        for index, keyword in enumerate(keyword):
            data = {
                'keyword':keyword,
                'result':scraper.search_list(keyword=keyword, limit=limit)
            }
            # print(f'{index}   {data}')
            result.append(data)
    return result

@app.get("/search/youtube")
async def search_youtube(keywords: str, limit:int=250):
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(executor, youtube_task, keywords, limit)
        return result
    except Exception as e:
        print(f'Error: {e}')
        return {'error':str(e)}
    
@app.middleware("http")
async def log_requests(request, call_next):
    # Get the current logger
    logger = logging.getLogger('uvicorn')
    
    # Remove all handlers from the logger
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Get the current date and create a log file name
    current_date = datetime.now().strftime('%Y-%m-%d')
    log_filename = f'app-{current_date}.log'
    
    # Create a new handler with the new log file name
    handler = logging.FileHandler(log_filename, 'a')
    handler.setFormatter(logging.Formatter('%(name)s - %(levelname)s - %(message)s'))
    
    # Add the new handler to the logger
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    
    ip_address = request.client.host
    request_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    start_time = time.time()
    logger.info(f"Incoming request: {request.method} {request.url} from IP: {ip_address} at {request_time}")
    response = await call_next(request)
    end_time = time.time()
    duration_time = round(end_time - start_time, 2)  # 소수점 두 자리까지 반올림
    logger.info(f"{request.method} {request.url} from IP : {ip_address} at Outgoing response: {response.status_code} Duration : {duration_time} seconds")
    
    return response
