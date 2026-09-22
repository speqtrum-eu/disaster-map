"""
WebSocket Real-Time Update Service for Disaster Map API
Handles real-time trajectory updates, waypoint changes, and live alerts.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field

from websockets.server import serve
from websockets.exceptions import ConnectionClosed

logger = logging.getLogger(__name__)


@dataclass
class WebSocketConnection:
    """Represents a WebSocket connection with subscription state."""
    websocket: Any
    subscribed_topics: Set[str] = field(default_factory=set)
    last_message_time: float = 0.0
    ping_interval: float = 30.0
    pong_timeout: float = 10.0


@dataclass
class RealTimeUpdate:
    """A real-time update message."""
    topic: str
    data: Dict[str, Any]
    timestamp: float
    source: Optional[str] = None


class WebSocketService:
    """
    Manages WebSocket connections and real-time updates.
    
    Features:
    - Topic-based subscriptions (trajectory, waypoints, alerts)
    - Automatic reconnection handling
    - Message broadcasting to subscribers
    - Connection health monitoring with ping/pong
    """
    
    def __init__(self):
        self.connections: Dict[str, WebSocketConnection] = {}
        self.subscribers: Dict[str, Set[WebSocketConnection]] = {
            'trajectory': set(),
            'waypoints': set(),
            'alerts': set()
        }
        self.update_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self.broadcast_task: Optional[asyncio.Task] = None
        self.running = False
    
    async def start(self):
        """Start the WebSocket service."""
        logger.info("Starting WebSocket Service...")
        
        # Start broadcast task in background
        self.broadcast_task = asyncio.create_task(
            self._broadcast_loop()
        )
        
        self.running = True
        
        # Setup server with custom handler
        async def handle_connection(websocket, path):
            await self._handle_connection(websocket)
        
        await serve(handle_connection, "0.0.0.0", 8765, ping_interval=30, 
                    ping_timeout=10, max_size=10 * 1024 * 1024)  # 10MB max message
    
    async def stop(self):
        """Stop the WebSocket service gracefully."""
        logger.info("Stopping WebSocket Service...")
        
        self.running = False
        
        if self.broadcast_task:
            self.broadcast_task.cancel()
            try:
                await self.broadcast_task
            except asyncio.CancelledError:
                pass
        
        # Close all connections
        for conn in list(self.connections.values()):
            try:
                await conn.websocket.close(1001, "Server shutting down")
            except Exception:
                pass
        
        logger.info("WebSocket Service stopped")
    
    async def _handle_connection(self, websocket):
        """Handle a new WebSocket connection."""
        conn_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        
        try:
            await websocket.accept()
            
            # Create connection object
            connection = WebSocketConnection(
                websocket=websocket,
                subscribed_topics=set(),
                last_message_time=time.time()
            )
            
            self.connections[conn_id] = connection
            
            logger.info(f"WebSocket connected: {conn_id}")
            
            # Handle messages
            async for message in websocket:
                await self._handle_message(conn_id, message)
                
        except ConnectionClosed as e:
            logger.info(f"WebSocket disconnected: {conn_id} (code={e.code})")
            await self._remove_connection(conn_id)
            
        except Exception as e:
            logger.error(f"WebSocket error for {conn_id}: {e}")
            await self._remove_connection(conn_id)
    
    async def _handle_message(self, conn_id: str, message: str):
        """Handle an incoming WebSocket message."""
        try:
            data = json.loads(message)
            
            # Update last activity time
            if conn_id in self.connections:
                self.connections[conn_id].last_message_time = time.time()
            
            msg_type = data.get('type', 'unknown')
            
            if msg_type == 'subscribe':
                topic = data.get('topic', 'trajectory')
                await self._subscribe(conn_id, topic)
                
            elif msg_type == 'unsubscribe':
                topic = data.get('topic', 'trajectory')
                await self._unsubscribe(conn_id, topic)
                
            elif msg_type in ('update', 'alert'):
                # Queue update for broadcasting
                update = RealTimeUpdate(
                    topic=data.get('topic', 'trajectory'),
                    data=data.get('data', {}),
                    timestamp=time.time(),
                    source=data.get('source')
                )
                
                await self.update_queue.put(update)
                
            elif msg_type == 'ping':
                # Echo pong response
                await websocket.send(json.dumps({'type': 'pong'}))
                
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON message from {conn_id}: {message[:100]}")
    
    async def _subscribe(self, conn_id: str, topic: str):
        """Subscribe a connection to a topic."""
        if conn_id not in self.connections:
            return
        
        connection = self.connections[conn_id]
        
        # Add to subscribers for this topic
        if topic in self.subscribers:
            self.subscribers[topic].add(connection)
        
        # Track subscription locally
        connection.subscribed_topics.add(topic)
        
        logger.info(f"Connection {conn_id} subscribed to '{topic}'")
    
    async def _unsubscribe(self, conn_id: str, topic: str):
        """Unsubscribe a connection from a topic."""
        if conn_id not in self.connections:
            return
        
        connection = self.connections[conn_id]
        
        # Remove from subscribers for this topic
        if topic in self.subscribers:
            self.subscribers[topic].discard(connection)
        
        # Remove local subscription tracking
        connection.subscribed_topics.discard(topic)
        
        logger.info(f"Connection {conn_id} unsubscribed from '{topic}'")
    
    async def _remove_connection(self, conn_id: str):
        """Remove a connection and clean up subscriptions."""
        if conn_id not in self.connections:
            return
        
        connection = self.connections[conn_id]
        
        # Unsubscribe from all topics
        for topic in list(connection.subscribed_topics):
            await self._unsubscribe(conn_id, topic)
        
        del self.connections[conn_id]
    
    async def broadcast(self, update: RealTimeUpdate):
        """Broadcast an update to all subscribers of a topic."""
        if not self.running:
            return
        
        subscribers = self.subscribers.get(update.topic, set())
        
        if not subscribers:
            logger.debug(f"No subscribers for topic '{update.topic}'")
            return
        
        # Send to each subscriber concurrently
        messages = [
            json.dumps({
                'type': update.topic,
                'data': update.data,
                'timestamp': update.timestamp,
                'source': update.source
            })
            for _ in subscribers
        ]
        
        await asyncio.gather(
            *[self._send_to_connection(conn, msg) 
              for conn, msg in zip(subscribers, messages)],
            return_exceptions=True
        )
    
    async def _broadcast_loop(self):
        """Background loop to process and broadcast updates."""
        while self.running:
            try:
                update = await asyncio.wait_for(
                    self.update_queue.get(), 
                    timeout=1.0
                )
                
                # Broadcast the update
                await self.broadcast(update)
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Broadcast loop error: {e}")
    
    async def _send_to_connection(self, connection: WebSocketConnection, message: str):
        """Send a message to a specific connection."""
        try:
            await connection.websocket.send(message)
        except ConnectionClosed:
            # Clean up stale connections
            if connection.conn_id in self.connections:
                del self.connections[connection.conn_id]
    
    @property
    def active_connections(self) -> int:
        """Get the number of active WebSocket connections."""
        return len(self.connections)
    
    @property
    def total_subscribers(self) -> Dict[str, int]:
        """Get subscriber counts per topic."""
        return {topic: len(subs) for topic, subs in self.subscribers.items()}


# ============================================================================
# Real-Time Update Generators
# ============================================================================

async def trajectory_update_generator(trajectory_data: Dict):
    """Generate real-time trajectory updates from a data source."""
    """
    Yields trajectory update messages as new pose data arrives.
    
    Usage:
        async for update in trajectory_update_generator(data_source):
            await websocket.send(json.dumps(update))
    """
    import time
    
    # Initial full state
    yield {
        'type': 'trajectory',
        'data': {
            'poses': trajectory_data.get('poses', []),
            'metadata': {
                'start_time': trajectory_data.get('start_time'),
                'end_time': trajectory_data.get('end_time'),
                'total_distance': trajectory_data.get('total_distance')
            }
        },
        'timestamp': time.time()
    }
    
    # Simulate incremental updates (replace with real data source)
    while True:
        await asyncio.sleep(1.0)  # Update interval
        
        try:
            new_pose = await get_next_pose()  # Replace with actual data source
            
            if new_pose:
                yield {
                    'type': 'trajectory',
                    'data': {
                        'pose': new_pose,
                        'delta_time': time.time() - last_update_time
                    },
                    'timestamp': time.time()
                }
                
        except Exception as e:
            logger.error(f"Error generating trajectory update: {e}")


async def waypoint_update_generator(waypoints_data: Dict):
    """Generate real-time waypoint updates."""
    import time
    
    # Initial full state
    yield {
        'type': 'waypoints',
        'data': waypoints_data,
        'timestamp': time.time()
    }
    
    while True:
        await asyncio.sleep(5.0)  # Check interval
        
        try:
            updated_waypoints = await check_waypoint_changes()
            
            if updated_waypoints is not None:
                yield {
                    'type': 'waypoints',
                    'data': updated_waypoints,
                    'timestamp': time.time()
                }
                
        except Exception as e:
            logger.error(f"Error generating waypoint update: {e}")


# ============================================================================
# Utility Functions
# ============================================================================

def create_live_update(topic: str, data: Dict) -> Dict:
    """Create a live update message."""
    return {
        'type': topic,
        'data': data,
        'timestamp': time.time(),
        'source': 'api'
    }


def validate_websocket_message(message: Dict) -> bool:
    """Validate an incoming WebSocket message."""
    required_fields = ['type']
    
    if not all(field in message for field in required_fields):
        return False
    
    # Validate topic subscriptions
    valid_topics = {'trajectory', 'waypoints', 'alerts'}
    if 'topic' in message and message['topic'] not in valid_topics:
        return False
    
    return True


# ============================================================================
# Main Entry Point (for testing)
# ============================================================================

async def run_websocket_server(port: int = 8765):
    """Run the WebSocket server for testing."""
    service = WebSocketService()
    
    await service.start()
    
    print(f"WebSocket server running on ws://localhost:{port}")
    print("Available topics: trajectory, waypoints, alerts")
    print("\nTest commands:")
    print('  {"type": "subscribe", "topic": "trajectory"}')
    print('  {"type": "update", "topic": "trajectory", "data": {...}}')
    
    # Keep running (for testing)
    try:
        while service.running:
            await asyncio.sleep(1.0)
    except KeyboardInterrupt:
        pass
    
    await service.stop()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="WebSocket Real-Time Service")
    parser.add_argument("--port", type=int, default=8765, help="Server port")
    
    args = parser.parse_args()
    
    asyncio.run(run_websocket_server(args.port))
