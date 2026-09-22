"""
Disaster Map API Module
Provides REST API endpoints for trajectory, point cloud, waypoints, and real-time updates.
"""

from .server import app
from .data_processing import (
    load_ply_points,
    parse_ply_header,
    get_pointcloud_stats,
    ply_to_3dtiles,
    generate_trajectory_visualization_data,
    generate_timeline_metadata,
    LazyPointCloud
)
from .websocket_service import WebSocketService

__version__ = "1.0.0"

__all__ = [
    # Server
    "app",
    
    # Data Processing
    "load_ply_points",
    "parse_ply_header",
    "get_pointcloud_stats",
    "ply_to_3dtiles",
    "generate_trajectory_visualization_data",
    "generate_timeline_metadata",
    "LazyPointCloud",
    
    # WebSocket
    "WebSocketService"
]
