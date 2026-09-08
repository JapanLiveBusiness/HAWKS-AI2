FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=120 --retries=10 -r requirements.txt

COPY . .
RUN chmod +x /app/scripts/run-app.sh

EXPOSE 8501

CMD ["/app/scripts/run-app.sh"]
