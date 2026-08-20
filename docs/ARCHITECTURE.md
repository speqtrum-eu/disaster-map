# System Architecture

## Overview

The Disaster Map system is designed to gather video streams from multiple sources (drones, body cameras), process them in real-time, and generate navigable orthomosaic maps with time-axis scrolling capabilities.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              USER INTERFACE                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │                     Web Interface (React)                            │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────┐  │ │
│  │  │  Map Viewer  │  │   Timeline   │  │    Stream Manager             │  │ │
│  │  │  (Three.js)  │  │  Controls    │  │    & Configuration           │  │ │
│  │  └─────────────┘  └─────────────┘  └─────────────────────────────┘  │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                              API LAYER                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │                     FastAPI Server (Port 8000)                        │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────┐  │ │
│  │  │  REST API    │  │ WebSocket    │  │   Static File Server         │  │ │
│  │  │  Endpoints   │  │  (Port 8001) │  │   (Tiles, Thumbnails)        │  │ │
│  │  └─────────────┘  └─────────────┘  └─────────────────────────────┘  │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
                                      │
              ┌───────────────────────┼───────────────────┐
              ▼                       ▼                   ▼
┌─────────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  STREAM INGESTION    │  │ ORTHOMOSAIC      │  │   STORAGE       │
│  SERVICE             │  │ ENGINE           │  │   SERVICE       │
│                      │  │                  │  │                 │
│  ┌───────────────┐  │  │  ┌─────────────┐ │  │  ┌─────────────┐ │
│  │ RTSP Ingestor │  │  │  │  Stitcher    │ │  │  │ Tile Manager│ │
│  └───────────────┘  │  │  │              │ │  │  └─────────────┘ │
│  ┌───────────────┐  │  │  │  Georeg.    │ │  │  ┌─────────────┐ │
│  │ RTMP Ingestor │  │  │  │  Service    │ │  │  │ Time-Series │ │
│  └───────────────┘  │  │  │              │ │  │  │ Database    │ │
│  ┌───────────────┐  │  │  └─────────────┘ │  │  └─────────────┘ │
│  │ HTTP Ingestor │  │  │                  │  │  ┌─────────────┐ │
│  └───────────────┘  │  │  ┌─────────────┐ │  │  │ Frame       │ │
│  ┌───────────────┐  │  │  │ Tile Gen.   │ │  │  │ Storage     │ │
│  │ WebRTC Ingest.│  │  │  │             │ │  │  └─────────────┘ │
│  └───────────────┘  │  │  └─────────────┘ │  │                 │
│  ┌───────────────┐  │  │                  │  │                 │
│  │ File Ingestor │  │  │  ┌─────────────┐ │  │                 │
│  └───────────────┘  │  │  │  Keyframe   │ │  │                 │
│                      │  │  │  Extractor  │ │  │                 │
│  ┌───────────────┐  │  │  │             │ │  │                 │
│  │ Frame Buffer  │  │  │  └─────────────┘ │  │                 │
│  └───────────────┘  │  │                  │  │                 │
└─────────────────────┘  └─────────────────┘  └─────────────────┘
```

## Component Details

### 1. Stream Ingestion Service

**Responsibility:** Capture video frames from various sources

**Components:**
- **MultiStreamManager**: Manages multiple video stream ingestors
- **StreamIngestor** (Abstract Base Class): Base class for all ingestors
  - **RTSPIngestor**: Handles RTSP streams
  - **RTMPIngestor**: Handles RTMP streams
  - **HTTPIngestor**: Handles HTTP/MJPEG streams
  - **FileIngestor**: Handles video files
  - **WebRTCIngestor**: Handles WebRTC streams
- **FrameExtractor**: Extracts frames from video streams
- **KeyframeExtractor**: Identifies keyframes for processing
- **GPSExtractor**: Extracts GPS metadata from frames

**Data Flow:**
```
Video Stream → Ingestor → Frame Decoding → Keyframe Selection → Frame Buffer
```

### 2. Orthomosaic Engine

**Responsibility:** Process frames and generate orthomosaic maps

**Components:**
- **OrthomosaicEngine**: Main processing engine
- **MultiStreamOrthoEngine**: Manages orthomosaics from multiple streams
- **OrthoStitcher** (Abstract Base Class): Base class for stitching
  - **HomographyStitcher**: Uses homography-based alignment
  - **IncrementalStitcher**: Incremental stitching for real-time
  - **BundleAdjustmentStitcher**: Uses bundle adjustment for accuracy
- **FeatureMatcher**: Matches features between frames
  - **SIFTMatcher**: Uses SIFT features
  - **ORBMatcher**: Uses ORB features
  - **AKAZEMatcher**: Uses AKAZE features
- **TileGenerator**: Generates tiles from orthomosaic
- **Georegistrator**: Handles geospatial registration

**Data Flow:**
```
Frames → Feature Extraction → Feature Matching → Homography Estimation → Stitching → Orthomosaic
```

### 3. Storage Service

**Responsibility:** Store and retrieve data

**Components:**
- **TileManager**: Manages orthomosaic tiles
  - **TileStorage**: Stores tiles (filesystem, SQLite, S3)
- **TimeSeriesDB**: Stores time-series orthomosaic data
- **FrameStorage**: Stores raw and processed frames

**Data Storage:**
- **Tiles**: Stored as PNG images in a directory structure
- **Time-Series**: SQLite database for orthomosaic metadata
- **Frames**: Optional storage of raw frames

### 4. API Layer

**Responsibility:** Provide REST and WebSocket interfaces

**Components:**
- **FastAPIServer**: REST API server
- **WebSocketServer**: WebSocket server for real-time updates
- **Routes**: API endpoint definitions

**Endpoints:**
- `/api/v1/streams`: Stream management
- `/api/v1/orthomosaic`: Orthomosaic retrieval
- `/api/v1/tiles`: Tile management
- `/api/v1/config`: Configuration management

### 5. User Interface

**Responsibility:** Visualize orthomosaic and provide controls

**Components:**
- **App**: Main application component
- **MapViewer**: Interactive map with Three.js
- **Timeline**: Time-axis navigation
- **StreamManager**: Stream configuration and management
- **ConfigPanel**: Processing configuration

**Technologies:**
- React 18
- TypeScript
- Three.js (for 3D map rendering)
- Material-UI (for UI components)
- Socket.IO (for real-time updates)

## Data Flow

### Real-Time Processing Flow

```
1. Video Streams → Stream Ingestion Service
   - Multiple ingestors capture frames from RTSP, RTMP, HTTP, WebRTC, or files
   - Frames are decoded and stored in a buffer

