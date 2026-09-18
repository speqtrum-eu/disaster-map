# Agentic Coding Guidelines - Disaster Map Project

## 🤖 Agent Roles & Expertise Areas

This document defines the roles, responsibilities, and coding standards for each agent in the disaster-map project.

---

## 1. Vision Agent (Computer Vision Specialist)

### Primary Domain: SLAM Algorithms & Image Processing

**Core Responsibilities:**
- Integrate monocular SLAM algorithms (ORB-SLAM2, DVM-SLAM, VINS-Mono)
- Implement real-time feature extraction and tracking
- Handle camera calibration and intrinsic parameters
- Optimize for 30-60 FPS performance on embedded hardware

### Required Skills

| Skill | Level | Tools |
|-------|-------|-------|
| C++/Python | Expert | OpenCV, Eigen, NumPy |
| SLAM Algorithms | Expert | ORB-SLAM2, DVM-SLAM, VINS-Mono |
| Feature Detection | Advanced | SIFT, SURF, ORB, AKAZE |
| 3D Reconstruction | Expert | SfM pipelines, point cloud processing |
| Real-time Optimization | Advanced | CUDA (optional), OpenMP |

### Coding Standards

```cpp
// ✅ GOOD: Clear function names with intent
void extractKeyframes(const std::vector<cv::Mat>& frames) {
    // Select keyframes based on motion threshold and feature change
}

// ❌ BAD: Vague or cryptic names
void proc(frames, 3);
```

```cpp
// ✅ GOOD: Proper error handling with meaningful messages
bool trackFrame(const cv::Mat& frame, PoseTracker& tracker) {
    if (!frame.empty() && frame.channels() == 3) {
        return tracker.update(frame);
    }
    LOG_ERROR("Invalid input frame");
    return false;
}

// ❌ BAD: Silent failures
tracker.update(frame); // What if it fails?
```

### Performance Guidelines

1. **Memory Management**
   - Use `std::unique_ptr` for owned resources
   - Avoid dynamic allocation in hot paths
   - Profile memory usage with Valgrind or similar

2. **CPU Optimization**
   - Vectorize feature matching where possible
   - Use SIMD instructions (AVX, SSE) for critical loops
   - Cache-friendly data structures

3. **GPU Acceleration (Optional)**
   ```cpp
   // Example: CUDA-accelerated feature matching
   cudaFeatureMatcher matcher;
   matcher.match(features1, features2);  // GPU-based
   ```

### Testing Requirements

- [ ] Unit tests for each SLAM algorithm component (>90% coverage)
- [ ] Integration tests with sample video sequences (TUM-VI dataset)
- [ ] Performance benchmarks: FPS, latency, memory usage
- [ ] Edge case testing: low texture, rapid motion, lighting changes

### Code Review Checklist

```markdown
- [ ] Algorithm handles edge cases gracefully
- [ ] Performance meets 30+ FPS target on target hardware
- [ ] Memory usage optimized for embedded systems (<1GB)
- [ ] Error handling prevents crashes on bad input
- [ ] Logging provides sufficient debugging information
- [ ] Code is well-documented with inline comments
```

### Sample Implementation Pattern

```cpp
// Base SLAM class - abstract interface
class ISLAMEngine {
public:
    virtual ~ISLAMEngine() = default;
    
    // Initialize engine with camera parameters
    virtual bool initialize(const CameraParams& params) = 0;
    
    // Process a new frame, returns true if tracking successful
    virtual bool processFrame(const cv::Mat& frame, 
                             PoseEstimate& pose_out) = 0;
    
    // Get current map state (point cloud, keyframes)
    virtual MapState getMapState() const = 0;
    
    // Reset engine for new mapping session
    virtual void reset() = 0;
};

// ORB-SLAM2 implementation
class ORBSLAM2Engine : public ISLAMEngine {
private:
    std::unique_ptr<ORB_SLAM2> slam_;
    CameraParams params_;
    
public:
    bool initialize(const CameraParams& params) override {
        // Configure ORB-SLAM2 with camera intrinsics
        slam_ = std::make_unique<ORB_SLAM2>(params);
        return true;
    }
    
    bool processFrame(const cv::Mat& frame, PoseEstimate& pose_out) override {
        if (!slam_) return false;
        
        // Extract features and track
        auto result = slam_->track(frame);
        if (result.successful) {
            pose_out = result.pose;
            return true;
        }
        LOG_WARNING("Tracking failed, attempting relocalization");
        return slam_->relocalize(frame);
    }
};
```

