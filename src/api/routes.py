"""
API route definitions
"""

import json
from typing import Optional, List, Dict, Any
from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse

from src.core.models import (
    StreamConfig,
    ProcessingConfig,
    Frame,
    OrthomosaicTile,
    StreamStatus,
)
from src.core.utils import get_logger, timestamp_now

logger = get_logger("api.routes")

# Create routers
api_router = APIRouter(tags=["api"])
streams_router = APIRouter(tags=["streams"])
ortho_router = APIRouter(tags=["orthomosaic"])
tiles_router = APIRouter(tags=["tiles"])
config_router = APIRouter(tags=["config"])


# Dependency to get app reference
def get_app(request: Any) -> Any:
    return request.app.state.app


# ========== API Routes ==========

@api_router.get("/status")
async def get_status():
    """Get application status"""
    return {
        "status": "running",
        "timestamp": timestamp_now(),
    }


@api_router.get("/stats")
async def get_stats(app = Depends(get_app)):
    """Get application statistics"""
    if app:
        return app.get_stats()
    return {"error": "App not available"}


# ========== Stream Routes ==========

@streams_router.get("/", response_model=List[Dict[str, Any]])
async def list_streams(app = Depends(get_app)):
    """List all streams"""
    if app and hasattr(app, '_stream_manager'):
        streams = app._stream_manager.get_streams()
        return [s.to_dict() for s in streams.values()]
    return []


@streams_router.get("/{stream_id}", response_model=Dict[str, Any])
async def get_stream(stream_id: str, app = Depends(get_app)):
    """Get stream information"""
    if app and hasattr(app, '_stream_manager'):
        stream = app._stream_manager.get_stream(stream_id)
        if stream:
            return stream.to_dict()
        raise HTTPException(status_code=404, detail="Stream not found")
    raise HTTPException(status_code=500, detail="App not available")


@streams_router.post("/{stream_id}/start")
async def start_stream(stream_id: str, app = Depends(get_app)):
    """Start a stream"""
    if app and hasattr(app, '_stream_manager'):
        success = app._stream_manager.start_stream(stream_id)
        if success:
            return {"status": "started", "stream_id": stream_id}
        raise HTTPException(status_code=400, detail="Failed to start stream")
    raise HTTPException(status_code=500, detail="App not available")


@streams_router.post("/{stream_id}/stop")
async def stop_stream(stream_id: str, app = Depends(get_app)):
    """Stop a stream"""
    if app and hasattr(app, '_stream_manager'):
        app._stream_manager.stop_stream(stream_id)
        return {"status": "stopped", "stream_id": stream_id}
    raise HTTPException(status_code=500, detail="App not available")


@streams_router.post("/")
async def add_stream(stream_config: Dict[str, Any], app = Depends(get_app)):
    """Add a new stream"""
    if app:
        stream_id = stream_config.get("id", "")
        if not stream_id:
            raise HTTPException(status_code=400, detail="Stream ID required")
        
        success = app._add_stream(stream_id, stream_config)
        if success:
            return {"status": "added", "stream_id": stream_id}
        raise HTTPException(status_code=400, detail="Failed to add stream")
    raise HTTPException(status_code=500, detail="App not available")


@streams_router.delete("/{stream_id}")
async def delete_stream(stream_id: str, app = Depends(get_app)):
    """Delete a stream"""
    if app and hasattr(app, '_stream_manager'):
        success = app._stream_manager.remove_stream(stream_id)
        if success:
            return {"status": "deleted", "stream_id": stream_id}
        raise HTTPException(status_code=404, detail="Stream not found")
    raise HTTPException(status_code=500, detail="App not available")


# ========== Orthomosaic Routes ==========

@ortho_router.get("/", response_model=Dict[str, Any])
async def get_orthomosaic(app = Depends(get_app)):
    """Get current orthomosaic (combined from all streams)"""
    if app:
        orthomosaic = app.get_orthomosaic()
        if orthomosaic is not None:
            # Convert to base64 for JSON response (for small orthomosaics)
            # In production, you'd want to return a URL or use a different endpoint
            import cv2
            import base64
            
            # Resize for preview
            preview = cv2.resize(orthomosaic, (800, 600))
            _, buffer = cv2.imencode(".jpg", preview, [cv2.IMWRITE_JPEG_QUALITY, 85])
            image_base64 = base64.b64encode(buffer).decode("utf-8")
            
            return {
                "resolution": list(orthomosaic.shape[:2]),
                "preview": image_base64,
                "timestamp": timestamp_now(),
            }
        raise HTTPException(status_code=404, detail="No orthomosaic available")
    raise HTTPException(status_code=500, detail="App not available")


