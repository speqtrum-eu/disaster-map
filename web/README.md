# Disaster Map Viewer - CesiumJS 3D Visualization

A comprehensive 3D viewer for disaster mapping built with React, CesiumJS, and Three.js. Features point cloud visualization (PLY format), camera trajectory tracking, waypoint markers, and real-time performance monitoring.

## Features

### Core Viewer
- **Point Cloud Loading**: Load PLY point cloud data using Cesium 3D Tiles
- **Trajectory Visualization**: Display camera path as a line with waypoints
- **Waypoint Markers**: Interactive markers with labels and actions
- **LOD System**: Automatic Level of Detail for large datasets

### Timeline Navigation
- **Playback Controls**: Play/pause, seek, speed control (0.5x - 4x)
- **Frame Markers**: Individual frame navigation
- **Smooth Scrubbing**: Real-time timeline interaction
- **Auto-Rotate**: Follow camera path automatically

### Camera Controls
- **Orbit Controls**: Zoom, pan, and rotate view
- **Snap-to-Waypoint**: Quick navigation to specific points
- **Keyboard Shortcuts**: R (reset), +/- (zoom)

### UI Components
- **Stats Panel**: Real-time FPS, latency, memory usage
- **Waypoint List**: Interactive list with coordinates and actions
- **Legend Overlay**: Map layer legend
- **Performance Benchmarks**: Target vs actual metrics

## Performance Targets

| Metric | Target | Current |
|--------|--------|---------|
| FPS | ≥ 60 | Dynamic |
| Latency | < 50ms | Real-time |
| Memory | < 500MB | Optimized |
| LOD Levels | Auto | Adaptive |

## Quick Start

### Prerequisites
- Node.js v18+
- Modern web browser (Chrome, Firefox, Safari)

### Installation

```bash
cd web
npm install
```

### Running the Server

```bash
# Development server
npm start

# Access at http://localhost:3000
```

### Building for Production

```bash
npm run build
```

## Data Files

The viewer expects the following data files in `public/data/`:

| File | Description | Format |
|------|-------------|--------|
| `trajectory.json` | Camera trajectory with poses | JSON |
| `rescue_waypoints.json` | Rescue waypoints and actions | JSON |
| `disaster_zone.ply` | Point cloud data (optional) | PLY |

### Trajectory Data Format

```json
{
  "metadata": {
    "total_frames": 150,
    "frame_interval_ms": 100
  },
  "poses": [
    {
      "frame": 0,
      "timestamp": 0.0,
      "position": [longitude, latitude, altitude],
      "orientation": {"roll", "pitch", "yaw"},
      "confidence": 0.9713
    }
  ]
}
```

### Waypoints Data Format

```json
{
  "waypoints": [
    {
      "name": "Search Zone A",
      "position": [longitude, latitude, altitude],
      "action": "scan"
    }
  ]
}
```

## API Reference

### Props

| Prop | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `trajectoryData` | Object | Yes | - | Camera trajectory data |
| `waypointsData` | Object | No | - | Waypoint markers data |
| `pointCloudUrl` | String | No | `/data/disaster_zone.ply` | PLY file URL |
| `onStatsUpdate` | Function | No | - | Callback for stats updates |

### Methods

```javascript
// Get current frame index
const currentFrame = viewer.getCurrentFrame();

// Get total frames
const totalFrames = viewer.getTotalFrames();

// Navigate to specific frame
viewer.navigateToFrame(frameIndex);

// Toggle auto-rotate
viewer.setAutoRotate(enabled);
```

## Performance Optimization

### LOD (Level of Detail)
The viewer automatically adjusts point cloud resolution based on camera distance:

- **Level 0**: Full resolution (close view)
- **Levels 1-5**: Progressive downsampled levels
- **Auto-switching**: Based on viewport and performance

### InstancedMesh Rendering
For efficient rendering of large point clouds, the viewer uses:
- GPU-accelerated instancing
- Batched draw calls
- Texture atlases for markers

### Memory Management
- Lazy loading of tile sets
- Automatic cleanup on component unmount
- Bounded frame buffers

## Browser Support

| Browser | Version | Status |
|---------|---------|--------|
| Chrome | 90+ | ✅ Full support |
| Firefox | 88+ | ✅ Full support |
| Safari | 14+ | ✅ Full support |
| Edge | 90+ | ✅ Full support |

## Development

### Adding New Features

1. Create component in `src/components/`
2. Add styles to `src/styles/`
3. Update main App component
4. Test with sample data files

### Code Style

- Use functional components with hooks
- Implement proper error handling
- Add TypeScript types for new props
- Write unit tests for critical functions

## License

MIT License - See LICENSE file for details.

## Contributing

See the main project repository for contribution guidelines.