### Common Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| Tracking loss in low-texture areas | Not enough features | Use IMU data or increase keyframe density |
| High drift over long trajectories | Accumulated error | Implement loop closure detection |
| Low FPS on embedded hardware | CPU bottleneck | Optimize feature extraction, use GPU if available |
| Memory leaks with large maps | Improper cleanup | Use smart pointers, implement RAII patterns |

---

## 2. Backend Agent (Systems & Data Engineer)

### Primary Domain: Real-time Data Pipelines & System Architecture

**Core Responsibilities:**
- Design and implement data pipelines for video streams
- Handle RTMP/RTSP stream ingestion with low latency
- Manage incremental map state efficiently
- Optimize for <50ms end-to-end processing latency

### Required Skills

| Skill | Level | Tools |
|-------|-------|-------|
| Python/TypeScript | Expert | FastAPI, Node.js, gRPC |
| Real-time Systems | Expert | ZeroMQ, WebSockets, MQTT |
| Data Structures | Advanced | Custom structures for maps |
| Performance Optimization | Expert | Profiling, memory management |

### Coding Standards

```python
# ✅ GOOD: Type hints and clear function signatures
from dataclasses import dataclass
from typing import Optional, List

@dataclass
class FrameData:
    timestamp: float
    image: np.ndarray
    pose: Optional[Pose3D] = None
    
def process_frame(frame_data: FrameData) -> ProcessingResult:
    """Process a single video frame and extract features."""
    if not validate_frame(frame_data):
        raise ValueError("Invalid frame data")
    
    # Process with timeout to prevent blocking
    result = _process_with_timeout(frame_data, timeout_ms=50)
    return result

# ❌ BAD: No type hints, unclear behavior
def proc(f):
    r = some_function(f.image)
    return r
```

### Performance Guidelines

1. **Latency Optimization**
   ```python
   # Use async/await for non-blocking I/O
   async def process_stream(stream_url: str):
       async with rtsp_client.connect(stream_url) as client:
           while True:
               frame = await client.receive_frame(timeout=0.1)  # 100ms timeout
               result = await process_frame_async(frame)
               yield result
   ```

2. **Memory Management**
   - Use memory-mapped files for large point clouds
   - Implement lazy loading for map data
   - Use object pools for frequently created/destroyed objects

3. **Parallel Processing**
   ```python
   # Process multiple frames in parallel with thread pool
   from concurrent.futures import ThreadPoolExecutor
   
   def process_batch(frames: List[FrameData]) -> List[ProcessingResult]:
       with ThreadPoolExecutor(max_workers=4) as executor:
           results = list(executor.map(process_frame, frames))
       return results
   ```

### API Design Standards

```python
# ✅ GOOD: Clear API with proper error handling
from pydantic import BaseModel, Field

class SLAMRequest(BaseModel):
    frame_data: FrameData
    timestamp: float = Field(..., description="Frame capture time")
    
class SLAMResponse(BaseModel):
    pose: Pose3D
    confidence: float
    success: bool
    
# FastAPI endpoint with validation
@app.post("/slam/track", response_model=SLAMResponse)
async def track_pose(request: SLAMRequest):
    if not request.timestamp > 0:
        raise HTTPException(status_code=400, detail="Invalid timestamp")
    
    try:
        result = slam_engine.process_frame(request.frame_data)
        return SLAMResponse(
            pose=result.pose,
            confidence=result.confidence,
            success=True
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### Testing Requirements

- [ ] Unit tests for all data processing functions (>80% coverage)
- [ ] Integration tests with mock video streams
- [ ] Load testing: 10+ concurrent stream connections
- [ ] Latency benchmarks: <50ms end-to-end

### Code Review Checklist

```markdown
- [ ] API has proper input validation and error handling
- [ ] Performance meets latency targets (<50ms)
- [ ] Memory usage optimized for large datasets
- [ ] Logging provides sufficient debugging information
- [ ] Error recovery mechanisms in place
- [ ] Code is well-documented with docstrings
```

### Sample Implementation Pattern

```python
# Frame processing pipeline
class FramePipeline:
    def __init__(self, slam_engine: ISLAMEngine):
        self.slam = slam_engine
        self.buffer_size = 1024  # Ring buffer for frames
    
    async def process_stream(self, stream_url: str) -> AsyncGenerator[FrameResult]:
        """Process RTSP/RTMP stream and yield results."""
        async with rtsp_client.connect(stream_url) as client:
            frame_buffer = asyncio.Queue(maxsize=self.buffer_size)
            
            # Start frame extraction in background
            extractor_task = asyncio.create_task(
                self._extract_frames(client, frame_buffer)
            )
            
            try:
                while True:
                    # Process frames with priority queue
                    frame_data = await frame_buffer.get()
                    
                    # Extract pose from SLAM engine
                    pose_result = await self.slam.process_frame_async(frame_data)
                    
                    yield FrameResult(
                        timestamp=frame_data.timestamp,
                        pose=pose_result.pose if pose_result.success else None,
                        confidence=pose_result.confidence
                    )
            finally:
                extractor_task.cancel()

    async def _extract_frames(self, client, buffer):
        """Extract frames from RTSP stream."""
        while True:
            frame = await client.receive_frame(timeout=0.1)
            if frame is None:
                break
            buffer.put_nowait(FrameData(
                timestamp=time.time(),
                image=frame.image
            ))
