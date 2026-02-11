# Образ для деплоя в корпоративном контуре или на любом хосте с Docker
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bot/ ./bot/

ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "bot.main"]
