from fastapi import FastAPI
from driver_manager import DriverManager
from scraper import Scraper
from urllib3.exceptions import TimeoutError, MaxRetryError


import re
import time

app = FastAPI()
driver_manager = DriverManager()
scraper = Scraper(driver=driver_manager.driver, driver_manager=driver_manager)

response_count = 0

@app.get("/search/naver/popular")
async def search_naver_popular(keywords: str):
    global response_count
    try:
      response_count += 1
      result = scraper.scrape_naver_popular(keyword=keywords, delay=0.5)
      print(result)
      return result
    except MaxRetryError:
      driver_manager.restart_driver(scraper.driver)

      data = {
          'keyword': keywords,
          'popular_contents': '인기 주제가 없습니다.'
      }
      return data
    except Exception as e:
      driver_manager.restart_driver(scraper.driver)
      result = scraper.scrape_naver_popular(keyword=keywords, delay=0.5)
      print(result)
      return result
    
    finally:
      if response_count > 30:
        scraper.driver = driver_manager.restart_driver(scraper.driver)
        response_count = 0
