# GCP Rocky Linux — DrissionPage + system Google Chrome
FROM rockylinux:9

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

ENV DISPLAY=:99 \
    DGOOGLE_PROFILE_DIR=/tmp/dgoogle_profile_suggest

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "80"]
