# Disaster Map System Architecture

## Overview

The Disaster Map system provides real-time 3D visualization and navigation for disaster response operations using SLAM-based mapping technology.

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Drone    │────▶│ Video Stream │────▶│   RTSP/RTMP │
│  Camera     │     │   Ingestion  │     │   Server   │
└─────────────┘     └──────────────┘     └─────────────┘
                                              │
                                              ▼
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   SLAM      │◀────│  Frame       │◀────│   Video     │
│  Engine     │     │  Processor  │     │   Decoder   │
│ (ORB-SLAM2) │     │  Pipeline   │     └─────────────┘
└─────────────┘     └──────────────┘              │
    │                                              ▼
    │                    ┌──────────────┐         ┌─────────────┐
    ▼                    │   Pose       │         │  Point      │
│  Map State            │  Estimation  │         │  Cloud      │
│ (Keyframes,           │  Service     │         │  Generator  │
│  Trajectory)          └──────────────┘         └─────────────┘
    │                                              │
    ▼                                              ▼
┌─────────────┐                              ┌─────────────┐
│   Backend   │◀────────────────────────────▶│  Frontend   │
│  API Server │                              │  Web Viewer │
│ (FastAPI)   │                              │  (Three.js) │
└─────────────┘                              └─────────────┘
    │                                              │
    ▼                                              ▼
┌─────────────┐                              ┌─────────────┐
│   Database  │                              │   Browser   │
│  (PostgreSQL)│                             │   Display   │
└─────────────┘                              └─────────────┘
```

## Data Flow Architecture

### 1. Video Stream Ingestion

```
Raw Video → RTSP/RTMP Server → Frame Extractor → Timestamped Frames
```

**Components:**
- **RTSP/RTMP Server**: Handles multiple video stream connections
- **Frame Extractor**: Extracts frames at configurable FPS (30-60)
- **Timestamp Manager**: Assigns precise timestamps to each frame

### 2. SLAM Processing Pipeline

```
Frame → Feature Extraction → Tracking → Pose Estimation → Map Update
```

**Components:**
- **Feature Extractor**: ORB/SIFT feature detection and matching
- **Pose Tracker**: Maintains camera pose estimation
- **Map Manager**: Stores keyframes and trajectory data

### 3. Data Storage Layer

```
┌─────────────────────────────────────────────────────────────┐
│                    PostgreSQL Database                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐ │
│  │ Frames   │  │ Poses    │  │ Maps     │  │ Configs      │ │
│  │ Table    │  │ Table    │  │ Table    │  │ Table        │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                   File Storage (S3/Local)                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐ │
│  │ Point    │  │ Trajectory│  │ Waypoints│  │ Visualizations│ │
│  │ Clouds   │  │ JSON      │  │ JSON     │  │ (PNG/MP4)    │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 4. API Layer

**RESTful Endpoints:**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/frames` | GET | List video frames |
| `/api/v1/poses` | GET | Get pose estimates |
| `/api/v1/maps` | POST | Upload map data |
| `/api/v1/stream` | WS | WebSocket for live updates |

**WebSocket Events:**

```json
{
  "type": "pose_update",
  "timestamp": 1695328058.123,
  "data": {
    "position": [x, y, z],
    "orientation": [qx, qy, qz, qw]
  }
}
```

## Component Architecture

### Core Modules

```
disaster-map/
├── src/
│   ├── core/              # SLAM algorithms and pose estimation
│   │   ├── slam/          # ORB-SLAM2, DVM-SLAM implementations
│   │   ├── tracking/      # Feature tracking and matching
│   │   └── mapping/       # Map building and management
│   ├── data_pipeline/     # Video processing pipeline
│   │   ├── ingestion/    # Stream handling (RTSP/RTMP)
│   │   ├── extraction/   # Frame extraction
│   │   └── processing/   # Image processing utilities
│   ├── streaming/         # Real-time communication
│   │   ├── websocket/    # WebSocket server
│   │   └── rtsp_server/  # RTSP server implementation
│   ├── visualization/     # 3D rendering and display
│   │   ├── renderer/     # Three.js/Cesium renderers
│   │   └── viewer/       # Web viewer components
│   └── utils/             # Helper functions and utilities
├── tests/                 # Test suite
│   ├── unit/              # Unit tests
│   ├── integration/       # Integration tests
│   └── e2e/               # End-to-end tests
└── config/                # Configuration files
    ├── slam_config.yaml   # SLAM parameters
    ├── pipeline_config.py # Pipeline settings
    └── viewer_config.json # Viewer options
```

### Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **SLAM** | ORB-SLAM2, DVM-SLAM | Simultaneous localization and mapping |
| **Backend** | Python 3.10, FastAPI | API server and data processing |
| **Frontend** | React, Three.js | Web-based 3D visualization |
| **Database** | PostgreSQL | Structured data storage |
| **Storage** | S3/Local File System | Point clouds, trajectories |
| **Communication** | WebSocket, RTSP/RTMP | Real-time data streaming |

## Performance Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| FPS (SLAM) | ≥ 30 fps | Frame processing rate |
| Latency (End-to-End) | ≤ 50ms | Stream to display |
| Memory Usage | < 2GB | System memory footprint |
| Map Size | Scalable to 1M+ points | Point cloud capacity |

## Security Considerations

1. **Authentication**: JWT-based API authentication
2. **Authorization**: Role-based access control (RBAC)
3. **Data Encryption**: TLS for all communications
4. **Input Validation**: Strict input sanitization on all endpoints

## Scalability

- Horizontal scaling via load balancer
- Database connection pooling
- Caching layer with Redis
- CDN for static assets and point clouds
