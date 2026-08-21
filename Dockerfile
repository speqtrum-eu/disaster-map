# Dockerfile for Disaster Map Backend
# Multi-stage build for smaller final image

# Build stage - use ubuntu with GDAL 3.10 which is compatible
FROM ubuntu:22.04 as builder

WORKDIR /app

# Install Python and build dependencies
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-dev \
    python3-pip \
    python3-venv \
    build-essential \
    cmake \
    git \
    wget \
    curl \
    libgdal-dev \
    gdal-bin \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN python3.11 -m pip install --no-cache-dir --user -r requirements.txt

# Runtime stage
FROM ubuntu:22.04

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-dev \
    python3-pip \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgdal-dev \
    gdal-bin \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Set GDAL data path
ENV GDAL_DATA=/usr/share/gdal

# Copy application code
COPY . .

# Create directories
RUN mkdir -p data/frames data/tiles data/thumbnails logs temp

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Expose ports
EXPOSE 8000 8001

# Set default command
CMD ["python3.11", "main.py"]