```

### Common Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| High latency in pipeline | Synchronous processing | Use async/await with non-blocking I/O |
| Memory pressure from large buffers | Unbounded queues | Implement bounded ring buffers |
| Connection drops on unstable networks | No reconnection logic | Add exponential backoff retry mechanism |
| Race conditions in shared state | Improper synchronization | Use thread-safe data structures or message passing |

---

## 3. Frontend Agent (Web & Visualization Specialist)

### Primary Domain: 3D Visualization & User Interface

**Core Responsibilities:**
- Build interactive 3D viewer with smooth rendering
- Implement timeline navigation system
- Create intuitive camera controls
- Optimize for large datasets (millions of points)

### Required Skills

| Skill | Level | Tools |
|-------|-------|-------|
| WebGL/Three.js | Expert | Three.js, Babylon.js |
| Geospatial Libraries | Advanced | CesiumJS, Mapbox GL JS |
| React/Vue | Advanced | Component architecture, state management |
| Performance Optimization | Expert | GPU optimization, LOD (Level of Detail) |

### Coding Standards

```javascript
// ✅ GOOD: Reusable components with clear props
function CameraControls({ 
  position, 
  onMove, 
  controlsEnabled = true 
}) {
  const [rotation, setRotation] = useState(0);
  
  return (
    <OrbitControls
      enableRotate={controlsEnabled}
      minDistance={10}
      maxDistance={1000}
      onEndDrag={onMove}
    />
  );
}

// ❌ BAD: Monolithic component with side effects
function Viewer() {
  useEffect(() => {
    // Do this in a custom hook instead
    initViewer();
  }, []);
  
  return <div>...</div>;
}
```

### Performance Guidelines

1. **Rendering Optimization**
   ```javascript
   // Use InstancedMesh for large point clouds
   const instancedPoints = new InstancedMesh(
     sphereGeometry, 
     material, 
     points.length
   );
   
   // Implement Level of Detail (LOD)
   function getLOD(level: number): PointCloud {
     switch (level) {
       case 0: return highResPoints;    // Close view
       case 1: return mediumResPoints;  // Medium distance
       case 2: return lowResPoints;     // Far away
       default: return lowResPoints;
     }
   }
   ```

2. **Memory Management**
   - Use `BufferGeometry` for large datasets
   - Implement texture atlases to reduce draw calls
   - Dispose geometries when no longer needed

3. **Frame Rate Optimization**
   ```javascript
   // RequestAnimationFrame with delta time
   function animate(timestamp) {
     const deltaTime = timestamp - lastTime;
     
     // Update scene based on deltaTime (not frame count)
     camera.position.x += Math.sin(timestamp * 0.001) * speed;
     
     renderer.render(scene, camera);
     requestAnimationFrame(animate);
   }
   ```

### Component Architecture

```javascript
// Reusable component library structure
src/components/
├── Viewer3D/
│   ├── index.jsx              # Main viewer container
│   ├── PointCloud.jsx         # 3D point cloud renderer
│   ├── CameraPath.jsx         # Trajectory visualization
│   └── MapOverlay.jsx         # Base map integration
├── Timeline/
│   ├── index.jsx              # Timeline component
│   ├── FrameMarker.jsx        # Individual frame marker
│   └── PlaybackControls.jsx   # Play/pause/seek controls
├── Navigation/
│   ├── OrbitControls.jsx      # Camera orbit controls
│   ├── ZoomSlider.jsx         # Distance zoom control
│   └── WaypointList.jsx       # Waypoint navigation list
└── VideoFeed/
    ├── LiveVideo.jsx          # RTMP/RTSP video overlay
    └── FrameSyncIndicator.jsx # Timestamp sync indicator
