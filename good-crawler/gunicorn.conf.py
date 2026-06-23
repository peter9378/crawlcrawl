import os


host = os.getenv("HOST", "0.0.0.0")
port = os.getenv("PORT", "80")
bind = f"{host}:{port}"
worker_class = "uvicorn.workers.UvicornWorker"
workers = int(os.getenv("WEB_CONCURRENCY", "1"))
threads = 1
timeout = int(os.getenv("GUNICORN_TIMEOUT", "180"))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "2"))
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
preload_app = False
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", "25"))
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", "5"))

# Avoid accidental multi-process browser fan-out on tiny servers.
if workers != 1:
    workers = 1
