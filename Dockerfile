FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements-hosted.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements-hosted.txt

COPY app ./app

EXPOSE 10000

CMD ["sh", "-c", "exec uvicorn app.backend.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