```

### Testing Requirements

- [ ] Unit tests for all components (>80% coverage)
- [ ] E2E tests with Cypress or Playwright
- [ ] Performance benchmarks: FPS, frame time, memory usage
- [ ] Cross-browser testing (Chrome, Firefox, Safari, Edge)

### Code Review Checklist

```markdown
- [ ] Components are reusable and well-tested
- [ ] Rendering maintains 60 FPS on modern hardware
- [ ] Timeline navigation is smooth and responsive
- [ ] Camera controls work intuitively
- [ ] Mobile/tablet support tested
- [ ] Accessibility features implemented (keyboard nav)
```

### Sample Implementation Pattern

```javascript
// CesiumJS viewer with live updates
import * as Cesium from 'cesium';
import { PointCloudTileProvider } from '../tile-provider';

class Live3DViewer {
  constructor(containerId, options = {}) {
    this.viewer = new Cesium.Viewer(containerId, {
      terrainProvider: options.terrain,
      baseLayerPicker: false,
      animation: false,
      timeline: true,
      geocoder: false,
      homeButton: false,
    });
    
    // Add 3D Tiles layer for point cloud
    this.tileProvider = new PointCloudTileProvider(options.pointCloudUrl);
    const tileSet = Cesium.CesiumIonTerrain.fromUrl(
      options.tileSetUrl || 'https://cesium.com/ion/tiles'
    );
    
    this.viewer.scene.primitives.add(tileSet);
    
    // Enable timeline for frame navigation
    this.setupTimeline(options.frameCount);
  }
  
  setupTimeline(frameCount) {
    const timeline = this.viewer.timeline;
    
    // Create time range from start to end of recording
    const startTime = new Cesium.JulianDate(0);
    const durationSeconds = frameCount * options.frameIntervalMs / 1000;
    const endTime = Cesium.addSeconds(startTime, durationSeconds);
    
    timeline.setRange(startTime, endTime);
    
    // Add frame markers for navigation
    for (let i = 0; i < frameCount; i++) {
      const time = startTime + Cesium.secondsToJulian(i * options.frameIntervalMs / 1000);
      
      timeline.addMarker({
        name: `Frame ${i}`,
        time: time,
        description: `Camera pose at frame ${i}`,
      });
    }
    
    // Enable smooth playback
    timeline.playbackRate = 1; // 1x real-time speed
  }
  
  updatePose(pose) {
    // Update camera position based on new pose
    const cartesian = Cesium.Cartesian3.fromRadians(
      pose.latitude, 
      pose.longitude, 
      pose.altitude
    );
    
    this.viewer.camera.setView({
      destination: cartesian,
      orientation: {
        heading: pose.heading,
        pitch: pose.pitch,
        roll: pose.roll,
      },
    });
  }
}

export default Live3DViewer;
```

### Common Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| Low FPS with large point clouds | Too many points rendered at once | Implement LOD (Level of Detail) system |
| Texture flickering | Missing texture atlas | Use texture atlases for efficient rendering |
| Timeline jumps during playback | Frame desynchronization | Use precise timestamp tracking |
| Memory leaks with long recordings | Unreleased geometries | Properly dispose geometries when no longer needed |

---

## 4. DevOps Agent (Infrastructure & Deployment)

### Primary Domain: CI/CD, Docker, Production Deployment

**Core Responsibilities:**
- Set up and maintain CI/CD pipelines
- Create production-ready Docker images
- Implement monitoring and alerting
- Manage cloud infrastructure

### Required Skills

| Skill | Level | Tools |
|-------|-------|-------|
| Docker/Kubernetes | Expert | Container orchestration |
| CI/CD Pipelines | Advanced | GitHub Actions, GitLab CI |
| Cloud Platforms | Advanced | AWS, GCP, Azure |
| Monitoring & Observability | Expert | Prometheus, Grafana, ELK |

### Coding Standards

```dockerfile
# ✅ GOOD: Multi-stage Dockerfile for production
FROM python:3.10-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

FROM python:3.10-slim as runtime
WORKDIR /app
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH
COPY src/ ./src/
COPY config/ ./config/
CMD ["python", "src/main.py"]

