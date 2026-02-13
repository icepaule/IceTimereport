FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        cron \
        curl \
        unzip \
    && rm -rf /var/lib/apt/lists/*

# Install rclone
RUN curl -fsSL https://rclone.org/install.sh | bash

# Python dependencies
COPY requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# App
COPY app/ /app/
WORKDIR /app

# Cron setup
COPY crontab /etc/cron.d/overtime-cron
RUN chmod 0644 /etc/cron.d/overtime-cron && \
    crontab /etc/cron.d/overtime-cron

# Output dirs
RUN mkdir -p /output/real /output/office

# Entry: run cron in foreground + allow manual CLI
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
