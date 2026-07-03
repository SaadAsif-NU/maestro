# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY maestro ./maestro
RUN pip install --upgrade pip && pip install .

RUN useradd --create-home --uid 1000 maestro && chown -R maestro:maestro /app
USER maestro

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "maestro.server.app:app", "--host", "0.0.0.0", "--port", "8000"]