# ❌ BAD: Single-stage with all dependencies
FROM python:3.10
COPY . .
RUN pip install -r requirements.txt
CMD python main.py
```

### CI/CD Pipeline Example (GitHub Actions)

```yaml
# .github/workflows/ci.yml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov
      
      - name: Run unit tests
        run: pytest tests/unit --cov=src --cov-report=xml
      
      - name: Run integration tests
        run: pytest tests/integration --timeout=300
      
      - name: Upload coverage reports
        uses: codecov/codecov-action@v3

  build:
    needs: test
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Build Docker image
        run: docker build -t disaster-map:${{ github.sha }} ./docker
      
      - name: Push to registry
        if: github.event_name == 'push' && github.ref == 'refs/heads/main'
        run: |
          docker tag disaster-map:${{ github.sha }} ghcr.io/${{ github.repository }}:${{ github.sha }}
          docker push ghcr.io/${{ github.repository }}:${{ github.sha }}

  deploy:
    needs: build
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    
    steps:
      - name: Deploy to production
        run: |
          # Deployment logic here
          echo "Deploying disaster-map v${{ github.sha }}"
```

### Monitoring Stack Example

```yaml
# docker-compose.monitoring.yml
version: '3.8'
services:
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      
  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    volumes:
      - grafana-data:/var/lib/grafana
      - ./dashboards:/etc/grafana/provisioning/dashboards
      
  alertmanager:
    image: prom/alertmanager:latest
    ports:
      - "9093:9093"

volumes:
  grafana-data:
```

### Code Review Checklist

```markdown
- [ ] Docker images are multi-stage and optimized (<500MB)
- [ ] CI/CD pipeline runs all tests on every commit
- [ ] Monitoring dashboards provide key metrics
- [ ] Security scanning integrated into pipeline
- [ ] Backup and recovery procedures documented
- [ ] Environment variables properly managed (no secrets in code)
```

### Common Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| Slow CI/CD builds | Large dependency downloads | Use caching, multi-stage builds |
| Docker image bloat | Including unnecessary files | Multi-stage builds, .dockerignore |
| Production crashes | Missing environment variables | Use config maps/secrets management |
| Monitoring gaps | Incomplete metrics collection | Define key metrics upfront, collect comprehensively |

---

## 5. QA Agent (Quality Assurance & Testing)

### Primary Domain: Test Automation & Performance Testing

**Core Responsibilities:**
- Design and implement comprehensive test suite
- Perform performance benchmarking
- Conduct end-to-end testing
- Create automated regression tests

### Required Skills

| Skill | Level | Tools |
|-------|-------|-------|
| Python/JavaScript | Advanced | Pytest, Jest, Mocha |
| Performance Testing | Expert | Locust, k6, JMeter |
| Automated Testing | Expert | Selenium, Playwright |
| Test Data Generation | Advanced | Custom fixtures, mocks |

### Testing Pyramid

```
                    ┌─────────────┐
                    │   E2E Tests │  (10% - Critical paths)
                    └──────┬──────┘
                           ▼
              ┌─────────────────────────┐
              │    Integration Tests    │  (20% - Component interaction)
              └─────────────┬───────────┘
                           ▼
      ┌─────────────────────────────────────────┐
      │           Unit Tests                    │  (70% - Individual functions)
      └─────────────────────────────────────────┘
```

### Test Data Generation

```python
# Generate realistic test video sequences
from pathlib import Path
import numpy as np

def generate_test_trajectory(num_frames=1000, max_distance=100):
    """Generate a realistic drone trajectory for testing."""
    trajectory = []
    
    # Start at origin
    x, y, z = 0.0, 0.0, 50.0
    
    for i in range(num_frames):
        # Add some noise to simulate real flight
        dx = np.random.normal(0, 2)
        dy = np.random.normal(0, 2)
        dz = np.random.uniform(-1, 1)  # Altitude changes
        
        x += dx
        y += dy
        z += dz
        
        # Keep within bounds
        if abs(x) > max_distance or abs(y) > max_distance:
            break
            
        trajectory.append({
            'frame': i,
            'position': (x, y, z),
            'timestamp': i * 0.1,  # 10 FPS
        })
    
    return trajectory

# Generate synthetic point cloud for testing
def generate_test_point_cloud(trajectory):
    """Generate a simple terrain model based on trajectory."""
    points = []
    colors = []
    
    for frame in trajectory:
        x, y, z = frame['position']
        
        # Create ground plane with some elevation variation
        ground_height = 0 + np.sin(x * 0.1) * np.cos(y * 0.1) * 5
        
        points.append([x, y, ground_height])
        colors.append([0.2, 0.8, 0.3])  # Green terrain color
    
    return np.array(points), np.array(colors)
