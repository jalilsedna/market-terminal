# Multi-Asset Research Terminal — container image for Railway (Phase A8).
#
# Single service: FastAPI serves the web UI + REST API and mounts the research
# MCP feed at /mcp, all behind one auth gate (see app/auth.py). OpenBB is heavy;
# the versions in requirements.txt are pinned precisely so pip does not backtrack
# (a mismatched fastapi/pydantic pin OOM-kills the resolver — see requirements.txt).

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# build-essential: some OpenBB transitive deps build native extensions.
# curl: used by the container/platform healthcheck.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# Install deps first so the layer caches across code-only changes.
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

# Railway injects $PORT; default to 8000 for local `docker run`. --proxy-headers
# (+ forwarded-allow-ips) lets uvicorn trust X-Forwarded-Proto behind Railway's
# TLS proxy, so request.url.scheme is "https" and the session cookie is set
# Secure. OpenBB's one-time static-package rebuild runs in the app lifespan on
# the main thread, so a single worker is required (also keeps the in-memory
# cache coherent).
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --proxy-headers --forwarded-allow-ips='*'"]
