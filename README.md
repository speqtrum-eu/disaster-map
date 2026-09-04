# Live Orthomosaic Generator (LOG)

## Overview
A real-time/near-real-time system designed to fuse heterogeneous video streams from drones and body cameras into a navigable, time-aware 3D orthomosaic map.

## Architecture
1. **Ingestion Layer**: FFmpeg-based stream processing & keyframe extraction.
2. **Vision Engine**: Deep feature matching (SuperPoint/SuperGlue) + SfM (Ceres Solver/COLMAP).
3. **Mapping Layer**: MVS for dense reconstruction and orthorectification.
4. **Storage Layer**: Cloud Optimized GeoTIFFs (COG) & PostGIS for spatio-temporal indexing.
5. **Visualization Layer**: WebGL-based map client (MapLibre GL JS) with time-slider support.

## Tech Stack
- **Language**: Python (Core logic), C++ (Performance critical vision tasks).
- **Vision**: OpenCV, Ceres Solver, PyTorch (for deep features).
- **Data/GIS**: PostGIS, GDAL, TiTiler.
- **Streaming**: FFmpeg, WebRTC.

## Setup (Placeholder)
*To be implemented.*
