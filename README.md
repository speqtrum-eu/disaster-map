# Disaster Map - Multi-Stream Orthomosaic System

A comprehensive application for gathering video streams from drones and body cameras, generating navigable orthomosaic maps with time-axis scrolling.

## Features

- **Multi-source video ingestion**: RTSP, RTMP, WebRTC streams from drones and body cameras
- **Real-time orthomosaic generation**: Stitches multiple video feeds into a single large map
- **Geospatial alignment**: GPS metadata integration for accurate world positioning
- **Interactive viewer**: Pan, zoom, and scroll through time
- **Configurable pipelines**: YAML-based configuration for streams and processing parameters

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Web Interface (React)                       │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐  │
│  │  Map Viewer  │◄──►│  Timeline    │◄──►│  Stream Config   │  │
│  │  (Three.js)  │    │  Controls    │    │  Dashboard       │  │
│  └─────────────┘    └─────────────┘    └─────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    API Gateway (FastAPI)                        │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐  │
│  │  REST API    │    │  WebSocket   │    │  Static Files    │  │
│  │  Endpoints   │    │  Gateway     │    │  (Tiles/Thumbs)  │  │
│  └─────────────┘    └─────────────┘    └─────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────────┼───────────────────┐
              ▼                   ▼                   ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  Stream Ingest   │  │  Processing       │  │  Tile Storage    │
│  Service         │  │  Pipeline         │  │  (SQLite/S3)     │
│  - RTSP/RTMP     │  │  - Feature Match  │  │  - Ortho Tiles   │
│  - WebRTC        │  │  - Stitching      │  │  - Metadata       │
│  - Frame Extract │  │  - Georegister    │  │  - Time Index    │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- FFmpeg
- OpenCV with contrib modules

### Installation

```bash
# Clone and setup
cd disaster-map

# Backend setup
pip install -r requirements.txt

# Frontend setup
cd frontend
npm install

# Run the system
docker-compose up -d  # Or run manually
```

### Running Manually

```bash
# Terminal 1: Backend
python main.py

# Terminal 2: Frontend
cd frontend
npm run dev

# Terminal 3: Stream processor (optional, separate worker)
python -m workers.stream_processor
```

## Configuration

Edit `config/streams.yaml` to configure your video sources:

```yaml
streams:
  drone_1:
    type: rtsp
    url: rtsp://drone1:554/stream
    gps: true
    resolution: [1920, 1080]
    fps: 30
  
  bodycam_1:
    type: webrtc
    url: webrtc://bodycam1:8080
    gps: false
    resolution: [1280, 720]
    fps: 24
```

## Usage

1. Access the web interface at `http://localhost:3000`
2. Configure your video streams in the dashboard
3. View the live orthomosaic map
4. Use mouse to pan/zoom
5. Use timeline slider to scroll through time

## API Documentation

See `docs/api.md` for complete API reference.

## License

MIT