@ortho_router.get("/{stream_id}", response_model=Dict[str, Any])
async def get_stream_orthomosaic(stream_id: str, app = Depends(get_app)):
    """Get orthomosaic for a specific stream"""
    if app:
        orthomosaic = app.get_orthomosaic(stream_id)
        if orthomosaic is not None:
            import cv2
            import base64
            
            # Resize for preview
            preview = cv2.resize(orthomosaic, (800, 600))
            _, buffer = cv2.imencode(".jpg", preview, [cv2.IMWRITE_JPEG_QUALITY, 85])
            image_base64 = base64.b64encode(buffer).decode("utf-8")
            
            return {
                "stream_id": stream_id,
                "resolution": list(orthomosaic.shape[:2]),
                "preview": image_base64,
                "timestamp": timestamp_now(),
            }
        raise HTTPException(status_code=404, detail="No orthomosaic available for stream")
    raise HTTPException(status_code=500, detail="App not available")


@ortho_router.get("/download")
async def download_orthomosaic(app = Depends(get_app)):
    """Download full orthomosaic"""
    if app:
        orthomosaic = app.get_orthomosaic()
        if orthomosaic is not None:
            import cv2
            import tempfile
            from fastapi.responses import FileResponse
            
            # Save to temp file
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                cv2.imwrite(tmp.name, orthomosaic, [cv2.IMWRITE_JPEG_QUALITY, 95])
                return FileResponse(
                    tmp.name,
                    filename=f"orthomosaic_{timestamp_now()}.jpg",
                    media_type="image/jpeg"
                )
        raise HTTPException(status_code=404, detail="No orthomosaic available")
    raise HTTPException(status_code=500, detail="App not available")


# ========== Tile Routes ==========

@tiles_router.get("/", response_model=List[Dict[str, Any]])
async def list_tiles(app = Depends(get_app)):
    """List all tiles"""
    if app:
        tiles = app.get_tiles()
        return [
            {
                "x": t.x,
                "y": t.y,
                "z": t.z,
                "timestamp": t.timestamp,
            }
            for t in tiles
        ]
    return []


@tiles_router.get("/{z}/{x}/{y}")
async def get_tile(z: int, x: int, y: int, app = Depends(get_app)):
    """Get a specific tile"""
    if app and hasattr(app, '_tile_manager'):
        tile = app._tile_manager.get_tile(z, x, y)
        if tile is not None:
            import cv2
            import base64
            
            _, buffer = cv2.imencode(".png", tile.data, [cv2.IMWRITE_PNG_COMPRESSION, 9])
            image_base64 = base64.b64encode(buffer).decode("utf-8")
            
            return {
                "x": tile.x,
                "y": tile.y,
                "z": tile.z,
                "data": image_base64,
                "timestamp": tile.timestamp,
            }
        raise HTTPException(status_code=404, detail="Tile not found")
    raise HTTPException(status_code=500, detail="App not available")


@tiles_router.get("/{z}/{x}/{y}/image")
async def get_tile_image(z: int, x: int, y: int, app = Depends(get_app)):
    """Get a specific tile as image"""
    if app and hasattr(app, '_tile_manager'):
        tile = app._tile_manager.get_tile(z, x, y)
        if tile is not None:
            import cv2
            import tempfile
            from fastapi.responses import FileResponse
            
            # Save to temp file
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                cv2.imwrite(tmp.name, tile.data, [cv2.IMWRITE_PNG_COMPRESSION, 9])
                return FileResponse(
                    tmp.name,
                    filename=f"tile_{z}_{x}_{y}.png",
                    media_type="image/png"
                )
        raise HTTPException(status_code=404, detail="Tile not found")
    raise HTTPException(status_code=500, detail="App not available")


# ========== Config Routes ==========

@config_router.get("/", response_model=Dict[str, Any])
async def get_config(app = Depends(get_app)):
    """Get application configuration"""
    if app:
        return app._config
    raise HTTPException(status_code=500, detail="App not available")


@config_router.get("/processing", response_model=Dict[str, Any])
async def get_processing_config(app = Depends(get_app)):
    """Get processing configuration"""
    if app and app._config:
        return app._config.get("processing", {})
    raise HTTPException(status_code=500, detail="Config not available")


@config_router.get("/streams", response_model=Dict[str, Any])
async def get_streams_config(app = Depends(get_app)):
    """Get streams configuration"""
    if app and app._config:
        return app._config.get("streams", {})
    raise HTTPException(status_code=500, detail="Config not available")


@config_router.post("/reload")
async def reload_config(app = Depends(get_app)):
    """Reload configuration"""
    if app:
        if app.load_config():
            return {"status": "reloaded"}
        raise HTTPException(status_code=400, detail="Failed to reload config")
    raise HTTPException(status_code=500, detail="App not available")
