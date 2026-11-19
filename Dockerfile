# ==============================================================
# STAGE 1: Build Frontend Assets (Tailwind CSS v4)
# ==============================================================
FROM node:20-alpine AS frontend-builder

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci || npm install

COPY static/ ./static/
COPY templates/ ./templates/

RUN npm run build:css

# ==============================================================
# STAGE 2: Python Application Runner
# ==============================================================
FROM python:3.13-slim AS runner

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=config.settings.production

# Install essential system dependencies (curl for healthcheck, libpq for postgres)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install Python dependencies first for caching layers
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev --no-install-project || uv sync --no-dev --no-install-project

# Copy project source code
COPY . /app

# Copy compiled Tailwind CSS from Stage 1
COPY --from=frontend-builder /app/static/css/output.css /app/static/css/output.css

# Make entrypoint script executable
RUN chmod +x /app/docker-entrypoint.sh

# Create non-privileged user and setup directories
RUN useradd -u 1000 -U -d /app -s /bin/bash appuser && \
    mkdir -p /app/staticfiles /app/media && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-"]
