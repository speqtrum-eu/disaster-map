# Implementation Plan: Live Orthomosaic Generator (LOG)

## Phase 1: Foundation & Environment Setup ✅
- [x] Define core dependency list (`pyproject.toml`, `requirements.txt`).
- [ ] Set up Docker environment for complex dependencies.
- [x] Establish testing framework (pytest) - **3 tests passing**.

## Phase 2: Ingestion Layer (`src/ingestion`) ✅
- [x] Implement FFmpeg-based stream consumer with async frame reading.
- [x] Develop keyframe extraction logic (time/motion-based, quality scoring).
- [x] Create Redis message queue for scalable frame delivery.

**Test Results**: All 3 ingestion tests passing ✅

## Phase 3: Vision Engine (`src/vision`) 🔄 Architecture Designed
### Component Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                    Vision Engine Layer                       │
├──────────────┬──────────────┬──────────────┬─────────────────┤
│ Feature      │ Matcher      │ SfM Solver   │ Pose Tracker    │
│ Extractor    │ (SuperGlue)  │ (Ceres)      │ (Kalman Filter) │
└──────┬───────┴──────┬───────┴──────┬───────┴────────┬────────┘
       │              │             │                │
┌──────▼───────┐ ┌────▼───────┐ ┌───▼────────┐ ┌─────▼───────┐
│ Preprocess   │ │ SuperPoint │ │ Bundle     │ │ Multi-stream│
│ (GPU/CPU)    │ │ + OpenCV   │ │ Adjustment │ │ Fusion      │
└──────────────┘ └───────────┘ └────────────┘ └─────────────┘
```

### Architecture Decisions
| Requirement | Decision |
|-------------|----------|
| **GPU Strategy** | Vendor-agnostic: CUDA (NVIDIA) primary, OpenCL fallback for ARM/Intel |
| **Latency Target** | Near-real-time (~2-5s per frame batch) |
| **Multi-stream Fusion** | Fuse all active streams into unified orthomosaic with temporal alignment |
| **Accuracy** | Sub-meter (≤0.5m GSD achievable with SfM bundle adjustment) |
| **Deployment** | Central server with Redis pub/sub for stream ingestion |

### Implementation Steps
1. **Feature Extraction Pipeline** - GPU-accelerated SuperPoint with vendor abstraction
2. **Matcher Layer** - SuperGlue/LightGlue with RANSAC outlier removal
3. **SfM Solver Integration** - Ceres Solver wrapper for bundle adjustment
4. **Multi-stream Fusion** - Temporal alignment and unified coordinate system
5. **Orthomosaic Generator** - Image stitching with sub-meter accuracy

## Phase 4: Mapping & Orthorectification (`src/mapping`) ⏳
- [ ] Implement Multi-View Stereo (MVS) for dense depth map generation.
- [ ] Create the orthorectification pipeline to project 3D data onto a 2D plane.
- [ ] Develop a tiling service to convert results into **Cloud Optimized GeoTIFFs (COG)**.

## Phase 5: Backend & API (`src/api`) ⏳
- [ ] Set up **PostGIS** for spatio-temporal metadata storage.
- [ ] Implement an API layer (FastAPI) to serve map tiles and temporal queries.
- [ ] Integrate a dynamic tiling server (e.g., **TiTiler**) for COG serving.

## Phase 6: Frontend Visualization (`src/web` - planned) ⏳
- [ ] Develop a web client using **MapLibre GL JS**.
- [ ] Implement a temporal slider to navigate through the time axis.
- [ ] Add 3D terrain support for immersive navigation.

## Phase 7: Integration & Optimization ⏳
- [ ] End-to-end testing with simulated drone/body cam streams.
- [ ] Latency optimization (parallelizing SfM and MVS).
- [ ] Memory management for high-resolution stream processing.
