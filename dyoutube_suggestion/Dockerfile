# GCP Rocky Linux - DrissionPage + system Google Chrome
FROM rockylinux:9

ARG TARGETARCH
ENV DEBIAN_FRONTEND=noninteractive

# Keep package installation stable on Rocky Linux builders.
RUN echo "ip_resolve=4" >> /etc/dnf/dnf.conf && \
    echo "timeout=15" >> /etc/dnf/dnf.conf && \
    echo "retries=5" >> /etc/dnf/dnf.conf && \
    sed -i 's/^mirrorlist=/#mirrorlist=/g' /etc/yum.repos.d/rocky*.repo 2>/dev/null || true && \
    sed -i 's/^#baseurl=http/baseurl=http/g' /etc/yum.repos.d/rocky*.repo 2>/dev/null || true && \
    dnf clean all && \
    dnf install -y --allowerasing \
        ca-certificates \
        python3 \
        python3-pip \
        python3-devel \
        gcc \
        glibc-langpack-ko \
        wget \
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

# System Chrome for DrissionPage.
RUN if [ "$TARGETARCH" != "amd64" ]; then \
        echo "google-chrome-stable RPM supports amd64 only; build with --platform linux/amd64"; \
        exit 1; \
    fi && \
    wget -q --inet4-only https://dl.google.com/linux/direct/google-chrome-stable_current_x86_64.rpm \
        -O /tmp/chrome.rpm && \
    dnf install -y --allowerasing /tmp/chrome.rpm && \
    rm -f /tmp/chrome.rpm && \
    (ln -sf /opt/google/chrome/google-chrome /usr/bin/google-chrome 2>/dev/null || true) && \
    test -x /usr/bin/google-chrome && \
    google-chrome --version

ENV DRISSION_CHROME_PATH=/usr/bin/google-chrome
ENV DISPLAY=:99
ENV DRISSION_CRAWL_TIMEOUT_SECONDS=70
ENV DRISSION_PAGE_TIMEOUT_SECONDS=35
ENV DRISSION_INPUT_TIMEOUT_SECONDS=15
ENV DRISSION_DROPDOWN_TIMEOUT_SECONDS=8
ENV DRISSION_LOAD_MODE=none
ENV YOUTUBE_DEBUG_DUMP=1
ENV LANG=ko_KR.UTF-8
ENV LC_ALL=ko_KR.UTF-8

WORKDIR /app
COPY requirements.txt ./
RUN pip3 install --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x /app/docker-entrypoint.sh

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["gunicorn", "app:app", "-c", "gunicorn.conf.py"]
