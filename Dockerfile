# Multi-Robot Adversarial Contingency Auctions (ACA) Demo
FROM python:3.10-slim

WORKDIR /app

# Set container execution flags
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST="0.0.0.0" \
    PORT=7860

# Install minimal runtime system dependencies (curl for container healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install only what demo needs
COPY requirements-core.txt requirements-demo.txt ./
RUN pip install --no-cache-dir -r requirements-demo.txt

# Create non-root application user
RUN useradd -m -u 1000 appuser

# Copy application source code and data assets
COPY --chown=appuser:appuser . .

USER appuser

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:7860/api/health || exit 1

CMD ["python", "app.py"]
