# ==============================================================================
# CIVIS-CORE Production Dockerfile
# Multi-stage, non-root, lightweight, layer-cached production container
# ==============================================================================

# Build Stage: Install build dependencies and compile wheels if needed
FROM python:3.12-slim-bookworm AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Install minimal build prerequisites
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt


# Final Runtime Stage: Minimal production image
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    HOST=0.0.0.0 \
    CIVIS_STORAGE_ROOT=/var/lib/civis \
    CIVIS_EVIDENCE_DIR=/var/lib/civis/evidence \
    CIVIS_LOG_DIR=/var/log/civis

# Install runtime system libraries (OpenCV / GL dependencies)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder stage
COPY --from=builder /install /usr/local

# Create non-root dedicated runtime user and directories
RUN groupadd -g 10001 civis && \
    useradd -u 10001 -g civis -s /bin/bash -m civis && \
    mkdir -p /app /var/lib/civis/evidence /var/log/civis && \
    chown -R civis:civis /app /var/lib/civis /var/log/civis

WORKDIR /app

# Copy application source code
COPY --chown=civis:civis . /app

# Switch to non-root user
USER civis:civis

# Expose standard FastAPI port
EXPOSE 8000

# Container Healthcheck (Liveness probe)
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://127.0.0.1:8000/health/liveness || exit 1

# Production entrypoint using Uvicorn
CMD ["python", "-m", "uvicorn", "civis.api.engine:create_api_engine().get_app()", "--host", "0.0.0.0", "--port", "8000", "--factory", "--no-access-log", "--proxy-headers", "--forwarded-allow-ips", "*"]