2. Frame Processing
   - Keyframes are extracted based on time interval or content changes
   - GPS metadata is extracted from frames or external sources
   - Frames are passed to the orthomosaic engine

3. Orthomosaic Generation
   - Features are detected and matched between consecutive frames
   - Homography matrices are estimated to align frames
   - Frames are stitched together to form an orthomosaic
   - The orthomosaic is updated incrementally as new frames arrive

4. Tiling and Storage
   - The orthomosaic is divided into tiles for efficient rendering
   - Tiles are stored in a hierarchical structure for multi-resolution display
   - Time-series data is stored for temporal navigation

5. User Interface
   - Tiles are sent to the frontend for rendering
   - Users can pan, zoom, and navigate through time
   - Real-time updates are pushed via WebSocket
```

### Batch Processing Flow

```
1. Image Collection
   - Collect images from drones or other sources
   - Ensure images have proper GPS metadata

2. Batch Processing
   - Process all images through the orthomosaic pipeline
   - Generate a single orthomosaic for the entire area

3. Storage
   - Store the orthomosaic and its tiles
   - Save metadata for later retrieval
```

## Class Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           DisasterMapApplication                           │
└─────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           MultiStreamManager                               │
│  + add_stream(config: StreamConfig): bool                                 │
│  + remove_stream(stream_id: str): bool                                    │
│  + start_stream(stream_id: str): bool                                     │
│  + stop_stream(stream_id: str): None                                     │
│  + start_all(): None                                                       │
│  + stop_all(): None                                                        │
└─────────────────────────────────────────────────────────────────────────┘
                                      │
              ┌───────────────────────┼───────────────────┐
              ▼                       ▼                   ▼
┌─────────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│      StreamIngestor   │  │   OrthoStitcher   │  │   TileManager   │
│  + connect(): bool    │  │ + add_frame()    │  │ + save_tile()   │
│  + disconnect(): None │  │ + get_ortho()   │  │ + get_tile()    │
│  + start(): bool      │  │ + reset()       │  │ + get_tiles()  │
│  + stop(): None       │  └─────────────────┘  └─────────────────┘
└─────────────────────┘          │
                              ▼
              ┌───────────────────────┼───────────────────┐
              ▼                       ▼                   ▼
┌─────────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│    FeatureMatcher    │  │  TileGenerator   │  │ TimeSeriesDB    │
│ + match_frames()    │  │ + generate()    │  │ + save_ortho()  │
│ + detect_features() │  └─────────────────┘  │ + get_ortho()   │
└─────────────────────┘                      └─────────────────┘
```

