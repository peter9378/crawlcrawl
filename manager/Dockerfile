FROM python:3.12-bookworm AS builder

# Install openssh-client, curl, vim and set ll alias
RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-client \
    curl \
    vim \
 && echo "alias ll='ls -al'" >> /root/.bashrc \
 && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose the port
EXPOSE 8000

CMD mkdir -p /root/.ssh && \
    cp -r /tmp/ssh_keys/* /root/.ssh/ && \
    chown -R root:root /root/.ssh && \
    chmod 700 /root/.ssh && \
    chmod 600 /root/.ssh/id_* && \
    echo "SSH keys setup complete." && \
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
