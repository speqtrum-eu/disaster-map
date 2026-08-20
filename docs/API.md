# Disaster Map API Documentation

## Overview

The Disaster Map API provides RESTful endpoints and WebSocket connections for managing video streams, processing orthomosaics, and retrieving map data.

## Base URL

```
http://localhost:8000/api/v1
```

## Authentication

Currently, no authentication is required. All endpoints are accessible without API keys.

---

## REST API Endpoints

### Status Endpoints

#### Get Application Status
```
GET /api/v1/status
```

**Response:**
```json
{
  "status": "running",
  "timestamp": 1700000000.0
}
```

#### Get Application Statistics
```
GET /api/v1/stats
```

**Response:**
```json
{
  "running": true,
  "uptime": 3600.5,
  "frame_count": 1500,
  "keyframe_count": 300,
  "start_time": 1700000000.0,
  "streams": {
    "drone_1": {
      "config": { ... },
      "status": "connected",
      "frame_count": 1000,
      "last_frame_time": 1700003600.0,
      "fps_actual": 29.5,
      "error_message": ""
    }
  },
  "ortho_engine": {
    "stream_count": 2,
    "streams": { ... }
  },
  "tile_manager": {
    "cache_size": 100,
    "storage_tiles": 500,
    "max_cache_size": 1000
  }
}
```

---

### Stream Management

#### List All Streams
```
GET /api/v1/streams
```

**Response:**
```json
{
  "drone_1": {
    "config": {
      "id": "drone_1",
      "name": "Drone 1 - Main",
      "enabled": true,
      "type": "rtsp",
      "url": "rtsp://192.168.1.100:554/live",
      "resolution": [1920, 1080],
      "fps": 30,
      "gps": true,
      "gps_source": "embedded"
    },
    "status": "connected",
    "frame_count": 1000,
    "last_frame_time": 1700003600.0,
    "fps_actual": 29.5,
    "error_message": ""
  }
}
```

#### Get Stream Information
```
GET /api/v1/streams/{stream_id}
```

**Response:** Same as list streams but for a single stream.

#### Start a Stream
```
POST /api/v1/streams/{stream_id}/start
```

**Response:**
```json
{
  "status": "started",
  "stream_id": "drone_1"
}
```

#### Stop a Stream
```
POST /api/v1/streams/{stream_id}/stop
```

**Response:**
```json
{
  "status": "stopped",
  "stream_id": "drone_1"
}
```

#### Add a New Stream
```
POST /api/v1/streams
```

**Request Body:**
```json
{
  "id": "new_stream",
  "name": "New Stream",
  "enabled": true,
  "type": "rtsp",
  "url": "rtsp://192.168.1.101:554/live",
  "resolution": [1920, 1080],
  "fps": 30,
  "gps": true,
  "gps_source": "embedded"
}
```

**Response:**
```json
{
  "status": "added",
  "stream_id": "new_stream"
}
```

#### Delete a Stream
```
DELETE /api/v1/streams/{stream_id}
```

**Response:**
```json
{
  "status": "deleted",
  "stream_id": "drone_1"
}
```

---

### Orthomosaic Endpoints

#### Get Current Orthomosaic (Combined)
```
GET /api/v1/orthomosaic
```

**Response:**
```json
{
  "resolution": [8192, 4096],
  "preview": "base64_encoded_jpeg",
  "timestamp": 1700003600.0
}
```

#### Get Stream Orthomosaic
```
GET /api/v1/orthomosaic/{stream_id}
```

**Response:** Same as combined orthomosaic but for a specific stream.

#### Download Full Orthomosaic
```
GET /api/v1/orthomosaic/download
```

**Response:** JPEG image file

---

### Tile Endpoints

#### List All Tiles
```
GET /api/v1/tiles
```

**Response:**
```json
[
  {
    "x": 0,
    "y": 0,
    "z": 0,
    "timestamp": 1700003600.0
  },
  {
    "x": 1,
    "y": 0,
    "z": 0,
    "timestamp": 1700003600.0
  }
]
```

#### Get Specific Tile
```
GET /api/v1/tiles/{z}/{x}/{y}
```

**Response:**
```json
{
  "x": 0,
  "y": 0,
  "z": 0,
  "data": "base64_encoded_png",
  "timestamp": 1700003600.0
}
```

#### Get Tile as Image
```
GET /api/v1/tiles/{z}/{x}/{y}/image
```

**Response:** PNG image file

---

### Configuration Endpoints

#### Get Full Configuration
```
GET /api/v1/config
```

**Response:** Complete configuration object

#### Get Processing Configuration
```
GET /api/v1/config/processing
```

**Response:** Processing configuration

#### Get Streams Configuration
```
GET /api/v1/config/streams
```

**Response:** Streams configuration

#### Reload Configuration
```
POST /api/v1/config/reload
```

**Response:**
```json
{
  "status": "reloaded"
}
```

---

## WebSocket API

### Connection

```
ws://localhost:8001
```

### Message Types

#### Frame Update
```json
{
  "type": "frame_update",
  "data": {
    "id": "frame_123",
    "stream_id": "drone_1",
    "timestamp": 1700003600.0,
    "frame_number": 100,
    "resolution": [1920, 1080]
  },
  "timestamp": 1700003600.5
}
```

#### Orthomosaic Update
```json
{
  "type": "orthomosaic_update",
  "data": {
    "timestamp": 1700003600.0,
    "resolution": [8192, 4096]
  },
  "timestamp": 1700003600.5
}
```

#### Tile Update
```json
{
  "type": "tile_update",
  "data": {
    "tile_count": 100,
    "tiles": [
      {
        "x": 0,
        "y": 0,
        "z": 0,
        "timestamp": 1700003600.0
      }
    ]
  },
  "timestamp": 1700003600.5
}
```

#### Status Update
```json
{
  "type": "status_update",
  "data": { ... },
  "timestamp": 1700003600.5
}
```

#### Acknowledgment
```json
{
  "type": "ack",
  "message_type": "frame_update",
  "timestamp": 1700003600.5
}
```

#### Error
```json
{
  "type": "error",
  "message": "Error message"
}
```

---

## Error Codes

| Code | Description |
|------|-------------|
| 400 | Bad Request |
| 404 | Not Found |
| 500 | Internal Server Error |
| 503 | Service Unavailable |

---

## Rate Limiting

Currently, no rate limiting is implemented. In production, you may want to add rate limiting to prevent abuse.

---

## Response Formats

All successful responses return JSON with appropriate HTTP status codes.

---

## Versioning

The API is versioned using URL prefixes. The current version is `v1`.

```
/api/v1/...
```

---

## CORS

CORS is enabled for all endpoints. By default, all origins are allowed. This can be configured in the `config/streams.yaml` file.

```yaml
network:
  cors_origins:
    - "http://localhost:3000"
    - "http://127.0.0.1:3000"
```
