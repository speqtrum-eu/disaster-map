# Live Orthomosaic Generator (LOG) - Deployment Configuration

## Quick Start

### 1. Build Docker Image

```bash
docker build -t log-orthomosaic:latest .
```

### 2. Run Container

```bash
docker run -d \
  --name log-server \
  --gpus all \
  -p 8080:8080 \
  -v $(pwd)/data:/app/data \
  -e REDIS_URL=redis://localhost:6379 \
  log-orthomosaic:latest
```

### 3. Verify Deployment

```bash
docker logs log-server --tail 50
curl http://localhost:8080/health
```

## Production Deployment

See `deploy/docker-compose.yml` for production setup with Redis, monitoring, and auto-restart.

## Systemd Service

See `deploy/log-orthomosaic.service` for systemd integration on Linux servers.

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `REDIS_URL` | Yes | - | Redis connection URL |
| `OUTPUT_DIR` | No | ./outputs | Output directory for orthomosaics |
| `MAX_WORKERS` | No | 4 | Maximum parallel workers |
| `BATCH_SIZE` | No | 32 | Batch processing size |
| `GPU_DEVICE` | No | 0 | GPU device ID (for multi-GPU) |

## Health Check Endpoints

- `GET /health` - System health status
- `GET /status` - Processing statistics
- `POST /process/batch` - Submit batch for processing
- `GET /outputs` - List generated outputs
