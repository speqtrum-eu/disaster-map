# Agent Instructions: Live Orthomosaic Generator

## Project Context
This project aims to build a high-performance pipeline for real-time 3D reconstruction and orthomosaic generation from multiple camera sources.

## Development Guidelines
- **Performance First**: Since this is "live" usage, prioritize efficient algorithms and asynchronous processing.
- **Modularity**: Keep the ingestion, vision, mapping, and serving layers decoupled via well-defined interfaces (e.g., message queues).
- **Data Integrity**: Ensure temporal consistency in the map generation process.

## Workflow
1. **Research/Design**: Use `explore` or `general` agents to validate mathematical models or library choices.
2. **Implementation**: Follow existing code patterns. Always run tests after changes.
3. **Verification**: Check for memory leaks and processing latency, as real-time performance is critical.

## Key Directories (Planned)
- `/src/ingestion`: Stream handling and keyframe extraction.
- `/src/vision`: SfM and feature matching logic.
- `/src/mapping`: Orthorectification and tiling.
- `/src/api`: Backend services for the frontend.
- `/tests`: Unit and integration tests.