## Sequence Diagrams

### Real-Time Frame Processing

```
Stream       Ingestor       Engine         Stitcher      Storage
  │             │             │             │             │
  │────────────>│             │             │             │
  │             │             │             │             │
  │             │────────────>│             │             │
  │             │             │             │             │
  │             │             │────────────>│             │
  │             │             │             │             │
  │             │             │<────────────│             │
  │             │             │             │             │
  │             │             │────────────────────────>│
```

### WebSocket Updates

```
Client         API           Engine
  │             │             │
  │────────────>│             │
  │             │             │
  │<────────────│─────────────│
  │             │             │
  │<────────────│             │
```

## Performance Considerations

### Memory Management

- **Frame Buffer**: Limited size to prevent memory overflow
- **Tile Cache**: LRU cache for frequently accessed tiles
- **Orthomosaic Size**: Configurable maximum size
- **GPU Acceleration**: Optional GPU acceleration for feature detection

### Processing Optimization

- **Keyframe Extraction**: Reduces the number of frames to process
- **Incremental Stitching**: Updates orthomosaic without reprocessing all frames
- **Multi-Resolution Tiles**: Allows efficient rendering at different zoom levels
- **Parallel Processing**: Multiple workers for concurrent processing

### Network Considerations

- **Compression**: JPEG/PNG compression for images
- **Tiling**: Small tiles for efficient transfer
- **WebSocket**: Efficient real-time updates
- **Caching**: Browser caching for static assets

## Scalability

### Horizontal Scaling

The system can be scaled horizontally by:

1. **Multiple Ingestors**: Run multiple instances of the ingestion service
2. **Distributed Processing**: Use a message queue (RabbitMQ, Kafka) for frame distribution
3. **Load Balancing**: Distribute API requests across multiple instances
4. **Shared Storage**: Use distributed storage (S3, MinIO) for tiles and data

### Vertical Scaling

The system can be scaled vertically by:

1. **More CPU**: For faster feature detection and matching
2. **More Memory**: For larger orthomosaics and caches
3. **GPU Acceleration**: For hardware-accelerated processing

## Security Considerations

### Authentication

- Add JWT-based authentication for API endpoints
- Implement role-based access control (RBAC)

### Authorization

- Restrict access to sensitive endpoints
- Validate user permissions for actions

### Data Protection

- Encrypt sensitive data at rest
- Use HTTPS for all communications
- Sanitize user inputs

### Network Security

- Use firewalls to restrict access
- Implement rate limiting
- Validate and sanitize all inputs

## Monitoring

### Metrics

- **Frame Rate**: Frames per second for each stream
- **Processing Time**: Time to process each frame
- **Memory Usage**: Memory consumption
- **CPU Usage**: CPU utilization
- **Tile Count**: Number of tiles generated
- **Orthomosaic Size**: Size of the orthomosaic

### Logging

- **Debug**: Detailed debugging information
- **Info**: General operational information
- **Warning**: Potential issues
- **Error**: Errors that occurred
- **Critical**: Critical failures

### Alerts

- Stream disconnections
- Processing failures
- High memory usage
- High CPU usage
- Storage capacity warnings
