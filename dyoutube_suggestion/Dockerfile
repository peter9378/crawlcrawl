# GCP Rocky Linux - Selenium + system Google Chrome
FROM rockylinux:9

ENV DEBIAN_FRONTEND=noninteractive

# GCP/container DNS and IPv6 timeout mitigation. Keep this aligned with dyoutube-us.
RUN echo "ip_resolve=4" >> /etc/dnf/dnf.conf && \
    echo "timeout=15" >> /etc/dnf/dnf.conf && \
    echo "retries=5" >> /etc/dnf/dnf.conf && \
    sed -i 's/^mirrorlist=/#mirrorlist=/g' /etc/yum.repos.d/rocky*.repo 2>/dev/null || true && \
    sed -i 's/^#baseurl=http/baseurl=http/g' /etc/yum.repos.d/rocky*.repo 2>/dev/null || true && \
    dnf clean all && \
    dnf install -y epel-release && \
    sed -i 's/^metalink=/#metalink=/g' /etc/yum.repos.d/epel*.repo 2>/dev/null || true && \
    sed -i 's|^#baseurl=https://download.example/pub|baseurl=https://dl.fedoraproject.org/pub|g' /etc/yum.repos.d/epel*.repo 2>/dev/null || true && \
    dnf clean all && \
    dnf install -y \
        python3 \
        python3-pip \
        python3-devel \
        gcc \
        curl \
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

# Chrome and matching Chromedriver. Use IPv4 during build to avoid resolver flakiness.
RUN wget -q --inet4-only https://dl.google.com/linux/direct/google-chrome-stable_current_x86_64.rpm \
        -O /tmp/chrome.rpm && \
    dnf install -y /tmp/chrome.rpm && \
    rm -f /tmp/chrome.rpm && \
    ln -sf /opt/google/chrome/google-chrome /usr/bin/google-chrome 2>/dev/null || true && \
    CHROME_MAJOR="$(google-chrome --version | awk '{print $3}' | cut -d. -f1)" && \
    DRIVER_VERSION="$(curl -4 -fsSL "https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_${CHROME_MAJOR}")" && \
    curl -4 -fsSL "https://storage.googleapis.com/chrome-for-testing-public/${DRIVER_VERSION}/linux64/chromedriver-linux64.zip" \
        -o /tmp/chromedriver.zip && \
    unzip -q /tmp/chromedriver.zip -d /tmp && \
    install -m 0755 /tmp/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver && \
    rm -rf /tmp/chromedriver.zip /tmp/chromedriver-linux64

ENV CHROMEDRIVER_PATH=/usr/local/bin/chromedriver
ENV DISPLAY=:99

WORKDIR /app
COPY requirements.txt ./
RUN pip3 install --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt

COPY . .

CMD ["gunicorn", "app:app", "-c", "gunicorn.conf.py"]
