"""
Gunicorn 설정 파일
프로덕션 환경에서 FastAPI 앱을 안정적으로 실행하기 위한 설정
"""
import multiprocessing
import os

# 서버 소켓
bind = "0.0.0.0:80"
backlog = 2048

# 워커 프로세스
# CPU 코어 수 * 2 + 1 (권장 공식)
# 환경변수로 오버라이드 가능
workers = int(os.getenv("GUNICORN_WORKERS", "2"))
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
max_requests = 1000  # 워커당 최대 요청 수 (메모리 누수 방지)
max_requests_jitter = 100  # 랜덤 지터 (모든 워커가 동시에 재시작되지 않도록)
timeout = 120  # Selenium 사용으로 긴 타임아웃 설정
graceful_timeout = 30  # Graceful shutdown 대기 시간
keepalive = 5

# 로깅
accesslog = "-"  # stdout
errorlog = "-"   # stderr
loglevel = os.getenv("LOG_LEVEL", "info")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# 프로세스 명명
proc_name = "dyoutube_scraper"

# 보안
limit_request_line = 4096
limit_request_fields = 100
limit_request_field_size = 8190

# 서버 메커니즘
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL (필요시 활성화)
# keyfile = None
# certfile = None

def on_starting(server):
    """서버 시작 시 호출"""
    server.log.info("Gunicorn server is starting")

def on_reload(server):
    """서버 리로드 시 호출"""
    server.log.info("Gunicorn server is reloading")

def when_ready(server):
    """서버가 준비되었을 때 호출"""
    server.log.info("Gunicorn server is ready. Spawning workers")

def pre_fork(server, worker):
    """워커 fork 전 호출"""
    pass

def post_fork(server, worker):
    """워커 fork 후 호출"""
    server.log.info(f"Worker spawned (pid: {worker.pid})")

def pre_exec(server):
    """새 마스터 프로세스 exec 전 호출"""
    server.log.info("Forked child, re-executing.")

def worker_int(worker):
    """워커가 SIGINT나 SIGQUIT을 받았을 때"""
    worker.log.info(f"Worker received INT or QUIT signal (pid: {worker.pid})")

def worker_abort(worker):
    """워커가 SIGABRT을 받았을 때"""
    worker.log.info(f"Worker received SIGABRT signal (pid: {worker.pid})")

def child_exit(server, worker):
    """워커가 종료되었을 때"""
    server.log.info(f"Worker exited (pid: {worker.pid})")

