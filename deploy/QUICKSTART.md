# Quick Start Guide - Live Orthomosaic Generator (LOG)

## Prerequisites

- **Python 3.9+** with pip
- **Docker** (optional, for production deployment)
- **Redis** (required for message broker)
- **GPU** (recommended for real-time processing)

## Local Development Setup

### 1. Clone and Install

```bash
git clone https://github.com/disaster-map/log.git
cd log

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"
```

### 2. Start Redis

```bash
redis-server --daemonize yes
```

### 3. Run LOG Server

```bash
export REDIS_URL=redis://localhost:6379
python src/main.py
```

## Production Deployment

### Option A: Docker (Recommended)

```bash
# Build image
docker build -t log-orthomosaic:latest .

# Run with GPU support
docker run --gpus all \
  -p 8080:8080 \
  -v $(pwd)/data:/app/data \
  -e REDIS_URL=redis://localhost:6379 \
  log-orthomosaic:latest
```

### Option B: Systemd Service

```bash
# Install dependencies
sudo ./deploy/deploy.sh install

# Start service
sudo systemctl start log-orthomosaic

# Enable auto-start on boot
sudo systemctl enable log-orthomosaic

# Check status
systemctl status log-orthomosaic
```

## Verify Installation

### Health Check

```bash
curl http://localhost:8080/health
# Expected: {"status":"healthy","timestamp":"2026-09-17T..."}
```

### Run Tests

```bash
pytest tests/ -v
# Expected: 33 passed in <1s
```

## Configuration

Edit `deploy/.env.example` and copy to `.env.local`:

```bash
cp deploy/.env.example .env.local
nano .env.local
```

Key settings:
- `REDIS_URL` - Redis connection (required)
- `OUTPUT_DIR` - Output directory for orthomosaics
- `MAX_WORKERS` - Parallel processing workers
- `BATCH_SIZE` - Frames per batch

## Next Steps

1. **Test with sample data**: See `tests/` for test fixtures
2. **Configure monitoring**: Set up Prometheus/Grafana
3. **Scale horizontally**: Deploy multiple LOG servers behind load balancer
4. **Production hardening**: Review security settings in systemd service file

For detailed documentation, see:
- `deploy/docker-compose.yml` - Production orchestration
- `deploy/log-orthomosaic.service` - Systemd integration
- `docs/IMPLEMENTATION_PLAN.md` - Architecture overview
