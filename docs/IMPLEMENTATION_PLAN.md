# Implementation Plan: Live Orthomosaic Generator (LOG)

## Phase 1: Foundation & Environment Setup
- [ ] Define core dependency list (`pyproject.toml` or `requirements.txt`).
- [ ] Set up Docker environment for complex dependencies (OpenCV, FFmpeg, GDAL, PostGIS).
- [ ] Establish a testing framework (pytest) and CI/CD pipeline.

## Phase 2: Ingestion Layer (`src/ingestion`)
- [ ] Implement RTSP/WebRTC stream consumer using `FFmpeg`.
- [ ] Develop keyframe extraction logic based on motion thresholds or time intervals.
- [ ] Create a message queue (e.g., Redis) to pass frames to the Vision Engine.

## Phase 3: Vision Engine (`src/vision`)
- [ ] Implement deep feature extraction using **SuperPoint**.
- [ ] Implement robust feature matching using **SuperGlue** or **LightGlue**.
- [ ] Integrate a Structure from Motion (SfM) solver (e.g., wrapper around **COLMAP** or custom **Ceres Solver** implementation).
- [ ] Develop camera pose estimation and bundle adjustment logic.

## Phase 4: Mapping & Orthorectification (`src/mapping`)
- [ ] Implement Multi-View Stereo (MVS) for dense depth map generation.
- [ ] Create the orthorectification pipeline to project 3D data onto a 2D plane.
- [ ] Develop a tiling service to convert results into **Cloud Optimized GeoTIFFs (COG)**.

## Phase 5: Backend & API (`src/api`)
- [ ] Set up **PostGIS** for spatio-temporal metadata storage.
- [ ] Implement an API layer (FastAPI) to serve map tiles and temporal queries.
- [ ] Integrate a dynamic tiling server (e.g., **TiTiler**) for COG serving.

## Phase 6: Frontend Visualization (`src/web` - planned)
- [ ] Develop a web client using **MapLibre GL JS**.
- [ ] Implement a temporal slider to navigate through the time axis.
- [ ] Add 3D terrain support for immersive navigation.

## Phase 7: Integration & Optimization
- [ ] End-to-end testing with simulated drone/body cam streams.
- [ ] Latency optimization (parallelizing SfM and MVS).
- [ ] Memory management for high-resolution stream processing.
