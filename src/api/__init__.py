"""
API module for REST and WebSocket interfaces
"""

from .server import (
    create_app,
    FastAPIServer,
    start_server,
)
from .websocket import (
    WebSocketServer,
    start_websocket_server,
)
from .routes import (
    api_router,
    streams_router,
    ortho_router,
    tiles_router,
    config_router,
)

__all__ = [
    "create_app",
    "FastAPIServer",
    "start_server",
    "WebSocketServer",
    "start_websocket_server",
    "api_router",
    "streams_router",
    "ortho_router",
    "tiles_router",
    "config_router",
]
