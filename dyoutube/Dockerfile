# GCP Rocky Linux — Selenium + system Google Chrome (dgoogle reference)
FROM rockylinux:9

ENV DEBIAN_FRONTEND=noninteractive

RUN dnf install -y epel-release && \
    dnf install -y \
        python3 \
        python3-pip \
        wget \
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

# Chrome 브라우저 설치 (Selenium Manager가 드라이버 자동 관리)
RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_x86_64.rpm \
        -O /tmp/chrome.rpm && \
    dnf install -y /tmp/chrome.rpm && \
    rm /tmp/chrome.rpm && \
    ln -sf /opt/google/chrome/google-chrome /usr/bin/google-chrome 2>/dev/null || true

WORKDIR /app
COPY requirements.txt ./
RUN pip3 install --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt

COPY . .

ENV DISPLAY=:99

# Gunicorn + Uvicorn worker 설정 (gunicorn.conf.py 활용)
CMD ["gunicorn", "app:app", "-c", "gunicorn.conf.py"]
