"""
FastAPI Server for Disaster Map Web Viewer
Provides REST API endpoints for trajectory, point cloud, waypoints, and real-time updates.
"""

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional

import numpy as np
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from websockets.server import serve

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Demo data paths
DEMO_DIR = Path(__file__).parent.parent.parent / "results" / "demo_20260920_230738"
TRAJECTORY_FILE = DEMO_DIR / "poses" / "trajectory.json"
PLY_FILES_DIR = DEMO_DIR / "maps"

# Cache for loaded data
_data_cache: Dict[str, any] = {}


class Pose(BaseModel):
    """Camera pose with position and orientation."""
    timestamp: float
    x: float
    y: float
    z: float
    roll: float
    pitch: float
    yaw: float
    confidence: float


class TrajectoryData(BaseModel):
    """Trajectory data with poses and metadata."""
    poses: List[Pose]
    start_time: float
    end_time: float
    total_distance: float
    frame_rate: float


class Waypoint(BaseModel):
    """Rescue waypoint for navigation."""
    id: int
    name: str
    position: Dict[str, float]  # x, y, z
    priority: int
    description: Optional[str] = None


# Initialize FastAPI app
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown."""
    logger.info("Starting Disaster Map API server...")
    
    # Pre-load demo data on startup
    if TRAJECTORY_FILE.exists():
        _data_cache["trajectory"] = load_trajectory(TRAJECTORY_FILE)
        logger.info(f"Loaded trajectory with {_data_cache['trajectory']['poses']} poses")
    
    yield
    
    logger.info("Shutting down Disaster Map API server...")


app = FastAPI(
    title="Disaster Map API",
    description="REST API for disaster map visualization and real-time updates",
    version="1.0.0",
    lifespan=lifespan,
)


# ============================================================================
# Trajectory Endpoints
# ============================================================================

@app.get("/api/trajectory", response_model=TrajectoryData)
async def get_trajectory(
    file_path: Optional[str] = None,
    lazy_load: bool = False
):
    """
    Load and return trajectory JSON with camera poses.
    
    - **file_path**: Path to trajectory JSON file (optional, uses demo data if not provided)
    - **lazy_load**: If True, defer full parsing for large files
    
    Returns trajectory data including all poses, timestamps, and metadata.
    """
    path = Path(file_path) if file_path else TRAJECTORY_FILE
    
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Trajectory file not found: {path}")
    
    # Check cache first
    if path.name in _data_cache.get("trajectory", {}):
        logger.info(f"Serving cached trajectory: {path.name}")
        return _data_cache["trajectory"]
    
    try:
        with open(path, 'r') as f:
            data = json.load(f)
        
        # Parse poses
        poses = []
        timestamps = []
        positions = []
        
        for pose_data in data.get("poses", data):
            if isinstance(pose_data, dict):
                pose = Pose(
                    timestamp=pose_data.get("timestamp", 0),
                    x=pose_data.get("x", 0),
                    y=pose_data.get("y", 0),
                    z=pose_data.get("z", 0),
                    roll=np.deg2rad(pose_data.get("roll", 0)),
                    pitch=np.deg2rad(pose_data.get("pitch", 0)),
                    yaw=np.deg2rad(pose_data.get("yaw", 0)),
                    confidence=pose_data.get("confidence", 1.0)
                )
            else:
                # Handle legacy format with numpy arrays
                pose = Pose(
                    timestamp=float(pose_data[0]) if len(pose_data) > 0 else 0,
                    x=float(pose_data[1]) if len(pose_data) > 1 else 0,
                    y=float(pose_data[2]) if len(pose_data) > 2 else 0,
                    z=float(pose_data[3]) if len(pose_data) > 3 else 0,
                    roll=np.deg2rad(float(pose_data[4]) if len(pose_data) > 4 else 0),
                    pitch=np.deg2rad(float(pose_data[5]) if len(pose_data) > 5 else 0),
                    yaw=np.deg2rad(float(pose_data[6]) if len(pose_data) > 6 else 0),
                    confidence=1.0
                )
            
            poses.append(pose)
            timestamps.append(pose.timestamp)
            positions.append((pose.x, pose.y, pose.z))
        
        # Calculate metadata
        start_time = min(timestamps) if timestamps else 0
        end_time = max(timestamps) if timestamps else 0
        
        # Calculate total distance (Euclidean between consecutive poses)
        total_distance = 0.0
        for i in range(1, len(positions)):
            dx = positions[i][0] - positions[i-1][0]
            dy = positions[i][1] - positions[i-1][1]
            dz = positions[i][2] - positions[i-1][2]
            total_distance += np.sqrt(dx**2 + dy**2 + dz**2)
        
        # Estimate frame rate from timestamps
        if len(timestamps) > 1:
            time_diff = timestamps[-1] - timestamps[0]
            frame_rate = len(poses) / max(time_diff, 0.001)
        else:
            frame_rate = 30.0  # Default
        
        trajectory_data = TrajectoryData(
            poses=[p.dict() for p in poses],
            start_time=start_time,
            end_time=end_time,
            total_distance=round(total_distance, 2),
            frame_rate=round(frame_rate, 1)
        )
        
        # Cache the result
        _data_cache["trajectory"] = trajectory_data
        
        logger.info(f"Loaded trajectory: {len(poses)} poses, {total_distance:.2f}m distance")
        return trajectory_data
    
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON in trajectory file: {e}")


@app.get("/api/trajectory/stats", response_model=dict)
async def get_trajectory_stats():
    """Get summary statistics for the loaded trajectory."""
    if "trajectory" not in _data_cache:
        raise HTTPException(status_code=404, detail="No trajectory data loaded")
    
    trajectory = _data_cache["trajectory"]
    poses = trajectory.poses
    
    # Calculate bounding box from pose coordinates
    positions = np.array([[p.x, p.y, p.z] for p in poses])
    min_pos = np.min(positions, axis=0)
    max_pos = np.max(positions, axis=0)
    
    return {
        "pose_count": len(poses),
        "duration_seconds": trajectory.end_time - trajectory.start_time,
        "frame_rate": trajectory.frame_rate,
        "total_distance_meters": trajectory.total_distance,
        "bounding_box": {
            "min": [round(min_pos[0], 2), round(min_pos[1], 2), round(min_pos[2], 2)],
            "max": [round(max_pos[0], 2), round(max_pos[1], 2), round(max_pos[2], 2)]
        },
        "average_speed_mps": trajectory.total_distance / max(trajectory.end_time - trajectory.start_time, 0.001)
    }


# ============================================================================
# Point Cloud Endpoints
# ============================================================================

@app.get("/api/pointcloud", response_class=StreamingResponse)
async def get_pointcloud(
    file_path: Optional[str] = None,
    format: str = "ply",  # ply, xyz, binary
    chunk_size: int = 1024 * 1024  # 1MB chunks for streaming
):
    """
    Serve PLY point cloud data with lazy loading support.
    
    - **file_path**: Path to PLY file (optional, uses demo data if not provided)
    - **format**: Output format (ply, xyz, binary)
    - **chunk_size**: Size of chunks for streaming
    
    Returns a stream of point cloud data optimized for large files.
    """
    path = Path(file_path) if file_path else PLY_FILES_DIR / "pointcloud.ply"
    
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Point cloud file not found: {path}")
    
    def iter_file():
        """Generator for streaming point cloud data."""
        with open(path, 'rb') as f:
            # Read header first to determine format
            header = f.read(8192).decode('utf-8', errors='replace')
            
            if format == "xyz":
                # Extract points from PLY header and stream as XYZ
                import re
                
                def extract_points(header):
                    """Extract point coordinates from PLY header."""
                    pattern = r'x\s*=\s*\d+\s*y\s*=\s*\d+\s*z\s*=\s*\d+'
                    matches = re.findall(pattern, header)
                    
                    for match in matches:
                        coords = [float(x.strip()) for x in match.split('=')[1].split(',')]
                        yield f"{coords[0]:.6f} {coords[1]:.6f} {coords[2]:.6f}\n"
                
                return iter(extract_points(header))
            
            # Stream binary data in chunks
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                yield chunk
    
    headers = {
        "Content-Type": f"application/octet-stream; charset={format}",
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "X-Point-Cloud-File": path.name
    }
    
    return StreamingResponse(
        iter_file(),
        media_type=f"application/{format}",
        headers=headers
    )


@app.get("/api/pointcloud/stats")
async def get_pointcloud_stats(file_path: Optional[str] = None):
    """Get statistics about the point cloud file."""
    path = Path(file_path) if file_path else PLY_FILES_DIR / "pointcloud.ply"
    
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Point cloud file not found: {path}")
    
    import struct
    
    with open(path, 'rb') as f:
        # Read header
        magic = f.read(4)
        if magic != b'PLY':
            raise HTTPException(status_code=400, detail="Invalid PLY file")
        
        version = f.read(2).decode('utf-8')
        if version not in ['1.0', '1.1']:
            raise HTTPException(status_code=400, detail=f"Unsupported PLY version: {version}")
        
        # Read element count and properties
        elements = []
        while True:
            elem_name = f.read(8).decode('utf-8')
            if not elem_name or elem_name == 'end_header':
                break
            
            num_elements = struct.unpack('<I', f.read(4))[0]
            
            for _ in range(num_elements):
                prop_type = f.read(2)
                prop_name = f.read(8).decode('utf-8')
                elements.append((prop_type, prop_name))
        
        # Count points (simplified - assumes vertex element with x,y,z)
        point_count = 0
        try:
            # Find vertex count from header
            for elem in elements:
                if elem[1] == 'vertex':
                    vertex_count = struct.unpack('<I', f.read(4))[0]
                    point_count = vertex_count
                    break
        except (struct.error, IOError):
            pass
        
        file_size = path.stat().st_size
    
    return {
        "file_path": str(path),
        "file_size_bytes": file_size,
        "point_count": point_count,
        "format": "PLY",
        "version": version
    }


# ============================================================================
# Waypoints Endpoints
# ============================================================================

@app.get("/api/waypoints")
async def get_waypoints(
    category: Optional[str] = None,
    priority: Optional[int] = None
):
    """
    Get rescue waypoints for navigation.
    
    - **category**: Filter by waypoint category (rescue, hazard, landmark)
    - **priority**: Filter by minimum priority level
    
    Returns list of waypoints with positions and metadata.
    """
    # Demo waypoints - in production, load from database or external source
    demo_waypoints = [
        Waypoint(
            id=1,
            name="Main Entrance",
            position={"x": 0.0, "y": 0.0, "z": 50.0},
            priority=1,
            description="Primary access point to disaster zone"
        ),
        Waypoint(
            id=2,
            name="Rescue Station A",
            position={"x": 150.0, "y": -75.0, "z": 48.0},
            priority=2,
            description="Medical support station"
        ),
        Waypoint(
            id=3,
            name="Rescue Station B",
            position={"x": -120.0, "y": 90.0, "z": 52.0},
            priority=2,
            description="Equipment and supplies depot"
        ),
        Waypoint(
            id=4,
            name="Hazard Zone",
            position={"x": 80.0, "y": 120.0, "z": 35.0},
            priority=5,
            description="Unstable structure - avoid"
        ),
        Waypoint(
            id=5,
            name="Helipad",
            position={"x": -200.0, "y": -150.0, "z": 80.0},
            priority=1,
            description="Aerial access point"
        ),
    ]
    
    # Apply filters
    if category:
        demo_waypoints = [w for w in demo_waypoints 
                         if any(cat.lower() in w.name.lower() or cat.lower() in w.description.lower() 
                               for cat in ["rescue", "hazard", "landmark"])]
    
    if priority is not None:
        demo_waypoints = [w for w in demo_waypoints if w.priority >= priority]
    
    return {"waypoints": [w.dict() for w in demo_waypoints]}


@app.post("/api/waypoints")
async def add_waypoint(waypoint: Waypoint):
    """Add a new rescue waypoint."""
    # In production, validate and store in database
    logger.info(f"Adding waypoint: {waypoint.name} at ({waypoint.position['x']}, {waypoint.position['y']})")
    
    return {"success": True, "waypoint_id": waypoint.id}


@app.delete("/api/waypoints/{waypoint_id}")
async def delete_waypoint(waypoint_id: int):
    """Remove a rescue waypoint."""
    logger.info(f"Removing waypoint ID {waypoint_id}")
    
    return {"success": True, "deleted_id": waypoint_id}


# ============================================================================
# Real-time WebSocket Endpoint
# ============================================================================

@app.websocket("/api/live")
async def websocket_live_updates(
    websocket: WebSocket,
    subscribe_to: Optional[str] = None
):
    """
    WebSocket endpoint for real-time updates.
    
    Supports subscribing to trajectory updates, waypoint changes, and alerts.
    
    - **subscribe_to**: Topic to subscribe (trajectory, waypoints, alerts)
    """
    await websocket.accept()
    logger.info(f"WebSocket connection established: {websocket.client.host}:{websocket.client.port}")
    
    # Connection state
    connections = {"trajectory": set(), "waypoints": set(), "alerts": set()}
    trajectory_updates = []
    waypoint_updates = []
    
    try:
        while True:
            # Receive message (can be JSON or text)
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                
                if "type" in message:
                    msg_type = message["type"]
                    
                    if msg_type == "subscribe":
                        topic = message.get("topic", "trajectory")
                        connections[topic].add(websocket)
                        logger.info(f"Subscribed to '{topic}': {websocket.client.host}")
                        
                    elif msg_type == "unsubscribe":
                        topic = message.get("topic", "trajectory")
                        connections[topic].discard(websocket)
                        logger.info(f"Unsubscribed from '{topic}'")
                        
                    elif msg_type in ["update", "alert"]:
                        # Forward update to all subscribers
                        if topic := message.get("topic"):
                            for conn in connections.get(topic, set()):
                                await conn.send_json(message)
                                
            except json.JSONDecodeError:
                # Handle raw text messages (e.g., heartbeat)
                pass
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket connection closed: {websocket.client.host}")
        
        # Clean up connections
        for topic, conns in connections.items():
            conns.discard(websocket)
    
    finally:
        await websocket.close()


@app.get("/api/live/status")
async def get_live_status():
    """Get current WebSocket connection status."""
    return {
        "active_connections": sum(len(conns) for conns in connections.values()),
        "subscribed_topics": list(connections.keys()),
        "connection_counts": {topic: len(conns) for topic, conns in connections.items()}
    }


# ============================================================================
# Utility Endpoints
# ============================================================================

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": time.time()}


@app.get("/api/version")
async def get_version():
    """Get API version information."""
    return {
        "version": "1.0.0",
        "name": "Disaster Map API",
        "endpoints": [
            "/api/trajectory",
            "/api/pointcloud", 
            "/api/waypoints",
            "/api/live"
        ]
    }


if __name__ == "__main__":
    import uvicorn
    
    # Start server with Uvicorn
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
