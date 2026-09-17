# Live Orthomosaic Generator (LOG) - Production Dockerfile
# Build: docker build -t log-orthomosaic:latest .
# Run:  docker run --gpus all -p 8080:8080 log-orthomosaic:latest

FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # Build tools for compiling C extensions
    build-essential \
    # Image processing libraries
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    # GDAL for geospatial support (optional)
    gdal-bin \
    # Cleanup
    && rm -rf /var/lib/apt/lists/*

# Create application directories
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/
COPY pyproject.toml .

# Install package in development mode
RUN pip install -e ".[dev]" 2>/dev/null || pip install -e "."

# Create output and data directories
RUN mkdir -p /app/data /app/outputs /app/logs \
    && chown -R app:app /app

# Switch to non-root user for security
USER app

# Expose port for health checks (optional)
EXPOSE 8080

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    OUTPUT_DIR=/app/outputs \
    DATA_DIR=/app/data \
    REDIS_URL=redis://localhost:6379

# Health check (optional - requires running server)
# HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
#     CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# Run the LOG server
CMD ["python", "-u", "/app/src/main.py"]
