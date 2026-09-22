# Disaster Map Web Viewer

A 3D disaster map visualization platform built with CesiumJS, React, and FastAPI.

## Project Structure

```
disaster-map-web-viewer/
├── frontend/                 # React + CesiumJS application
│   ├── src/
│   │   ├── components/      # Reusable UI components
│   │   ├── hooks/           # Custom React hooks
│   │   └── utils/           # Utility functions
│   ├── package.json
│   └── vite.config.js
├── backend/                  # FastAPI REST API
│   ├── app/
│   │   ├── routers/         # API route handlers
│   │   ├── services/        # Business logic layer
│   │   └── middleware/      # Request/response middleware
│   ├── requirements.txt
│   └── pyproject.toml
├── docker/                   # Docker configuration
│   ├── Dockerfile.frontend
│   ├── Dockerfile.backend
│   └── nginx.conf
├── .github/workflows/        # CI/CD pipelines
└── README.md
```

## Quick Start

### Prerequisites

- Node.js 20+ 
- Python 3.10+
- Docker (optional)

### Local Development

#### Frontend

```bash
cd frontend
npm install
npm run dev
# Opens at http://localhost:3000
```

#### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
# API available at http://localhost:8000
```

### Docker Development

```bash
# Build and run both services
docker-compose up --build

# Frontend: http://localhost:80
# Backend: http://localhost:8000
```

## Available Scripts

### Frontend

| Command | Description |
|---------|-------------|
| `npm install` | Install dependencies |
| `npm run dev` | Start development server |
| `npm run build` | Build for production |
| `npm run preview` | Preview production build |
| `npm run lint` | Run ESLint |
| `npm run typecheck` | TypeScript checking |

### Backend

| Command | Description |
|---------|-------------|
| `pip install -r requirements.txt` | Install dependencies |
| `uvicorn app.main:app --reload` | Start development server |
| `pytest tests/` | Run test suite |
| `black src tests` | Format code |
| `mypy src` | Type checking |

## API Endpoints

### Health Check

```http
GET /api/health/health
```

Response:
```json
{
  "status": "healthy",
  "service": "disaster-map-backend"
}
```

### Trajectory

```http
GET /api/trajectory/trajectory
POST /api/trajectory/trajectory
```

### Pose Data

```http
GET /api/pose/{frame_id}
POST /api/pose
```

## Docker Images

- **Frontend**: `disaster-map-frontend` - Multi-stage build with nginx
- **Backend**: `disaster-map-backend` - Python 3.10 with uvicorn

### Build Commands

```bash
# Frontend image
docker build -t disaster-map-frontend ./docker

# Backend image
docker build -t disaster-map-backend ./docker
```

## CI/CD Pipeline

The project uses GitHub Actions for automated testing and deployment:

- **Frontend**: Linting, type checking, build verification
- **Backend**: Linting (Black), type checking (mypy), pytest tests
- **Docker**: Image build validation
- **Deploy**: Automated deployment on main branch push

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `NODE_ENV` | Node environment | development |
| `PYTHONUNBUFFERED` | Disable Python buffering | 1 (Docker) |

### Cesium Ion Token

Replace the access token in `frontend/index.html` with your own Cesium Ion token for production use.

## License

MIT License - See LICENSE file for details.