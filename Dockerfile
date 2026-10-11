# Multi-Robot Adversarial Contingency Auctions (ACA) Demo
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt requirements-demo.txt ./
RUN pip install --no-cache-dir -r requirements-demo.txt

# Copy application source code and data assets
COPY . .

# Expose Gradio port
EXPOSE 7860

ENV GRADIO_SERVER_NAME="0.0.0.0"
ENV GRADIO_SERVER_PORT=7860

CMD ["python", "app.py"]