```

### Performance Benchmarking

```python
# SLAM performance benchmark
import time
from pathlib import Path

def benchmark_slam_performance(video_path: str):
    """Benchmark SLAM algorithm performance."""
    results = {
        'fps': 0,
        'avg_latency_ms': 0,
        'memory_peak_mb': 0,
        'tracking_success_rate': 0,
    }
    
    start_time = time.time()
    frame_count = 0
    successful_tracks = 0
    
    # Process video frames
    for frame in extract_frames(video_path):
        frame_start = time.time()
        
        pose_result = slam_engine.process_frame(frame)
        
        latency_ms = (time.time() - frame_start) * 1000
        
        if pose_result.success:
            successful_tracks += 1
        
        results['fps'] = frame_count / (time.time() - start_time)
        results['avg_latency_ms'] += latency_ms
    
    results['tracking_success_rate'] = successful_tracks / frame_count
    return results

# Run benchmark and save results
if __name__ == '__main__':
    video_path = 'test_videos/sample_drone.mp4'
    results = benchmark_slam_performance(video_path)
    
    print(f"Performance Results:")
    print(f"  FPS: {results['fps']:.2f}")
    print(f"  Avg Latency: {results['avg_latency_ms']:.2f} ms")
    print(f"  Success Rate: {results['tracking_success_rate']*100:.1f}%")
```

### Test Coverage Requirements

| Module | Target Coverage | Priority |
|--------|-----------------|----------|
| SLAM Engine | >90% | Critical |
| Data Pipeline | >85% | High |
| Visualization Layer | >80% | Medium |
| Navigation System | >75% | Low |

### Code Review Checklist

```markdown
- [ ] Test coverage meets targets for each module
- [ ] Performance benchmarks meet SLA requirements
- [ ] Regression tests run on every PR
- [ ] Bug reports include reproducible steps
- [ ] Test data is realistic and representative
- [ ] Documentation updated when behavior changes
```

---

## 🔄 Agent Collaboration Workflow

### Task Assignment Process

1. **Task Creation** → Project Manager creates task in issue tracker
2. **Priority Assessment** → Assign priority (P0-P3) based on impact
3. **Agent Selection** → Assign to appropriate agent(s) based on expertise
4. **Implementation** → Agent implements solution with code review
5. **Testing** → QA validates functionality and performance
6. **Deployment** → DevOps deploys to staging/production

### Communication Channels

```yaml
# Recommended communication tools
slack_channels:
  - #vision-slam     # Vision agent discussions
  - #backend-pipeline # Backend development
  - #frontend-viz    # Frontend and visualization
  - #devops-infra    # Infrastructure and deployment
  - #qa-testing      # Testing and quality assurance

code_review_platform: GitHub Pull Requests
documentation_tool: MkDocs with Git versioning
project_management: GitHub Projects or Jira
```

### Conflict Resolution

| Scenario | Resolution Process |
|----------|-------------------|
| Task priority conflict | Project Manager decides based on business impact |
| Technical disagreement | Lead engineer makes final decision after discussion |
| Resource contention | DevOps allocates resources based on criticality |
| Performance vs. feature trade-off | Product Owner prioritizes based on user value |

---

## 📊 Success Metrics by Agent

### Vision Agent KPIs
- [ ] FPS ≥ 30 for all SLAM algorithms
- [ ] Tracking success rate ≥ 95% in normal conditions
- [ ] Drift < 5cm per 10m trajectory (with GPS correction)

### Backend Agent KPIs
- [ ] End-to-end latency ≤ 50ms
- [ ] Memory usage ≤ 2GB for typical scenarios
- [ ] Uptime ≥ 99.9% in production

### Frontend Agent KPIs
- [ ] FPS ≥ 60 on modern hardware
- [ ] Timeline navigation smooth (no stuttering)
- [ ] Cross-browser compatibility (Chrome, Firefox, Safari, Edge)

### DevOps Agent KPIs
- [ ] CI/CD pipeline execution time < 15 minutes
- [ ] Deployment success rate ≥ 99%
- [ ] Mean Time To Recovery (MTTR) < 30 minutes

### QA Agent KPIs
- [ ] Test coverage ≥ 80% overall, >90% critical modules
- [ ] Bug detection rate before production ≥ 95%
- [ ] Performance regression incidents = 0

---

This document provides comprehensive guidelines for each agent role. Agents should refer to this when:
1. Starting new tasks or features
2. Code reviewing pull requests from other agents
3. Planning capacity and workload distribution
4. Establishing performance baselines and targets