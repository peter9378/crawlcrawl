import requests
import time
import asyncio
import json
from urllib.parse import unquote

async def send_request(session, request_url:str, keyword:str):
    async with session.get(f'{request_url}?keywords={keyword}') as response:
        return await response.text()

async def test_navershopping():
    query = ['샴푸바', '고체샴푸', '설거지바', '설거지비누', '린스바', '고체비누', '세안바', '워싱바', '동구밭', '빌리메이', '솝24', '오이로이', '지미프로젝트', '러쉬', '마마포레스트', '두피엔', '톤28', '쿠켄도르', '소미지', '세안', '설거지', '샴푸', '탈모', '탈모 샴푸', '친환경 샴푸', '천연 샴푸', '약산성 샴푸']
    limit = 20000
    success = 0
    failed = 0
    while True:
        for keyword in query:
            response = requests.get(f'http://localhost:8001/search/navershopping?keywords={keyword}')
            # print(response.text)
            response_json = json.loads(response.text)
            try:
                result = response_json['result']
                if result:
                    success += 1
            except Exception as e:
                print(f'Error: {e}')
                failed += 1
            # if response
            limit -= 1
        if limit == 0:
            break
    print(f'Success: {success}, Failed: {failed}')

async def test_naver():
    query = ['샴푸바', '고체샴푸', '설거지바', '설거지비누', '린스바', '고체비누', '세안바', '워싱바', '동구밭', '빌리메이', '솝24', '오이로이', '지미프로젝트', '러쉬', '마마포레스트', '두피엔', '톤28', '쿠켄도르', '소미지', '세안', '설거지', '샴푸', '탈모', '탈모 샴푸', '친환경 샴푸', '천연 샴푸', '약산성 샴푸']
    limit = 20000
    success = 0
    failed = 0
    while True:
        for keyword in query:
            response = requests.get(f'http://localhost:8001/search/naver?keywords={keyword}')
            # print(response.text)
            response_json = json.loads(response.text)
            try:
                result = response_json['result']
                if result:
                    success += 1
            except Exception as e:
                print(f'Error: {e}')
                failed += 1
            # if response
            limit -= 1
        if limit == 0:
            break
    print(f'Success: {success}, Failed: {failed}')

if __name__ == '__main__':
    asyncio.run(test_navershopping())
    # asyncio.run(test_naver())