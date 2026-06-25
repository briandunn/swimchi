FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends cron && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV SWIMCHI_DB=/app/data/swimchi.db

# Set up daily cron job for data refresh at 6am
RUN ln -sf /proc/1/fd/1 /var/log/swimchi-refresh.log
RUN echo "0 6 * * * SWIMCHI_DB=/app/data/swimchi.db cd /app && /usr/local/bin/python -m jobs.refresh >> /var/log/swimchi-refresh.log 2>&1" | crontab -

EXPOSE 8000

COPY <<'EOF' /app/entrypoint.sh
#!/bin/sh
mkdir -p /app/data
# Run initial refresh if DB doesn't exist yet
if [ ! -f "$SWIMCHI_DB" ]; then
  echo "No database found, running initial data refresh..."
  python -m jobs.refresh
fi
cron
exec gunicorn -b 0.0.0.0:8000 'app:create_app()'
EOF
RUN chmod +x /app/entrypoint.sh

CMD ["/app/entrypoint.sh"]
