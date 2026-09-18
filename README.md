# Disaster Map - Live 3D Mapping from RTMP/RTSP Streams

A real-time 3D mapping system that creates navigable, continuously-updated maps from drone and body camera video streams using monocular SLAM algorithms.

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Docker (for development and operations)
- OpenCL-enabled GPU (optional but recommended for real-time performance)

### Development Setup

```bash
# Clone the repository
git clone https://github.com/speqtrum-eu/disaster-map.git
cd disaster-map

# Start Docker development environment
docker compose up --build

# Run the application
python src/main.py --config config/development.yaml
```

### Quick Demo

```bash
# Generate sample test data
python scripts/generate-demo-data.py

# Run a quick benchmark
python scripts/benchmark-slam.py test_videos/sample.mp4
```

## 📁 Project Structure

See [PROJECT_STRUCTURE.md](./PROJECT_STRUCTURE.md) for the complete directory layout and implementation phases.

## 🔧 Configuration

Configuration files are located in `config/`:

| File | Purpose |
|------|---------|
| `default.yaml` | Default settings |
| `development.yaml` | Development environment |
| `production.yaml` | Production deployment |
| `slam-configs/orb-slam2.yaml` | ORB-SLAM2 parameters |
| `slam-configs/dvm-slam.yaml` | DVM-SLAM parameters |

### Example Configuration

```yaml
# config/development.yaml
slam:
  algorithm: "orb_slam2"  # orb_slam2, dvm_slam, vins_mono
  keyframe_interval: 10   # Frames between keyframes
  max_keyframes: 1000     # Maximum keyframes in memory

streaming:
  rtsp_timeout_ms: 500    # RTSP connection timeout
  frame_extraction_fps: 30  # Target FPS for extraction

visualization:
  viewer: "cesium"        # cesium, threejs, mapbox
  max_points_render: 1000000  # Maximum points to render at once
```

## 🎯 Supported SLAM Algorithms

| Algorithm | Camera Type | Real-time | Best For |
|-----------|-------------|-----------|----------|
| ORB-SLAM2 | Monocular RGB | ✅ Yes | General purpose, well-documented |
| DVM-SLAM | Monocular RGB | ✅ Yes | Multi-agent scenarios |
| VINS-Mono | Monocular + IMU | ✅ Very Fast | Drones with IMU data |

## 🌐 Visualization Options

| Viewer | Features | Best For |
|--------|----------|----------|
| CesiumJS | Geospatial, 3D Tiles, Timeline | Production, georeferenced maps |
| Three.js | Custom rendering, WebGL | Custom visualizations |
| Mapbox GL JS | Hybrid 2D/3D | Web-based applications |

## 📊 Performance Targets

| Metric | Target | Current Status |
|--------|--------|----------------|
| SLAM FPS | ≥ 30 | Phase 1: N/A, Phase 6: ✅ |
| Visualization FPS | ≥ 60 | Phase 4: In Progress |
| End-to-end Latency | < 50ms | Phase 2: Targeting |
| Memory Usage | ≤ 2GB | Phase 3: Optimizing |

## 🧪 Testing

```bash
# Run unit tests
pytest tests/unit --cov=src --cov-report=term-missing

# Run integration tests
pytest tests/integration -v

# Run end-to-end test with sample video
pytest tests/integration/test_end_to_end.py::test_full_pipeline
```

## 📚 Documentation

- [Architecture Overview](./docs/architecture/overview.md)
- [API Reference](./docs/api-reference.md)
- [Implementation Guides](./docs/guides/)
- [Research Notes](./docs/research/)

## 👥 Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for contribution guidelines.

### Agent Roles

This project uses an agentic development model with specialized roles:

1. **Vision Agent** - SLAM algorithms, computer vision
2. **Backend Agent** - Data pipelines, real-time processing
3. **Frontend Agent** - 3D visualization, UI/UX
4. **DevOps Agent** - CI/CD, deployment, infrastructure
5. **QA Agent** - Testing, performance benchmarking

See [AGENTS.md](./AGENTS.md) for detailed role descriptions and coding standards.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](./LICENSE) file for details.

## 🔗 Resources

- **Research Papers:**
  - [DVM-SLAM](https://arxiv.org/pdf/2503.04126.pdf)
  - [ORB-SLAM2](https://arxiv.org/abs/1707.08131)
  - [VINS-Mono](https://arxiv.org/abs/1809.02963)

- **Datasets:**
  - [TUM-VI Dataset](http://vision.in.tum.de/data/datasets/vision_online_slam_vio)
  - [EuRoC MAV](http://robotics.ethz.ch/~asl-datasets/)

## 🆘 Support

- **Issues:** [GitHub Issues](https://github.com/your-org/disaster-map/issues)
- **Discussions:** [GitHub Discussions](https://github.com/your-org/disaster-map/discussions)
- **Documentation:** [Read the Docs](https://disaster-map.readthedocs.io)
