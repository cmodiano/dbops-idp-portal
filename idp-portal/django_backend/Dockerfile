# =============================================================================
# IDP Portal - Backend Django Dockerfile
# Multi-stage build for production-optimized image
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Builder (install dependencies)
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /build

# Install system dependencies for compilation (lxml, xmlsec, cryptography)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    libxml2-dev \
    libxmlsec1-dev \
    libxmlsec1-openssl \
    && rm -rf /var/lib/apt/lists/*

# Copy lockfile first for layer caching
COPY requirements.lock .

# Install Python dependencies
RUN pip install --no-cache-dir --prefix=/install -r requirements.lock

# ---------------------------------------------------------------------------
# Stage 2: Production runtime
# ---------------------------------------------------------------------------
FROM python:3.12-slim

# Runtime dependencies for lxml/xmlsec
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2 \
    libxmlsec1 \
    libxmlsec1-openssl \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -g 1000 idp && \
    useradd -u 1000 -g idp -m -s /bin/bash idp

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

WORKDIR /opt/idp-portal/django_backend

# Copy application code
COPY --chown=idp:idp . .

# Create staticfiles directory
RUN mkdir -p /opt/idp-portal/django_backend/staticfiles && \
    chown -R idp:idp /opt/idp-portal/django_backend

# Collect static files (requires DJANGO_SETTINGS_MODULE)
ENV DJANGO_SETTINGS_MODULE=idp_backend.settings
ENV STATIC_ROOT=/opt/idp-portal/django_backend/staticfiles

# collectstatic needs a SECRET_KEY but doesn't use it for static generation
# Note: Errors are shown but won't fail build (some static files may be optional)
RUN SECRET_KEY=build-only-not-used \
    AUTH_DEV_BYPASS=true \
    DEBUG=false \
    python manage.py collectstatic --noinput || echo "Warning: collectstatic completed with warnings"

# Switch to non-root user
USER idp

# Expose ASGI server port
EXPOSE 8000

# Healthcheck (with trailing slash for Django APPEND_SLASH compatibility)
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health/ || exit 1

# Start Gunicorn with ASGI worker for HTTP + WebSocket support
# Uses native ASGI worker (Gunicorn 25+) — 4 workers, 60s timeout, access/error logging
CMD ["gunicorn", "idp_backend.asgi:application", \
    "--worker-class", "asgi", \
    "--workers", "4", \
    "--bind", "0.0.0.0:8000", \
    "--timeout", "60", \
    "--graceful-timeout", "30", \
    "--keep-alive", "5", \
    "--access-logfile", "-", \
    "--error-logfile", "-", \
    "--capture-output", \
    "--enable-stdio-inheritance"]
