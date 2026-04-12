# GCP Rocky Linux 환경 (RHEL-compatible)
FROM rockylinux:9

# ── 시스템 패키지 ──────────────────────────────────────────────────────────
RUN dnf install -y epel-release && \
    dnf install -y \
        python3 \
        python3-pip \
        wget \
        unzip \
        # Xvfb — 가상 디스플레이 (headless 없이 Chrome 실행)
        xorg-x11-server-Xvfb \
        # Chrome 의존 라이브러리
        alsa-lib \
        atk \
        at-spi2-atk \
        cups-libs \
        dbus-libs \
        gtk3 \
        libdrm \
        libgbm \
        libX11 \
        libXcomposite \
        libXdamage \
        libXext \
        libXfixes \
        libXrandr \
        libxkbcommon \
        mesa-libgbm \
        nss \
        nspr \
        pango \
        xdg-utils \
    && dnf clean all

# ── Google Chrome 안정 버전 설치 ───────────────────────────────────────────
RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_x86_64.rpm \
        -O /tmp/chrome.rpm && \
    dnf install -y /tmp/chrome.rpm && \
    rm /tmp/chrome.rpm

# ── Python 앱 설치 ─────────────────────────────────────────────────────────
WORKDIR /app
COPY . .

RUN pip3 install --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt

# ── 실행 ───────────────────────────────────────────────────────────────────
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "80"]
