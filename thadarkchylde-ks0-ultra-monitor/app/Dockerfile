FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir flask requests

COPY server /app/server
COPY web /app/web

WORKDIR /app/server

CMD ["python", "app.py"]
