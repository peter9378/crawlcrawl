from fastapi import FastAPI, HTTPException, Response, Request
import logging
from urllib.parse import quote

from datetime import datetime
import time
from concurrent.futures import ThreadPoolExecutor
import shlex
import asyncio
import traceback
import json

from scraper import Scraper

app = FastAPI()
executor = ThreadPoolExecutor(max_workers=4)
current_server_index = 0
max_retries = 3  # 재시도 가능한 최대 횟수 설정
logger = logging.getLogger("uvicorn")

def shopping_related(keyword: str):
    result = {
        'keyword': keyword,
        'result': []
    }
    try:
        scraper = Scraper()
        result_data = scraper.scrape_naver_shop_related_tags(keyword)
        result = {
            'keyword': keyword,
            'result': result_data
        }
    except Exception as e:
        traceback.print_exc()
        logger.error(f"Exception in list_task: {e}")
    return result

@app.get("/youtube")
async def youtube(keywords: str, limit: int, retry_count: int = 0):
    global current_server_index

    SSH_USER = 'root'       # Replace with your SSH username
    SERVERS = [
        {'host': '27.96.135.171', 'port': 1234},
        {'host': '118.67.129.181', 'port': 1234},
        {'host': '118.67.135.127', 'port': 1234},
        {'host': '101.101.218.102', 'port': 1234}
    ]

    # 재시도가 아닐 때에만 서버 인덱스를 업데이트(라운드 로빈)
    if retry_count == 0:
        server = SERVERS[current_server_index]
        current_server_index = (current_server_index + 1) % len(SERVERS)
    else:
        # 재시도 중이라면 이전에 선택된 서버로 재시도
        server = SERVERS[(current_server_index - 1) % len(SERVERS)]
    print(f"[Server index: {current_server_index}] 서버 정보: {server}")

    # Build the query string
    query_params = f"keywords={quote(keywords)}&limit={limit}"
    print(f"쿼리 파라미터: {query_params}")

    # Build the full URL
    url = f"http://localhost:{server['port']}/search/list?{query_params}"

    # Build the curl command as a list
    curl_command = ['curl', '-s', '-X', 'GET', url]

    # Build the command string
    curl_cmd_str = shlex.join(curl_command)

    # Build the SSH command
    ssh_command = ['ssh', f"{SSH_USER}@{server['host']}", '--', curl_cmd_str]

    # Execute the SSH command
    process = await asyncio.create_subprocess_exec(
        *ssh_command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()

    # Handle errors
    if process.returncode != 0:
        return Response(content=stderr.decode('utf-8'), status_code=500)

    # stdout 이 비어 있는 경우 재시도 로직
    content = stdout.decode('utf-8')
    if not content.strip():
        # 아직 재시도 횟수가 남아 있으면 다시 호출
        if retry_count < max_retries:
            print(f"데이터가 비어있어 재시도합니다. (시도 횟수: {retry_count + 1}) (현재 서버: {server}")
            return await youtube(keywords, limit, retry_count=retry_count + 1)
        else:
            # 재시도를 모두 소진했는데도 데이터가 비어 있다면 에러 반환
            print("여러 번 재시도했지만 여전히 데이터가 비어 있습니다.")
            return Response(content="데이터 수신에 실패했습니다.", status_code=500)

    # Return the response from server
    return Response(content=stdout.decode('utf-8'), media_type='application/json', status_code=200)

@app.get("/google")
async def google(keywords: str, limit: int = 10):
    SSH_USER = 'root'       # Replace with your SSH username
    SSH_HOST = '118.67.129.100'  # Replace with your server A hostname or IP
    REMOTE_PORT = 2345          # Port on which server A is running the API
    # Build the query string
    query_params = f"keywords={quote(keywords)}&limit={limit}"
    print(query_params)

    # Build the full URL
    url = f"http://localhost:{REMOTE_PORT}/search/google?{query_params}"

    # Build the curl command as a list
    curl_command = ['curl', '-s', '-X', 'GET', url]

    # Build the command string
    curl_cmd_str = shlex.join(curl_command)

    # Build the SSH command
    ssh_command = ['ssh', f'{SSH_USER}@{SSH_HOST}', '--', curl_cmd_str]

    # Execute the SSH command
    process = await asyncio.create_subprocess_exec(
        *ssh_command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()

    # Handle errors
    if process.returncode != 0:
        return Response(content=stderr.decode('utf-8'), status_code=500)

    # Return the response from server A
    return Response(content=stdout.decode('utf-8'), media_type='application/json', status_code=200)


@app.get("/naver_blog")
async def naverb(keywords: str, limit: int = 10):
    SSH_USER = 'root'       # Replace with your SSH username
    SSH_HOST = '115.85.183.222'  # Replace with your server A hostname or IP
    REMOTE_PORT = 1234          # Port on which server A is running the API
    # Build the query string
    query_params = f"keywords={quote(keywords)}&limit={limit}"
    print(query_params)

    # Build the full URL
    url = f"http://localhost:{REMOTE_PORT}/search/naver_blog?{query_params}"

    # Build the curl command as a list
    curl_command = ['curl', '-s', '-X', 'GET', url]

    # Build the command string
    curl_cmd_str = shlex.join(curl_command)

    # Build the SSH command
    ssh_command = ['ssh', f'{SSH_USER}@{SSH_HOST}', '--', curl_cmd_str]

    # Execute the SSH command
    process = await asyncio.create_subprocess_exec(
        *ssh_command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()

    # Handle errors
    if process.returncode != 0:
        return Response(content=stderr.decode('utf-8'), status_code=500)

    # Return the response from server A
    return Response(content=stdout.decode('utf-8'), media_type='application/json', status_code=200)
    
@app.get("/naver_cafe")
async def naverb(keywords: str, limit: int = 10):
    SSH_USER = 'root'       # Replace with your SSH username
    SSH_HOST = '115.85.183.222'  # Replace with your server A hostname or IP
    REMOTE_PORT = 1234          # Port on which server A is running the API
    # Build the query string
    query_params = f"keywords={quote(keywords)}&limit={limit}"
    print(query_params)

    # Build the full URL
    url = f"http://localhost:{REMOTE_PORT}/search/naver_cafe?{query_params}"

    # Build the curl command as a list
    curl_command = ['curl', '-s', '-X', 'GET', url]

    # Build the command string
    curl_cmd_str = shlex.join(curl_command)

    # Build the SSH command
    ssh_command = ['ssh', f'{SSH_USER}@{SSH_HOST}', '--', curl_cmd_str]

    # Execute the SSH command
    process = await asyncio.create_subprocess_exec(
        *ssh_command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()

    # Handle errors
    if process.returncode != 0:
        return Response(content=stderr.decode('utf-8'), status_code=500)

    # Return the response from server A
    return Response(content=stdout.decode('utf-8'), media_type='application/json', status_code=200)
    
@app.get("/naver_related")
async def naverr(keywords: str):
    SSH_USER = 'root'       # Replace with your SSH username
    SSH_HOST = '118.67.129.100'  # Replace with your server A hostname or IP
    REMOTE_PORT = 1234          # Port on which server A is running the API
    # Build the query string
    query_params = f"keywords={quote(keywords)}"
    print(query_params)

    # Build the full URL
    url = f"http://localhost:{REMOTE_PORT}/search/naver_related?{query_params}"

    # Build the curl command as a list
    curl_command = ['curl', '-s', '-X', 'GET', url]

    # Build the command string
    curl_cmd_str = shlex.join(curl_command)

    # Build the SSH command
    ssh_command = ['ssh', f'{SSH_USER}@{SSH_HOST}', '--', curl_cmd_str]

    # Execute the SSH command
    process = await asyncio.create_subprocess_exec(
        *ssh_command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()

    # Handle errors
    if process.returncode != 0:
        return Response(content=stderr.decode('utf-8'), status_code=500)

    # Return the response from server A
    return Response(content=stdout.decode('utf-8'), media_type='application/json', status_code=200)
    

@app.get("/naver_popular")
async def naverp(keywords: str):
    SSH_USER = 'root'       # Replace with your SSH username
    SSH_HOST = '118.67.129.100'  # Replace with your server A hostname or IP
    REMOTE_PORT = 1234          # Port on which server A is running the API
    # Build the query string
    query_params = f"keywords={quote(keywords)}"
    print(query_params)

    # Build the full URL
    url = f"http://localhost:{REMOTE_PORT}/search/naver_popular?{query_params}"

    # Build the curl command as a list
    curl_command = ['curl', '-s', '-X', 'GET', url]

    # Build the command string
    curl_cmd_str = shlex.join(curl_command)

    # Build the SSH command
    ssh_command = ['ssh', f'{SSH_USER}@{SSH_HOST}', '--', curl_cmd_str]

    # Execute the SSH command
    process = await asyncio.create_subprocess_exec(
        *ssh_command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()

    # Handle errors
    if process.returncode != 0:
        return Response(content=stderr.decode('utf-8'), status_code=500)

    # Return the response from server A
    return Response(content=stdout.decode('utf-8'), media_type='application/json', status_code=200)
    
@app.get("/naver_shopping") # naver_together(함께찾은 키워드임)
async def navers(keywords: str):
    SSH_USER = 'root'       # Replace with your SSH username
    SSH_HOST = '118.67.129.100'  # Replace with your server A hostname or IP
    REMOTE_PORT = 1234          # Port on which server A is running the API
    # Build the query string
    query_params = f"keywords={quote(keywords)}"
    print(query_params)

    # Build the full URL
    url = f"http://localhost:{REMOTE_PORT}/search/naver_together?{query_params}"

    # Build the curl command as a list
    curl_command = ['curl', '-s', '-X', 'GET', url]

    # Build the command string
    curl_cmd_str = shlex.join(curl_command)

    # Build the SSH command
    ssh_command = ['ssh', f'{SSH_USER}@{SSH_HOST}', '--', curl_cmd_str]

    # Execute the SSH command
    process = await asyncio.create_subprocess_exec(
        *ssh_command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()

    # Handle errors
    if process.returncode != 0:
        return Response(content=stderr.decode('utf-8'), status_code=500)

    # Return the response from server A
    return Response(content=stdout.decode('utf-8'), media_type='application/json', status_code=200)

@app.get("/naver_shopping_related") # 네이버 쇼핑 연관 검색어
async def naversr(keywords: str):
    keywords = keywords.strip()
    if not keywords:
        raise HTTPException(status_code=400, detail="Keyword cannot be empty.")

    try:
        loop = asyncio.get_running_loop()
        # 최대 20분(1200초)까지 대기
        result = await asyncio.wait_for(
            loop.run_in_executor(executor, shopping_related, keywords),
            timeout=1200
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="The operation took too long and timed out.")
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal Server Error")

    return Response(content=json.dumps(result).encode('utf-8'), media_type='application/json', status_code=200)
