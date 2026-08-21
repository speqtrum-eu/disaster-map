# Dockerfile for Disaster Map Backend
# Multi-stage build for smaller final image

# Use official GDAL image as base to ensure version compatibility
FROM osgeo/gdal:3.13.3 as builder

WORKDIR /app

# Install Python and build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-dev \
    build-essential \
    cmake \
    git \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip3 install --no-cache-dir --user -r requirements.txt

# Runtime stage
FROM osgeo/gdal:3.13.3

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY . .

# Create directories
RUN mkdir -p data/frames data/tiles data/thumbnails logs temp

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV GDAL_DATA=/usr/share/gdal

# Expose ports
EXPOSE 8000 8001

# Set default command
CMD ["python3", "main.py"]
