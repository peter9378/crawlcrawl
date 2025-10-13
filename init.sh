#!/usr/bin/env bash
# Rocky Linux 10 for GCP - Selenium/Docker setup
# Run as root (or with sudo):  sudo bash setup_rocky10_selenium.sh

set -euo pipefail

# ===== Config =====
PYTHON_BIN="${PYTHON_BIN:-python3.12}"
APP_USER="${SUDO_USER:-${USER}}"
APP_HOME="$(eval echo ~${APP_USER})"
VENV_DIR="${VENV_DIR:-/opt/py312-venv}"
CHROMEDRIVER_DEST="/usr/local/bin/chromedriver"

echo "[1/9] Checking Python..."
if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "ERROR: ${PYTHON_BIN} not found. Install Python 3.12 first (e.g., dnf install python3.12)."
  exit 1
fi

echo "[2/9] Refreshing packages & installing base tools..."
dnf -y update || true
dnf -y install curl wget unzip jq tar ca-certificates git openssh-clients which
dnf -y install python3.12-pip

echo "[3/9] Installing screen..."
dnf -y install git

echo "[4/9] Installing Docker (using official repo for Rocky Linux)..."
dnf -y remove docker docker-client docker-client-latest docker-common docker-latest \
               docker-latest-logrotate docker-logrotate docker-engine || true
dnf -y install dnf-plugins-core
dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
dnf -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker
usermod -aG docker "${APP_USER}"

echo "[5/9] Installing Google Chrome (stable)..."
# Add Google Chrome repo if not present
if [ ! -f /etc/yum.repos.d/google-chrome.repo ]; then
  cat >/etc/yum.repos.d/google-chrome.repo <<'EOF'
[google-chrome]
name=google-chrome
baseurl=https://dl.google.com/linux/chrome/rpm/stable/$basearch
enabled=1
gpgcheck=1
gpgkey=https://dl.google.com/linux/linux_signing_key.pub
EOF
fi
dnf -y install google-chrome-stable

echo "[6/9] Installing ChromeDriver matching installed Chrome..."
# Determine installed Chrome version (major)
CHROME_VERSION="$(google-chrome --version | awk '{print $3}')"
CHROME_MAJOR="${CHROME_VERSION%%.*}"
echo "  - Detected Chrome version: ${CHROME_VERSION} (major ${CHROME_MAJOR})"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT

download_chromedriver_cft() {
  # Try Chrome for Testing JSON (preferred modern path)
  # 1) known-good-versions-with-downloads.json -> pick version starting with major
  local json_url="https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json"
  echo "  - Trying Chrome-for-Testing index..."
  if curl -fsSL "$json_url" -o "${TMP_DIR}/cft.json"; then
    # Find latest entry whose version starts with CHROME_MAJOR.
    local version
    version="$(jq -r --arg m "${CHROME_MAJOR}." '
      .versions
      | map(select(.version|startswith($m)))
      | sort_by(.version)
      | last
      | .version // empty' "${TMP_DIR}/cft.json")"
    if [ -n "${version}" ]; then
      echo "    * Matched CFT version: ${version}"
      # Extract linux64 chromedriver download URL for that version
      local url
      url="$(jq -r --arg v "${version}" '
        .versions[] | select(.version==$v)
        | .downloads.chromedriver[]?
        | select(.platform=="linux64")
        | .url' "${TMP_DIR}/cft.json")"
      if [ -n "${url}" ]; then
        echo "    * Downloading: ${url}"
        curl -fSL "${url}" -o "${TMP_DIR}/chromedriver.zip"
        unzip -q "${TMP_DIR}/chromedriver.zip" -d "${TMP_DIR}/cdl"
        # New CFT layout: chromedriver-linux64/chromedriver
        local src="${TMP_DIR}/cdl/chromedriver-linux64/chromedriver"
        if [ -f "${src}" ]; then
          install -m 0755 "${src}" "${CHROMEDRIVER_DEST}"
          return 0
        fi
      fi
    fi
  fi
  return 1
}

