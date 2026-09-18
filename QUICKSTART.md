# Quick Start Guide - Disaster Map Development

This guide will help you get up and running with the disaster-map project in under 30 minutes.

## 📋 Prerequisites Checklist

- [ ] Python 3.10+ installed (`python --version`)
- [ ] Docker Desktop (macOS/Windows) or Docker Engine (Linux)
- [ ] Git installed
- [ ] Code editor (VS Code recommended with extensions)

## ⚡ Fast Track (5 minutes)

```bash
# 1. Clone the repository
git clone https://github.com/speqtrum-eu/disaster-map.git
cd disaster-map

# 2. Start Docker development environment
docker compose up --build

# 3. Run the demo with sample video
python scripts/run-demo.py
```

You should see a live 3D map visualization in your browser with:
- Real-time camera pose tracking
- Point cloud rendering
- Timeline navigation controls

## 🏗️ Full Development Setup (15 minutes)

### Step 1: Install Python Dependencies

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install core dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -e ".[dev]"
```

### Step 2: Set Up Docker Development Environment

```bash
# Build all services
docker compose build

# Start development environment
docker compose up --detach

# View logs
docker compose logs -f
```

The Docker setup includes:
- **Backend service** - SLAM engine and data pipeline
- **Web server** - Visualization frontend
- **Database** - Map state storage (PostgreSQL)
- **Redis** - Real-time message broker

### Step 3: Configure Your Development Environment

Create a `.env` file in the project root:

```bash
# .env
SLAM_ALGORITHM=orb_slam2
DEBUG=true
LOG_LEVEL=debug
MAX_KEYFRAMES=1000
RTSP_TIMEOUT_MS=500
```

### Step 4: Run Tests

```bash
# Quick smoke test
pytest tests/unit/test_config.py -v

# Full test suite
pytest --cov=src --cov-report=term-missing

# Performance benchmark
python scripts/benchmark-slam.py test_videos/sample.mp4
```

## 🎮 Running the Application

### Development Mode

```bash
# Run with development configuration
python src/main.py --config config/development.yaml

# Run with specific SLAM algorithm
python src/main.py --slam dvm_slam --config config/development.yaml

# Run with verbose logging
python src/main.py --verbose --config config/development.yaml
```

### Production Mode

```bash
# Build production Docker image
docker build -t disaster-map:latest ./docker

# Run production container
docker run -p 8080:8080 disaster-map:latest \
    --config /app/config/production.yaml
```

## 📊 Testing with Sample Data

### Generate Test Trajectory

```bash
python scripts/generate-demo-data.py --frames 1000 --output test_data/
```

This creates:
- `test_data/video.mp4` - Sample video sequence
- `test_data/trajectory.json` - Ground truth trajectory
- `test_data/ground_truth.ply` - Point cloud reference

### Run End-to-End Test

```bash
pytest tests/integration/test_end_to_end.py::test_full_pipeline \
    --video-path=test_videos/sample.mp4 \
    --output-dir=results/
```

## 🐛 Debugging Tips

### Common Issues

**Issue: RTSP stream timeout**
```yaml
# config/development.yaml
streaming:
  rtsp_timeout_ms: 1000  # Increase timeout for slow networks
```

**Issue: Low FPS on visualization**
```python
# Enable LOD (Level of Detail) rendering
viewer.set_max_points(500000)  # Reduce max points
viewer.enable_lod(True)       # Enable LOD
```

**Issue: Memory usage spike**
```bash
# Monitor memory usage
docker stats disaster-map-backend

# Check for memory leaks
valgrind --leak-check=full python src/main.py
```

### Debug Logging

Enable debug logging in your code:

```python
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)
logger.debug("Processing frame %d", frame_number)
```

## 📚 Next Steps

1. **Read the Architecture Guide**  
   `docs/architecture/overview.md`

2. **Explore Agent Roles**  
   `AGENTS.md` - Understand each agent's responsibilities

3. **Review Implementation Phases**  
   `PROJECT_STRUCTURE.md` - See the complete roadmap

4. **Join the Community**  
   GitHub Issues, Discussions, and Slack channel

## 🆘 Getting Help

- **Documentation:** [Read the Docs](https://disaster-map.readthedocs.io)
- **GitHub Issues:** Report bugs or request features
- **Slack:** Join #disaster-map-dev for real-time help
- **Email:** dev@disaster-map.org

## 📈 Performance Benchmarks

| Metric | Target | Your System |
|--------|--------|-------------|
| SLAM FPS | ≥ 30 | ? |
| Visualization FPS | ≥ 60 | ? |
| End-to-end Latency | < 50ms | ? |
| Memory Usage | ≤ 2GB | ? |

Run benchmarks: `python scripts/benchmark-slam.py your_video.mp4`

---

Happy mapping! 🗺️
