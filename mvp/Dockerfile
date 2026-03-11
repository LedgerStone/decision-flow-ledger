FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY blockchain.py .
COPY init.sql .
COPY dashboard.html .

# Blockchain data directory
RUN mkdir -p /data/blockchain

ENV PORT=8000

EXPOSE ${PORT}

CMD uvicorn main:app --host 0.0.0.0 --port ${PORT}
