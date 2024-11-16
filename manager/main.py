from fastapi import FastAPI, Response
from urllib.parse import quote

import shlex
import asyncio

app = FastAPI()

SSH_USER = 'root'       # Replace with your SSH username
SSH_HOST = '27.96.135.171'  # Replace with your server A hostname or IP
REMOTE_PORT = 1234          # Port on which server A is running the API

@app.get("/youtube")
async def proxy(keywords: str, limit: int):
    # Build the query string
    query_params = f"keywords={quote(keywords)}&limit={limit}"
    print(query_params)

    # Build the full URL
    url = f"http://localhost:{REMOTE_PORT}/search/list?{query_params}"

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
    print("good!")
    stdout, stderr = await process.communicate()

    # Handle errors
    if process.returncode != 0:
        return Response(content=stderr.decode('utf-8'), status_code=500)

    # Return the response from server A
    return Response(content=stdout.decode('utf-8'), media_type='application/json', status_code=200)
