# GCP Rocky Linux — Selenium + system Google Chrome (dgoogle reference)
FROM rockylinux:9

ENV DEBIAN_FRONTEND=noninteractive

# GCP 네트워크/DNS 해소 및 IPv6 타임아웃 방지 (Curl Error 6 총망라 대응)
RUN echo "ip_resolve=4" >> /etc/dnf/dnf.conf && \
    echo "timeout=15" >> /etc/dnf/dnf.conf && \
    echo "retries=5" >> /etc/dnf/dnf.conf && \
    sed -i 's/^mirrorlist=/#mirrorlist=/g' /etc/yum.repos.d/rocky*.repo 2>/dev/null || true && \
    sed -i 's/^#baseurl=http/baseurl=http/g' /etc/yum.repos.d/rocky*.repo 2>/dev/null || true && \
    dnf clean all && \
    dnf install -y epel-release && \
    sed -i 's/^metalink=/#metalink=/g' /etc/yum.repos.d/epel*.repo 2>/dev/null || true && \
    sed -i 's/^#baseurl=http/baseurl=http/g' /etc/yum.repos.d/epel*.repo 2>/dev/null || true && \
    dnf clean all && \
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

# Chrome 브라우저 설치 (IPv4 강제 적용)
RUN wget -q --inet4-only https://dl.google.com/linux/direct/google-chrome-stable_current_x86_64.rpm \
        -O /tmp/chrome.rpm && \
    dnf install -y /tmp/chrome.rpm && \
    rm -f /tmp/chrome.rpm && \
    ln -sf /opt/google/chrome/google-chrome /usr/bin/google-chrome 2>/dev/null || true

WORKDIR /app
COPY requirements.txt ./
RUN pip3 install --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt

COPY . .

ENV DISPLAY=:99

# Gunicorn + Uvicorn worker 설정 (gunicorn.conf.py 활용)
CMD ["gunicorn", "app:app", "-c", "gunicorn.conf.py"]
