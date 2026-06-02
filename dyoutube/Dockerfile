# GCP Rocky Linux 환경 (RHEL-compatible) — dgoogle Dockerfile 구조 기반
FROM rockylinux:9

ENV CHROMEDRIVER_PATH=/usr/local/bin/chromedriver \
    DEBIAN_FRONTEND=noninteractive

# 1. 시스템 패키지 및 Chrome 의존 라이브러리 설치
RUN dnf install -y epel-release && \
    dnf install -y \
        python3 \
        python3-pip \
        wget \
        curl \
        unzip \
        xorg-x11-server-Xvfb \
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

# 2. Google Chrome 안정 버전 RPM 패키지 설치 및 매칭되는 ChromeDriver 설치
RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_x86_64.rpm -O /tmp/chrome.rpm && \
    dnf install -y /tmp/chrome.rpm && \
    rm -f /tmp/chrome.rpm && \
    ln -sf /opt/google/chrome/google-chrome /usr/bin/google-chrome 2>/dev/null || true && \
    CHROME_MAJOR="$(google-chrome --version | awk '{print $3}' | cut -d. -f1)" && \
    DRIVER_VERSION="$(curl -fsSL "https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_${CHROME_MAJOR}")" && \
    curl -fsSL "https://storage.googleapis.com/chrome-for-testing-public/${DRIVER_VERSION}/linux64/chromedriver-linux64.zip" -o /tmp/chromedriver.zip && \
    unzip -q /tmp/chromedriver.zip -d /tmp && \
    install -m 0755 /tmp/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver && \
    rm -rf /tmp/chromedriver.zip /tmp/chromedriver-linux64

WORKDIR /app

COPY requirements.txt ./
RUN pip3 install --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt

COPY . .

# Gunicorn 구동 (uvicorn worker class 사용으로 안정성 확보)
CMD ["gunicorn", "app:app", "-c", "gunicorn.conf.py"]
