FROM python:3.12-slim

WORKDIR /app

# Install system dependencies including process-compose
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/* \
    && wget -O /tmp/process-compose.tar.gz https://github.com/F1bonacc1/process-compose/releases/latest/download/process-compose_linux_arm64.tar.gz \
    && tar -xzf /tmp/process-compose.tar.gz -C /usr/local/bin/ \
    && chmod +x /usr/local/bin/process-compose \
    && rm /tmp/process-compose.tar.gz

# Copy project files
COPY pyproject.toml uv.lock ./
COPY src/ ./src/

# Install uv and dependencies
RUN pip install uv
RUN uv sync --frozen

# Create log directories
RUN mkdir -p /var/log/supervisor && \
    mkdir -p /var/run

# Copy process-compose config
COPY process-compose.yaml ./process-compose.yaml

# Create non-root user with home directory
RUN groupadd -r appuser && useradd -r -g appuser -m appuser
RUN chown -R appuser:appuser /app /var/log/supervisor /var/run
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000 8080

CMD ["uv", "run", "gunicorn", "src.k8s_health_monitor.main:app", "-w", "2", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]