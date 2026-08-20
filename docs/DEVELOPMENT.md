# Development Guide

## Setting Up the Development Environment

### Prerequisites

- Python 3.10 or higher
- Node.js 18 or higher
- Git
- Docker (optional)
- FFmpeg

### Installation

#### 1. Clone the Repository

```bash
git clone https://github.com/speqtrum-eu/disaster-map.git
cd disaster-map
```

#### 2. Set Up Python Backend

Create and activate a virtual environment:

```bash
# Create virtual environment
python -m venv .venv

# Activate on Linux/Mac
source .venv/bin/activate

# Activate on Windows
.venv\Scripts\activate
```

Install Python dependencies:

```bash
pip install -r requirements.txt
```

#### 3. Set Up Frontend

Navigate to the frontend directory and install dependencies:

```bash
cd frontend
npm install
cd ..
```

#### 4. Configure the Application

Edit the configuration file:

```bash
# Copy example config if needed
cp config/streams.yaml.example config/streams.yaml

# Edit configuration
nano config/streams.yaml
```

---

## Running the Application

### Development Mode

#### Backend Server

```bash
# Run the backend server
python main.py

# Or with custom config
python main.py --config config/streams.yaml
```

The backend will be available at `http://localhost:8000`

#### Frontend Development Server

```bash
cd frontend
npm run dev
```

The frontend will be available at `http://localhost:3000`

#### Run Both Together

Open two terminal windows and run the backend and frontend separately.

### Production Mode

#### Using Docker Compose

```bash
# Build and start all services
docker-compose up -d --build

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

#### Manual Production Build

**Backend:**
```bash
# Install production dependencies
pip install -r requirements.txt --no-dev

# Run with production settings
python main.py
```

**Frontend:**
```bash
cd frontend
npm run build

# Serve the built files (requires a web server)
npx serve -s dist -l 3000
```

---

## Project Structure

```
disaster-map/
├── config/                  # Configuration files
│   └── streams.yaml        # Stream and processing configuration
├── src/                    # Backend source code
│   ├── api/                # REST API and WebSocket server
│   ├── core/               # Core models and utilities
│   ├── processing/         # Orthomosaic processing
│   ├── storage/            # Data storage
│   └── streaming/          # Video stream ingestion
├── frontend/               # Frontend source code
│   ├── public/             # Static files
│   └── src/                # React components
├── docs/                   # Documentation
├── tests/                  # Tests
├── docker/                 # Docker configuration
├── main.py                 # Main entry point
├── requirements.txt        # Python dependencies
├── Dockerfile              # Backend Dockerfile
└── docker-compose.yml      # Docker Compose configuration
```

---

## Configuration

### Stream Configuration

Edit `config/streams.yaml` to configure your video sources:

```yaml
streams:
  drone_1:
    enabled: true
    type: rtsp
    url: rtsp://192.168.1.100:554/live
    name: "Drone 1 - Main"
    gps: true
    gps_source: embedded
    resolution: [1920, 1080]
    fps: 30
    
    # Camera calibration (optional)
    calibration:
      fx: 1500.0
      fy: 1500.0
      cx: 960.0
      cy: 540.0
      distortion: [0.0, 0.0, 0.0, 0.0, 0.0]
    
    # Geospatial settings
    geospatial:
      altitude: 100
      heading: 0
      tilt: 90

  bodycam_1:
    enabled: true
    type: webrtc
    url: webrtc://192.168.1.102:8080
    name: "Body Cam 1"
    gps: false
    resolution: [1280, 720]
    fps: 24
```

### Processing Configuration

```yaml
processing:
  # Feature detection
  detector: SIFT
  min_features: 1000
  
  # Feature matching
  matcher: FLANN
  min_matches: 50
  ratio_test: 0.75
  
  # Stitching
  stitch_method: incremental
  confidence_threshold: 0.8
  reprojection_error: 5.0
  
  # Frame processing
  frame_skip: 1
  keyframe_interval: 1.0
  quality: high
  
  # Tiling
  tile_size: 256
  overlap: 20
  resolution: 0.1
  
  # Geospatial
  coordinate_system: EPSG:4326
  target_system: EPSG:3857
  
  # Performance
  use_gpu: false
  max_memory: 8
  num_workers: 4
```

### Network Configuration

```yaml
network:
  api_host: 0.0.0.0
  api_port: 8000
  ws_host: 0.0.0.0
  ws_port: 8001
  cors_origins: ["http://localhost:3000", "http://127.0.0.1:3000"]
```

---

## Testing

### Running Tests

```bash
# Install test dependencies
pip install -r requirements.txt

# Run all tests
pytest

# Run specific test file
pytest tests/test_streams.py

# Run with coverage
pytest --cov=src --cov-report=html
```

### Writing Tests

Create test files in the `tests/` directory. Use `pytest` for testing.

Example test:

```python
# tests/test_streams.py
import pytest
from src.streaming.ingestors import RTSPIngestor

def test_rtsp_ingestor():
    config = StreamConfig(
        id="test",
        type=StreamType.RTSP,
        url="rtsp://example.com/live",
    )
    ingestor = RTSPIngestor(config)
    # Test code here
```

---

## Code Style

### Python

- Use `black` for code formatting
- Use `ruff` for linting
- Use `mypy` for type checking

```bash
# Format code
black src/ tests/

# Lint code
ruff check src/ tests/

# Type checking
mypy src/
```

### TypeScript/JavaScript

- Use ESLint for linting
- Use Prettier for formatting

```bash
cd frontend
npm run lint
```

---

## Debugging

### Backend Debugging

```bash
# Run with debug logging
python main.py --debug

# Or set environment variable
PYTHONPATH=. python -m pdb main.py
```

### Frontend Debugging

```bash
cd frontend
npm run dev
```

Then open `http://localhost:3000` in Chrome and use the DevTools.

---

## Logging

The application uses Python's built-in `logging` module. Logs are written to:

- Console (stdout)
- `logs/disaster_map.log`

Log levels:
- DEBUG
- INFO
- WARNING
- ERROR
- CRITICAL

---

## Troubleshooting

### Common Issues

#### OpenCV not found

```bash
# Install OpenCV with contrib modules
pip install opencv-python-headless opencv-contrib-python-headless
```

#### FFmpeg not found

```bash
# Install FFmpeg
# On Ubuntu/Debian
sudo apt-get install ffmpeg

# On Mac
brew install ffmpeg

# On Windows
# Download from https://ffmpeg.org/
```

#### WebRTC not working

```bash
# Install aiortc for WebRTC support
pip install aiortc
```

#### GPU acceleration not available

```bash
# Install CUDA and cuDNN for GPU acceleration
# See https://developer.nvidia.com/cuda-downloads

# Install GPU-accelerated OpenCV
pip install opencv-python-headless --upgrade --force-reinstall --no-cache-dir
```

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## License

This project is licensed under the MIT License.
