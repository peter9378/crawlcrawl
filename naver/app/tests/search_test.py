import asyncio
from aiohttp import ClientSession
import random

def generate_random_string(length):
    # 한글 유니코드 범위
    start, end = (0xAC00, 0xD7A3)
    return ''.join(chr(random.randint(start, end)) for _ in range(length))

async def send_request(url):
    async with ClientSession() as session:
        random_string = generate_random_string(5)
        async with session.get(f'{url}?keywords={random_string}') as resp:
            print(f'Status code for {url} search: {resp.status}')

async def main():
    tasks = []
    for _ in range(200):
        tasks.append(send_request('http://localhost:8001/search/naver'))
        tasks.append(send_request('http://localhost:8001/search/navershopping'))
    await asyncio.gather(*tasks)

asyncio.run(main())