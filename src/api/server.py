"""
FastAPI server for the Disaster Map application
"""

import os
import sys
import json
import asyncio
from typing import Optional, Dict, Any, List
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
import uvicorn

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.models import (
    StreamConfig,
    ProcessingConfig,
    Frame,
    OrthomosaicTile,
)
from src.core.utils import get_logger, timestamp_now
from src.api.websocket import WebSocketServer

logger = get_logger("api.server")


class FastAPIServer:
    """
    FastAPI server for the Disaster Map application
    
    Provides REST API endpoints for:
    - Stream management
    - Orthomosaic retrieval
    - Configuration
    - Status monitoring
    """
    
    def __init__(
        self,
        title: str = "Disaster Map API",
        description: str = "API for Disaster Map - Multi-Stream Orthomosaic System",
        version: str = "1.0.0",
        host: str = "0.0.0.0",
        port: int = 8000,
        cors_origins: List[str] = ["*"],
    ):
        self.title = title
        self.description = description
        self.version = version
        self.host = host
        self.port = port
        self.cors_origins = cors_origins
        
        # Create FastAPI app
        self.app = FastAPI(
            title=self.title,
            description=self.description,
            version=self.version,
        )
        
        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=self.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # WebSocket server
        self.ws_server: Optional[WebSocketServer] = None
        
        # Setup routes
        self._setup_routes()
    
    def _setup_routes(self) -> None:
        """Setup API routes"""
        # Import routes
        from . import routes
        
        # Mount static files (for frontend)
        try:
            static_dir = Path(__file__).parent.parent.parent / "frontend" / "dist"
            if static_dir.exists():
                self.app.mount("/static", StaticFiles(directory=static_dir), name="static")
        except Exception as e:
            logger.warning(f"Could not mount static files: {e}")
        
        # Include API routers
        self.app.include_router(routes.api_router, prefix="/api/v1")
        self.app.include_router(routes.streams_router, prefix="/api/v1/streams")
        self.app.include_router(routes.ortho_router, prefix="/api/v1/orthomosaic")
        self.app.include_router(routes.tiles_router, prefix="/api/v1/tiles")
        self.app.include_router(routes.config_router, prefix="/api/v1/config")
        
        # Root endpoint
        @self.app.get("/", response_class=HTMLResponse)
        async def root():
            return """
            <html>
                <head>
                    <title>Disaster Map API</title>
                </head>
                <body>
                    <h1>Disaster Map API</h1>
                    <p>See <a href="/docs">API Documentation</a></p>
                    <p>See <a href="/static">Web Interface</a></p>
                </body>
            </html>
            """
        
        # Health check
        @self.app.get("/health")
        async def health_check():
            return {"status": "healthy", "timestamp": timestamp_now()}
    
    def set_app_reference(self, app: Any) -> None:
        """Set reference to the main application"""
        self.app.state.app = app
    
    def start(self, host: Optional[str] = None, port: Optional[int] = None) -> None:
        """Start the server"""
        actual_host = host or self.host
        actual_port = port or self.port
        
        logger.info(f"Starting FastAPI server on {actual_host}:{actual_port}")
        
        # Start WebSocket server in background
        self.ws_server = WebSocketServer(host=actual_host, port=actual_port + 1)
        self.ws_server.start()
        
        # Start FastAPI server
        uvicorn.run(
            self.app,
            host=actual_host,
            port=actual_port,
            log_level="info",
        )
    
    async def start_async(self, host: Optional[str] = None, port: Optional[int] = None) -> None:
        """Start the server asynchronously"""
        actual_host = host or self.host
        actual_port = port or self.port
        
        logger.info(f"Starting FastAPI server on {actual_host}:{actual_port}")
        
        # Create server config
        config = uvicorn.Config(
            self.app,
            host=actual_host,
            port=actual_port,
            log_level="info",
        )
        
        # Create server
        server = uvicorn.Server(config)
        
        # Start WebSocket server
        self.ws_server = WebSocketServer(host=actual_host, port=actual_port + 1)
        await self.ws_server.start_async()
        
        # Start FastAPI server
        await server.startup()
        await server.main_loop()


def create_app(
    title: str = "Disaster Map API",
    description: str = "API for Disaster Map - Multi-Stream Orthomosaic System",
    version: str = "1.0.0",
    host: str = "0.0.0.0",
    port: int = 8000,
    cors_origins: List[str] = ["*"],
) -> FastAPI:
    """Create a FastAPI application"""
    server = FastAPIServer(
        title=title,
        description=description,
        version=version,
        host=host,
        port=port,
        cors_origins=cors_origins,
    )
    return server.app


def start_server(
    host: str = "0.0.0.0",
    port: int = 8000,
    title: str = "Disaster Map API",
    description: str = "API for Disaster Map - Multi-Stream Orthomosaic System",
    version: str = "1.0.0",
    cors_origins: List[str] = ["*"],
) -> None:
    """Start the FastAPI server"""
    server = FastAPIServer(
        title=title,
        description=description,
        version=version,
        host=host,
        port=port,
        cors_origins=cors_origins,
    )
    server.start()


if __name__ == "__main__":
    # Load configuration
    try:
        from src.core.utils import load_config
        config = load_config("config/streams.yaml")
        network_config = config.get("network", {})
        
        host = network_config.get("api_host", "0.0.0.0")
        port = network_config.get("api_port", 8000)
        cors_origins = network_config.get("cors_origins", ["*"])
        
        start_server(
            host=host,
            port=port,
            cors_origins=cors_origins,
        )
        
    except Exception as e:
        logger.error(f"Error starting server: {e}")
        sys.exit(1)
