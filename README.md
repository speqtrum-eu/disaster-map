# Live Orthomosaic Generator (LOG)

## Overview
A near-real-time system designed to fuse heterogeneous video streams from drones and body cameras into a navigable, time-aware 3D orthomosaic map with sub-meter accuracy.

## Current Status
- **Phase 2**: ✅ Complete - Ingestion layer operational (3/3 tests passing)
- **Phase 3**: 🔄 Architecture designed - Vision Engine components ready to implement
- **Phases 4-7**: ⏳ Pending implementation

## Architecture
```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Ingestion │────▶│  Vision     │────▶│    Mapping   │
│  (FFmpeg)   │     │   Engine    │     │  (MVS/COG)  │
└─────────────┘     └──────────────┘     └─────────────┘
                        │
                        ▼
                 ┌─────────────┐
                 │ SfM Solver  │
                 │   (Ceres)   │
                 └─────────────┘
```

### Component Layers
1. **Ingestion Layer**: FFmpeg stream consumer, keyframe extraction, Redis pub/sub
2. **Vision Engine**: SuperPoint feature extraction, SuperGlue matching, Ceres bundle adjustment
3. **Mapping Layer**: Multi-view stereo, orthorectification, COG tiling
4. **Storage Layer**: PostGIS for spatio-temporal indexing
5. **Visualization**: MapLibre GL JS with temporal navigation

## Tech Stack
- **Language**: Python 3.10+ (Core logic)
- **Vision**: OpenCV, PyTorch, SuperPoint/SuperGlue, Ceres Solver
- **Data/GIS**: GDAL, PostGIS, TiTiler
- **Streaming**: FFmpeg, Redis pub/sub

## Quick Start

### 1. Clone and Setup
```bash
git clone <repository>
cd disaster-map
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Run Tests
```bash
pytest tests/ -v
# Expected: 3 passed in ~0.16s
```

### 3. Verify Imports
```bash
python -c "from src.ingestion import FFmpegStreamConsumer; from src.vision.gpu import GPUContext"
```

## Requirements

### System Dependencies
- **GPU**: NVIDIA (CUDA preferred), ARM, or Intel with OpenCL support
- **Memory**: ≥8GB RAM recommended for multi-stream processing
- **Storage**: SSD for frame buffering and output tiles

### Python Packages
Core dependencies are defined in `pyproject.toml`:
```toml
numpy, opencv-python-headless, torch, torchvision, fastapi, uvicorn, 
ffmpeg-python, psycopg2-binary, redis, msgpack
```

## Development Guidelines
- **Performance First**: Prioritize efficient algorithms and async processing
- **Modularity**: Keep ingestion, vision, mapping layers decoupled via message queues
- **Testing**: Run `pytest` after every change; all tests must pass

## License
*To be defined.*
