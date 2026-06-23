FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends cron && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Set up daily cron job for data refresh at 6am
RUN echo "0 6 * * * cd /app && python -m jobs.refresh >> /var/log/swimchi-refresh.log 2>&1" | crontab -

EXPOSE 8000

CMD cron && gunicorn -b 0.0.0.0:8000 'app:create_app()'
