# IPC_QUERY Dockerfile
# Multi-stage build for production deployment

# Build stage
FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies
RUN pip install --no-cache-dir build wheel setuptools

# Copy project files
COPY pyproject.toml ./
COPY build_db.py ./
COPY ipc_query/ ./ipc_query/
COPY cli/ ./cli/

# Build wheel
RUN python -m build --wheel

# Runtime stage
FROM python:3.11-slim

WORKDIR /app

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/data /app/cache && \
    chown -R appuser:appuser /app

# Copy built wheel and install
COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl

# Copy web static files
COPY web/ ./web/

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    DATABASE_PATH=/app/data/ipc.sqlite \
    LOG_LEVEL=INFO \
    LOG_FORMAT=json

# Expose port
EXPOSE 8791

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8791/api/health', timeout=2).read()" || exit 1

# Switch to non-root user
USER appuser

# Default command
CMD ["python", "-m", "ipc_query", "serve", "--host", "0.0.0.0", "--port", "8791"]
