# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# 1) Build the React app (Vite -> frontend/dist)
# ---------------------------------------------------------------------------
FROM node:20-alpine AS frontend

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---------------------------------------------------------------------------
# 2) Python runtime: Django serves the API and the built SPA
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBUG=False \
    PORT=8000

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt

COPY backend/ backend/
COPY start.sh docker-entrypoint.sh ./
COPY --from=frontend /app/frontend/dist frontend/dist

# collectstatic only needs a throwaway key; the real SECRET_KEY is provided at
# runtime and is never baked into the image.
RUN SECRET_KEY=build-only-not-a-real-secret-key-0000000000 DEBUG=False \
    python backend/manage.py collectstatic --noinput \
    && chmod +x start.sh docker-entrypoint.sh

RUN useradd --create-home --uid 10001 app \
    && chown -R app:app /app
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health/', timeout=5)"

# Migrations run at container start (the database is external: Neon).
CMD ["./docker-entrypoint.sh"]
