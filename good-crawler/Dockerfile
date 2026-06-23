FROM rockylinux:9

ARG TARGETARCH
ENV PYTHONUNBUFFERED=1

RUN echo "timeout=15" >> /etc/dnf/dnf.conf && \
    echo "retries=5" >> /etc/dnf/dnf.conf && \
    dnf clean all && \
    dnf install -y --allowerasing \
        ca-certificates \
        python3 \
        python3-pip \
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
        xdg-utils && \
    dnf clean all

RUN if [ "$TARGETARCH" != "amd64" ]; then \
        echo "google-chrome-stable RPM supports amd64 only; build with --platform linux/amd64"; \
        exit 1; \
    fi && \
    wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_x86_64.rpm \
        -O /tmp/chrome.rpm && \
    dnf install -y --allowerasing /tmp/chrome.rpm && \
    rm -f /tmp/chrome.rpm && \
    ln -sf /opt/google/chrome/google-chrome /usr/bin/google-chrome && \
    google-chrome --version

ENV DRISSION_CHROME_PATH=/usr/bin/google-chrome
ENV DRISSION_LOAD_MODE=eager
ENV CRAWLER_MAX_WORKERS=1
ENV CRAWLER_PAGE_TIMEOUT=35
ENV CRAWLER_INPUT_TIMEOUT=15
ENV CRAWLER_RESULTS_TIMEOUT=35
ENV CRAWLER_START_XVFB=1
ENV PORT=80
ENV WEB_CONCURRENCY=1
ENV GUNICORN_MAX_REQUESTS=25
ENV GUNICORN_MAX_REQUESTS_JITTER=5
ENV LANG=ko_KR.UTF-8
ENV LC_ALL=ko_KR.UTF-8

WORKDIR /app
COPY requirements.txt ./
RUN pip3 install --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x /app/run_local.sh

CMD ["gunicorn", "app:app", "-c", "gunicorn.conf.py"]
