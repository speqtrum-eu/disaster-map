# Disaster Map API

FastAPI-based REST API server for disaster map visualization with real-time updates.

## Features

- **REST Endpoints**
  - `/api/trajectory` - Load trajectory JSON with camera poses
  - `/api/pointcloud` - Serve PLY point cloud data (with streaming support)
  - `/api/waypoints` - Get rescue waypoints for navigation
  - `/api/live` - WebSocket endpoint for real-time updates

- **Data Processing**
  - PLY to Cesium 3D Tiles conversion
  - Trajectory visualization data generation
  - Timeline metadata extraction from pose timestamps

- **Performance Optimizations**
  - Memory-mapped I/O for large PLY files
  - Lazy loading for point clouds
  - Streaming responses for large datasets
  - Response times <100ms target

## Quick Start

### Installation

```bash
# Install dependencies
pip install fastapi uvicorn websockets numpy pydantic httpx psutil

# Optional: For PLY processing
pip install trimesh
```

### Run the Server

```bash
uvicorn src.api.server:app --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000` with interactive docs at `/docs`.

## Endpoints

### Trajectory

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/trajectory` | GET | Load trajectory JSON with poses |
| `/api/trajectory/stats` | GET | Get summary statistics for loaded trajectory |

**Response Example:**
```json
{
  "poses": [
    {
      "timestamp": 0.0,
      "x": 0.0,
      "y": 0.0,
      "z": 50.0,
      "roll": 0.0,
      "pitch": 0.0,
      "yaw": 0.0,
      "confidence": 1.0
    }
  ],
  "start_time": 0.0,
  "end_time": 4.97,
  "total_distance": 234.56,
  "frame_rate": 30.2
}
```

### Point Cloud

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/pointcloud` | GET | Serve PLY point cloud data (streaming) |
| `/api/pointcloud/stats` | GET | Get statistics about the point cloud file |

**Query Parameters:**
- `file_path`: Path to PLY file (optional, uses demo data if not provided)
- `format`: Output format - `ply`, `xyz`, or `binary`
- `chunk_size`: Size of chunks for streaming (default: 1MB)

### Waypoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/waypoints` | GET | Get rescue waypoints for navigation |
| `/api/waypoints/{id}` | DELETE | Remove a waypoint |

**Query Parameters:**
- `category`: Filter by category (rescue, hazard, landmark)
- `priority`: Minimum priority level

### Real-time Updates

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/live` | WebSocket | Real-time updates for trajectory, waypoints, alerts |

**WebSocket Protocol:**
```json
// Subscribe to topic
{"type": "subscribe", "topic": "trajectory"}

// Receive update
{"type": "trajectory", "data": {...}, "timestamp": 1234567890}
```

## Data Processing Utilities

### PLY File Handling

The API uses memory-mapped I/O for efficient handling of large PLY files:

```python
from src.api.data_processing import load_ply_points, get_pointcloud_stats

# Load point cloud with memory mapping
positions, colors = load_ply_points('pointcloud.ply', use_mmap=True)

# Get statistics
stats = get_pointcloud_stats('pointcloud.ply')
print(f"Points: {stats.count}")
```

### PLY to 3D Tiles Conversion

Convert PLY point clouds to Cesium 3D Tiles format for efficient web rendering:

```python
from src.api.data_processing import ply_to_3dtiles

result = ply_to_3dtiles(
    input_path='pointcloud.ply',
    output_dir='tiles_output',
    tile_size=10.0,  # Tile size in meters
    compression="async"
)

print(f"Generated {result['tile_count']} tiles")
```

### Trajectory Visualization Data

Generate visualization data for the web viewer:

```python
from src.api.data_processing import generate_trajectory_visualization_data

viz_data = generate_trajectory_visualization_data(trajectory_data)

# Returns:
# - lines: Line segments for trajectory path
# - markers: Key points with metadata
# - animation: Animation keyframes for smooth playback
```

### Timeline Metadata

Extract timeline configuration from pose timestamps:

```python
from src.api.data_processing import generate_timeline_metadata

timeline = generate_timeline_metadata(trajectory_data, frame_interval_ms=100.0)

# Returns:
# - start_time, end_time, duration_ms
# - markers: Navigation markers at intervals
# - playback_rate: Suggested playback speed
```

## Performance Benchmarks

### Trajectory Loading (150 poses)
- JSON Parsing: **0.29ms average** (target: <50ms) ✓
- Pose Extraction: ~0.05ms per pose

### Point Cloud Loading
- Header Parsing: ~0.15ms for 10k+ points
- Memory-mapped loading: Efficient for files >10MB

### API Response Times
- `/api/trajectory`: <10ms (cached) / <50ms (uncached)
- `/api/waypoints`: <5ms
- WebSocket handshake: ~50ms

## File I/O Best Practices

### For Large Files (>1GB)

1. **Use Memory Mapping** - Reduces memory footprint by 70%+
2. **Stream Responses** - Use `StreamingResponse` for large datasets
3. **Lazy Loading** - Load data on-demand with `LazyPointCloud` class
4. **Pagination** - Implement client-side pagination for point clouds

### Example: Lazy Point Cloud Loading

```python
from src.api.data_processing import LazyPointCloud

# Create lazy loader
lazy_pc = LazyPointCloud('large_pointcloud.ply', chunk_size=1024*1024)

# Load on-demand when needed
positions, colors = lazy_pc.load()

# Get spatial subset
subset_pos, subset_colors = lazy_pc.get_subset(
    x_min=-100, x_max=100,
    y_min=-100, y_max=100,
    z_min=0, z_max=200
)
```

## WebSocket Real-time Updates

The WebSocket endpoint supports real-time updates for:

- **trajectory**: Live pose updates from SLAM engine
- **waypoints**: Dynamic waypoint additions/removals
- **alerts**: Emergency alerts and notifications

### Server-Side Update Generation

```python
from src.api.websocket_service import WebSocketService, RealTimeUpdate

# Create service instance
ws_service = WebSocketService()

# Generate trajectory updates
async for update in trajectory_update_generator(trajectory_data):
    await ws_service.broadcast(update)

# Generate waypoint updates
async for update in waypoint_update_generator(waypoints_data):
    await ws_service.broadcast(update)
```

## Production Deployment

### Docker

```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
CMD ["uvicorn", "src.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `API_HOST` | Server host address | 0.0.0.0 |
| `API_PORT` | Server port | 8000 |
| `WS_PORT` | WebSocket server port | 8765 |
| `CACHE_ENABLED` | Enable Redis caching | false |

### Scaling Considerations

1. **Horizontal Scaling** - Use API Gateway with load balancing
2. **Caching Layer** - Add Redis for trajectory and waypoint data
3. **Database** - PostgreSQL for persistent waypoint storage
4. **Message Queue** - RabbitMQ/Redis for real-time update distribution

## Testing

### Run Tests

```bash
# Unit tests
pytest tests/unit/test_api/ -v

# Integration tests
pytest tests/integration/test_api.py -v

# Benchmark tests
python src/api/benchmarks.py --json > benchmarks.json
```

### Test Coverage

Target coverage: **>80%** for API module

## License

MIT License - See LICENSE file for details.
