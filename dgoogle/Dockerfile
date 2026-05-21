# 경량화 Dockerfile (~3.5GB → ~1.6GB 목표).
# 핵심 절감 포인트:
#   1) 베이스를 python:3.11-slim-bookworm 으로 변경 (rockylinux:9 대비 ~60MB ↓)
#   2) google-chrome-stable .deb 가 필요한 모든 그래픽/사운드/X11/폰트 의존성을 자동 설치하므로
#      개별 라이브러리 나열 제거 — 누락 위험도 동시에 제거
#   3) playwright 의 chromium 다운로드(playwright install chromium) 의도적으로 생략 (~250MB ↓).
#      scraper.py 의 Scraper._find_chrome() 이 /usr/bin/google-chrome 을 자동 사용한다.
#   4) wget/gnupg 등 빌드 도구는 사용 직후 purge
#   5) requirements.txt 를 코드보다 먼저 COPY 해서 레이어 캐시 효율 ↑
FROM python:3.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# ── Google Chrome stable + Xvfb 설치 ──────────────────────────────────────
# 단일 RUN 안에서 빌드 도구를 도입했다가 즉시 purge — 최종 이미지에 흔적이 남지 않게.
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        wget \
        gnupg \
        ca-certificates \
        xvfb \
        fonts-liberation; \
    wget -q -O- https://dl.google.com/linux/linux_signing_key.pub \
        | gpg --dearmor > /usr/share/keyrings/google-chrome.gpg; \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" \
        > /etc/apt/sources.list.d/google-chrome.list; \
    apt-get update; \
    apt-get install -y --no-install-recommends google-chrome-stable; \
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