download_chromedriver_legacy() {
  # Legacy storage.googleapis.com path (fallback for some environments)
  local latest_url="https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${CHROME_MAJOR}"
  echo "  - Trying legacy Chromedriver storage (fallback)..."
  if curl -fsSL "${latest_url}" -o "${TMP_DIR}/latest.txt"; then
    local ver
    ver="$(cat "${TMP_DIR}/latest.txt")"
    if [ -n "${ver}" ]; then
      local zip_url="https://chromedriver.storage.googleapis.com/${ver}/chromedriver_linux64.zip"
      echo "    * Downloading: ${zip_url}"
      curl -fSL "${zip_url}" -o "${TMP_DIR}/chromedriver.zip"
      unzip -q "${TMP_DIR}/chromedriver.zip" -d "${TMP_DIR}/cdl"
      local src="${TMP_DIR}/cdl/chromedriver"
      if [ -f "${src}" ]; then
        install -m 0755 "${src}" "${CHROMEDRIVER_DEST}"
        return 0
      fi
    fi
  fi
  return 1
}

if download_chromedriver_cft || download_chromedriver_legacy; then
  echo "  - Installed chromedriver to ${CHROMEDRIVER_DEST}"
else
  echo "ERROR: Failed to install a matching ChromeDriver." >&2
  exit 2
fi

echo "[7/9] Creating Python 3.12 virtual environment & installing packages..."
sudo -u "${APP_USER}" bash -lc "
  python -m pip install --upgrade pip
  # Correct packages: selenium, requests, uvicorn, fastapi, beautifulsoup4, psutil
  python3.12 -m pip install 'selenium' 'requests' 'uvicorn' 'fastapi' 'beautifulsoup4' 'psutil'
"

echo "[8/9] Verifying Selenium <-> Chrome <-> Chromedriver versions..."
sudo -u "${APP_USER}" bash -lc "
  source '${VENV_DIR}/bin/activate'
  python - <<'PY'
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import shutil, subprocess

chrome_bin = shutil.which('google-chrome') or 'google-chrome'
try:
    v = subprocess.check_output([chrome_bin, '--version'], text=True).strip()
except Exception as e:
    v = f'Unknown ({e})'
print('[Check] Chrome  :', v)

cd = shutil.which('chromedriver') or 'chromedriver'
try:
    out = subprocess.check_output([cd, '--version'], text=True).strip()
except Exception as e:
    out = f'Unknown ({e})'
print('[Check] Driver  :', out)

print('[Check] Selenium:', __import__('selenium').__version__)
PY
"

echo "[9/9] Generating SSH key (id_rsa) for local access if missing..."
SSH_DIR="${APP_HOME}/.ssh"
sudo -u "${APP_USER}" mkdir -p "${SSH_DIR}"
sudo -u "${APP_USER}" chmod 700 "${SSH_DIR}"

if [ ! -f "${SSH_DIR}/id_rsa" ]; then
  sudo -u "${APP_USER}" ssh-keygen -t rsa -b 4096 -N "" -f "${SSH_DIR}/id_rsa" -C "${APP_USER}@$(hostname -f 2>/dev/null || hostname)"
  sudo -u "${APP_USER}" chmod 600 "${SSH_DIR}/id_rsa"
  sudo -u "${APP_USER}" chmod 644 "${SSH_DIR}/id_rsa.pub"
  echo "  - New SSH key created at ${SSH_DIR}/id_rsa"
else
  echo "  - Existing SSH key found at ${SSH_DIR}/id_rsa (no changes)."
fi

echo
echo "===== Setup Complete ====="
echo "User       : ${APP_USER}"
echo "Venv       : ${VENV_DIR} (activate with: source ${VENV_DIR}/bin/activate)"
echo "Chrome     : $(google-chrome --version || echo 'N/A')"
echo "Chromedriver: $(${CHROMEDRIVER_DEST} --version | head -n1 || echo 'N/A')"
echo
echo "Your public key (~/.ssh/id_rsa.pub):"
echo "------------------------------------"
sudo -u "${APP_USER}" cat "${SSH_DIR}/id_rsa.pub" || true
echo "------------------------------------"
echo
echo "NOTE:"
echo "- You may need to re-login for docker group membership to take effect (or run: newgrp docker)."
echo "- To run Selenium with headless Chrome, use the venv's Python and ChromeOptions(headless)."

