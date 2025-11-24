FROM python:3.8-slim

RUN apt-get update && apt-get install -yqq \
    wget \
    build-essential \
    python3-dev \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libu2f-udev \
    libvulkan1 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    libcurl3-gnutls \
    libcurl3-nss \
    libcurl4 && \
    wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    dpkg -i google-chrome-stable_current_amd64.deb && \
    rm google-chrome-stable_current_amd64.deb && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . .

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Gunicorn + Uvicorn workers로 실행
# gunicorn.conf.py 파일에서 설정 관리
# 주요 설정:
# - workers: 2 (환경변수 GUNICORN_WORKERS로 조정 가능)
# - worker-class: uvicorn.workers.UvicornWorker (ASGI 지원)
# - max-requests: 1000 (메모리 누수 방지를 위한 자동 워커 재시작)
# - timeout: 120초 (Selenium 작업을 위한 긴 타임아웃)
CMD ["gunicorn", "app:app", "-c", "gunicorn.conf.py"]
