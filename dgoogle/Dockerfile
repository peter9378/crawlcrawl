# 경량화 Dockerfile.
# 핵심 절감 포인트:
#   1) 베이스를 python:3.11-slim-bookworm 으로 변경 (rockylinux:9 대비 ~60MB ↓)
#   2) playwright 의 chromium 다운로드(playwright install chromium) 의도적으로 생략 (~250MB ↓).
#      scraper.py 의 Scraper._find_chrome() 이 system google-chrome 을 자동 사용한다.
#   3) wget/gnupg 등 빌드 도구는 사용 직후 purge
#   4) requirements.txt 를 코드보다 먼저 COPY 해서 레이어 캐시 효율 ↑
FROM python:3.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    # Playwright 의 chromium 다운로드를 건너뛰고 host validation 도 스킵.
    # scraper.py 가 executable_path 로 system Google Chrome 을 명시 주입한다.
    PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 \
    PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1

# ── 시스템 의존성 + Google Chrome stable + Xvfb ────────────────────────────
# google-chrome-stable .deb 가 대부분의 그래픽/사운드/X11 의존성을 자동 설치하지만
# playwright host requirements 검증이 검사하는 일부(libatspi2.0-0 등)는 명시한다.
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        wget \
        gnupg \
        ca-certificates \
        xvfb \
        fonts-liberation \
        libglib2.0-0 \
        libnss3 \
        libnspr4 \
        libdbus-1-3 \
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libatspi2.0-0 \
        libxcomposite1 \
        libxdamage1 \
        libgbm1 \
        libxkbcommon0 \
        libasound2; \
    wget -q -O- https://dl.google.com/linux/linux_signing_key.pub \
        | gpg --dearmor > /usr/share/keyrings/google-chrome.gpg; \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" \
        > /etc/apt/sources.list.d/google-chrome.list; \
    apt-get update; \
    apt-get install -y --no-install-recommends google-chrome-stable; \
    # google-chrome-stable .deb 의 alternatives 시스템이 슬림 베이스에서 누락될 수 있어
    # /usr/bin/google-chrome 심볼릭 링크를 명시 보장한다.
    if [ ! -e /usr/bin/google-chrome ]; then \
        ln -s /opt/google/chrome/google-chrome /usr/bin/google-chrome; \
    fi; \
    # 동작 검증: chrome 이 정상 실행되는지 (의존성 누락 시 여기서 빌드 실패)
    /usr/bin/google-chrome --version; \
    apt-get purge -y --auto-remove wget gnupg; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/* /var/cache/apt /tmp/* /var/tmp/* \
           /usr/share/doc /usr/share/man /usr/share/locale/*

# ── Python 의존성 ─────────────────────────────────────────────────────────
WORKDIR /app
COPY requirements.txt ./
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# ── 앱 코드 ───────────────────────────────────────────────────────────────
COPY . .

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "80"]
