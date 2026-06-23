# Good Crawler

Minimal DrissionPage-based YouTube search crawler API.

## API

- `GET /health`
- `GET /search/youtube?query=쿠키&limit=10`

Response shape:

```json
{
  "query": "쿠키",
  "result": [
    {
      "rank": 1,
      "title": "video title",
      "url": "https://www.youtube.com/watch?v=...",
      "channel": "channel",
      "metadata": "views/date text"
    }
  ]
}
```

## Local Run

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
./run_local.sh
```

`run_local.sh` uses the same production stack as Docker: `gunicorn` with one `UvicornWorker`.

Then:

```bash
curl 'http://localhost:8080/health'
curl 'http://localhost:8080/search/youtube?query=쿠키&limit=5'
```

## Docker

```bash
docker build --platform linux/amd64 -t good-crawler .
docker run --rm -p 8080:80 good-crawler
```

The service is intentionally serialized with `CRAWLER_MAX_WORKERS=1`; each request starts and closes its own Chrome/Xvfb session and removes the temporary browser profile.
Gunicorn is also configured with `GUNICORN_MAX_REQUESTS=25` so the API worker is recycled periodically on small long-running hosts.
