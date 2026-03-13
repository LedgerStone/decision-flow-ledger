FROM python:3.11-slim

WORKDIR /app

COPY saas/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY saas/app/ ./app/
COPY saas/init.sql .

RUN mkdir -p /data/blockchain

ENV PORT=8000

EXPOSE ${PORT}

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 1
