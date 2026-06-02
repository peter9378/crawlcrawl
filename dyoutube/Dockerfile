# syntax=docker/dockerfile:1
FROM python:3.11-slim-bookworm

ENV CHROMEDRIVER_PATH=/usr/local/bin/chromedriver \
    DEBIAN_FRONTEND=noninteractive

# apt/curl 단계는 호스트 네트워크 사용 (Docker 빌드 DNS 127.0.0.11 실패 대응)
RUN --network=host apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    unzip \
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
    && rm -rf /var/lib/apt/lists/*

RUN --network=host CHROME_VERSION="$(curl -fsSL https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_STABLE)" && \
    curl -fsSL "https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chrome-linux64.zip" -o /tmp/chrome.zip && \
    curl -fsSL "https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chromedriver-linux64.zip" -o /tmp/chromedriver.zip && \
    unzip -q /tmp/chrome.zip -d /opt && \
    unzip -q /tmp/chromedriver.zip -d /opt && \
    ln -sf /opt/chrome-linux64/chrome /usr/local/bin/google-chrome && \
    ln -sf /opt/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver && \
    rm -f /tmp/chrome.zip /tmp/chromedriver.zip

WORKDIR /app

COPY requirements.txt .
RUN --network=host pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["gunicorn", "app:app", "-c", "gunicorn.conf.py"]
