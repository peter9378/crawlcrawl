# 경량화 Dockerfile.
# 핵심 절감 포인트:
#   1) 베이스를 python:3.11-slim-bookworm 으로 변경 (rockylinux:9 대비 ~60MB ↓)
#   2) wget/gnupg 등 빌드 도구는 사용 직후 purge
#   3) doc/man/locale 정리, --no-install-recommends 로 추천 패키지 제외
#   4) requirements.txt 를 코드보다 먼저 COPY 해서 레이어 캐시 효율 ↑
#
# 안정성:
#   - system Google Chrome stable 설치 (1순위 사용 — Scraper._find_chrome())
#   - playwright chromium 도 함께 설치 (2순위 fallback) — 어떤 경로에서도 launch 보장
FROM python:3.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    # host requirements 검증 스킵 — 모든 chromium/chrome 의존성은 아래 RUN 에서 명시 설치한다.
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

# ── Python 의존성 + playwright chromium fallback ──────────────────────────
WORKDIR /app
COPY requirements.txt ./
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    # playwright chromium 을 함께 설치 — system Google Chrome 을 못 찾는 경로에서도
    # default browser 로 launch 가 가능하도록 안전망을 둔다 (~250MB).
    playwright install chromium

# ── 앱 코드 ───────────────────────────────────────────────────────────────
COPY . .

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "80"]
