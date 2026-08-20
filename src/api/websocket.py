"""
WebSocket server for real-time communication
"""

import asyncio
import json
import threading
from typing import Optional, Dict, Any, List, Set, Callable
from pathlib import Path
import websockets

# Add src to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.models import Frame, OrthomosaicTile
from src.core.utils import get_logger, timestamp_now

logger = get_logger("api.websocket")


class WebSocketServer:
    """
    WebSocket server for real-time updates
    
    Provides WebSocket endpoints for:
    - Frame updates
    - Orthomosaic updates
    - Tile updates
    - Status notifications
    """
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8001):
        self.host = host
        self.port = port
        self._server: Optional[websockets.serve] = None
        self._running: bool = False
        self._connections: Set[websockets.WebSocketServerProtocol] = set()
        self._lock = threading.Lock()
        
        # Message handlers
        self._message_handlers: Dict[str, Callable[[Dict[str, Any]], None]] = {}
    
    def register_handler(self, message_type: str, handler: Callable[[Dict[str, Any]], None]) -> None:
        """Register a message handler"""
        self._message_handlers[message_type] = handler
    
    def unregister_handler(self, message_type: str) -> None:
        """Unregister a message handler"""
        if message_type in self._message_handlers:
            del self._message_handlers[message_type]
    
    async def _handler(self, websocket: websockets.WebSocketServerProtocol, path: str) -> None:
        """WebSocket connection handler"""
        with self._lock:
            self._connections.add(websocket)
        
        logger.info(f"New WebSocket connection from {websocket.remote_address}")
        
        try:
            async for message in websocket:
                try:
                    # Parse message
                    data = json.loads(message)
                    message_type = data.get("type", "unknown")
                    
                    # Handle message
                    if message_type in self._message_handlers:
                        self._message_handlers[message_type](data)
                    else:
                        logger.warning(f"Unknown message type: {message_type}")
                        
                    # Send acknowledgment
                    await websocket.send(json.dumps({
                        "type": "ack",
                        "message_type": message_type,
                        "timestamp": timestamp_now(),
                    }))
                    
                except json.JSONDecodeError:
                    logger.error("Invalid JSON message")
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": "Invalid JSON",
                    }))
                except Exception as e:
                    logger.error(f"Error handling message: {e}")
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": str(e),
                    }))
        
        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket connection closed")
        finally:
            with self._lock:
                self._connections.discard(websocket)
    
    async def _broadcast_loop(self) -> None:
        """Background loop for broadcasting updates"""
        while self._running:
            await asyncio.sleep(0.1)
    
    def start(self) -> None:
        """Start the WebSocket server in a background thread"""
        if self._running:
            logger.warning("WebSocket server already running")
            return
        
        self._running = True
        
        # Start server in background thread
        def run_server():
            asyncio.run(self._run_server())
        
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        
        logger.info(f"WebSocket server started on {self.host}:{self.port}")
    
    async def start_async(self) -> None:
        """Start the WebSocket server asynchronously"""
        if self._running:
            logger.warning("WebSocket server already running")
            return
        
        self._running = True
        await self._run_server()
    
    async def _run_server(self) -> None:
        """Run the WebSocket server"""
        self._server = await websockets.serve(
            self._handler,
            self.host,
            self.port,
            ping_interval=None,
        )
        
        logger.info(f"WebSocket server listening on {self.host}:{self.port}")
        
        # Start broadcast loop
        await self._broadcast_loop()
        
        # Wait for server to complete (shouldn't happen)
        await self._server.wait_closed()
    
    def stop(self) -> None:
        """Stop the WebSocket server"""
        if not self._running:
            return
        
        self._running = False
        
        if self._server:
            asyncio.run(self._server.ws_server.close())
            self._server = None
        
        with self._lock:
            for connection in self._connections:
                try:
                    asyncio.run(connection.close())
                except Exception:
                    pass
            self._connections.clear()
        
        logger.info("WebSocket server stopped")
    
    async def broadcast(self, message: Dict[str, Any]) -> None:
        """Broadcast a message to all connected clients"""
        message["timestamp"] = timestamp_now()
        message_json = json.dumps(message)
        
        with self._lock:
            disconnected = set()
            for connection in self._connections:
                try:
                    await connection.send(message_json)
                except Exception as e:
                    logger.error(f"Error broadcasting to client: {e}")
                    disconnected.add(connection)
            
            # Remove disconnected clients
            for connection in disconnected:
                self._connections.discard(connection)
    
    async def send_frame_update(self, frame: Frame) -> None:
        """Send frame update to clients"""
        message = {
            "type": "frame_update",
            "data": {
                "id": frame.id,
                "stream_id": frame.stream_id,
                "timestamp": frame.timestamp,
                "frame_number": frame.frame_number,
                "resolution": list(frame.resolution),
            },
        }
        await self.broadcast(message)
    
    async def send_orthomosaic_update(self, orthomosaic: np.ndarray, timestamp: float) -> None:
        """Send orthomosaic update to clients"""
        # Note: In production, you might want to send a thumbnail or tile info
        # rather than the full image
        message = {
            "type": "orthomosaic_update",
            "data": {
                "timestamp": timestamp,
                "resolution": list(orthomosaic.shape[:2]),
                # Could include thumbnail data
            },
        }
        await self.broadcast(message)
    
    async def send_tile_update(self, tiles: List[OrthomosaicTile]) -> None:
        """Send tile update to clients"""
        message = {
            "type": "tile_update",
            "data": {
                "tile_count": len(tiles),
                "tiles": [
                    {
                        "x": t.x,
                        "y": t.y,
                        "z": t.z,
                        "timestamp": t.timestamp,
                    }
                    for t in tiles
                ],
            },
        }
        await self.broadcast(message)
    
    async def send_status_update(self, status: Dict[str, Any]) -> None:
        """Send status update to clients"""
        message = {
            "type": "status_update",
            "data": status,
        }
        await self.broadcast(message)
    
    def get_connection_count(self) -> int:
        """Get number of active connections"""
        with self._lock:
            return len(self._connections)


# Import numpy for type hints
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    logger.warning("NumPy not available")
