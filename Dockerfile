# Use Python 3.12 slim image for smaller size
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=8002

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/

# Copy .env file if it exists (optional for cloud deployments)
COPY .env* ./
RUN if [ ! -f ".env" ]; then \
    echo "No .env file found, using environment variables from cloud provider"; \
    fi

# Create storage directories
RUN mkdir -p /app/src/app/storage/uploads \
    /app/src/app/storage/processed \
    /app/src/app/storage/downloads

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app
USER app

# Expose port
EXPOSE 8002

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8002/health || exit 1

# Run the application using uvicorn directly
WORKDIR /app/src
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"] 