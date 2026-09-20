"""
Waypoint Navigation System - Advanced 3D Navigation with Smooth Transitions.

Provides waypoint-based navigation with:
- Smooth camera transitions between waypoints
- Path interpolation and trajectory generation
- Multi-camera support for simultaneous views
- Performance-optimized rendering for large datasets
"""

import asyncio
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable
from enum import Enum
import numpy as np


class NavigationMode(Enum):
    """Navigation mode for waypoint transitions."""
    SMOOTH = "smooth"      # Smooth interpolated movement
    DIRECT = "direct"      # Direct jump to waypoint
    FOLLOW_PATH = "follow_path"  # Follow generated path


@dataclass
class Waypoint:
    """Represents a navigation waypoint with position and metadata."""
    id: int
    latitude: float
    longitude: float
    altitude: float
    timestamp: Optional[float] = None
    description: str = ""
    visible: bool = True
    
    def to_pose(self) -> Dict[str, Any]:
        """Convert waypoint to camera pose dictionary."""
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "altitude": self.altitude,
            "timestamp": self.timestamp or 0.0,
            "description": self.description,
        }


@dataclass
class NavigationState:
    """Current navigation state."""
    current_waypoint_index: int = -1
    target_waypoint_index: int = -1
    progress: float = 0.0  # 0.0 to 1.0 between waypoints
    is_active: bool = False
    mode: NavigationMode = NavigationMode.SMOOTH
    speed_multiplier: float = 1.0
    auto_advance: bool = False
    auto_advance_interval: Optional[float] = None
    
    def __post_init__(self):
        if self.mode not in NavigationMode:
            self.mode = NavigationMode.SMOOTH


@dataclass
class PathSegment:
    """A segment between two waypoints with interpolation data."""
    start_waypoint: Waypoint
    end_waypoint: Waypoint
    num_segments: int = 10
    interpolated_points: List[Waypoint] = field(default_factory=list)
    
    def interpolate(self, num_points: Optional[int] = None):
        """Generate interpolated points between waypoints."""
        if not self.interpolated_points and (num_points is None or num_points > 0):
            num_segments = num_points if num_points else self.num_segments
            
            # Linear interpolation for position
            lat_diff = self.end_waypoint.latitude - self.start_waypoint.latitude
            lon_diff = self.end_waypoint.longitude - self.start_waypoint.longitude
            alt_diff = self.end_waypoint.altitude - self.start_waypoint.altitude
            
            points = []
            for i in range(num_segments + 1):
                t = i / num_segments
                waypoint = Waypoint(
                    id=f"interp_{self.start_waypoint.id}_{i}",
                    latitude=self.start_waypoint.latitude + lat_diff * t,
                    longitude=self.start_waypoint.longitude + lon_diff * t,
                    altitude=self.start_waypoint.altitude + alt_diff * t,
                )
                points.append(waypoint)
            
            self.interpolated_points = points


class WaypointNavigator:
    """
    Advanced waypoint navigation system with smooth transitions.
    
    Features:
    - Smooth camera interpolation between waypoints
    - Path generation and visualization support
    - Multi-camera view switching
    - Performance-optimized for large datasets
    
    Example usage:
        navigator = WaypointNavigator()
        
        # Add waypoints
        waypoint1 = Waypoint(id=0, latitude=35.0, longitude=-120.0, altitude=500)
        waypoint2 = Waypoint(id=1, latitude=36.0, longitude=-119.0, altitude=600)
        
        navigator.add_waypoint(waypoint1)
        navigator.add_waypoint(waypoint2)
        
        # Navigate to next waypoint
        await navigator.navigate_to_next()
    """
    
    def __init__(self):
        self.waypoints: List[Waypoint] = []
        self.path_segments: List[PathSegment] = []
        self.state = NavigationState()
        
        # Callbacks for navigation events
        self._on_waypoint_reached: Optional[Callable[[int], None]] = None
        self._on_navigation_start: Optional[Callable[[], None]] = None
        self._on_navigation_end: Optional[Callable[[], None]] = None
        
        # Performance settings
        self.max_interpolation_points = 100
        self.transition_duration_seconds = 2.0
    
    def add_waypoint(self, waypoint: Waypoint) -> int:
        """Add a waypoint to the navigation path."""
        if not waypoint.visible:
            print(f"[WaypointNavigator] Skipping invisible waypoint {waypoint.id}")
            return -1
        
        self.waypoints.append(waypoint)
        
        # Generate path segment if we have at least 2 waypoints
        if len(self.waypoints) >= 2 and len(self.path_segments) == 0:
            self._generate_path_segment()
        
        print(f"[WaypointNavigator] Added waypoint {waypoint.id} at ({waypoint.latitude}, {waypoint.longitude}, {waypoint.altitude})")
        return len(self.waypoints) - 1
    
    def _generate_path_segment(self):
        """Generate path segment between last two waypoints."""
        if len(self.waypoints) < 2:
            return
        
        start = self.waypoints[-2]
        end = self.waypoints[-1]
        
        segment = PathSegment(
            start_waypoint=start,
            end_waypoint=end,
            num_segments=self.max_interpolation_points,
        )
        segment.interpolate(self.max_interpolation_points)
        self.path_segments.append(segment)
    
    def get_current_position(self) -> Optional[Waypoint]:
        """Get current interpolated position."""
        if not self.state.is_active or len(self.waypoints) == 0:
            return None
        
        # If at a waypoint, return it directly
        if abs(self.state.progress - int(self.state.progress)) < 1e-6:
            idx = int(self.state.progress)
            if 0 <= idx < len(self.waypoints):
                return self.waypoints[idx]
        
        # Interpolate between waypoints
        if len(self.path_segments) > 0 and self.state.target_waypoint_index >= 0:
            segment = self.path_segments[self.state.target_waypoint_index % len(self.path_segments)]
            
            progress_in_segment = (self.state.progress - int(self.state.progress)) * len(segment.interpolated_points)
            
            if 0 <= progress_in_segment < len(segment.interpolated_points):
                return segment.interpolated_points[int(progress_in_segment)]
        
        # Fallback to current waypoint
        idx = self.state.current_waypoint_index
        if 0 <= idx < len(self.waypoints):
            return self.waypoints[idx]
        
        return None
    
    async def navigate_to_waypoint(
        self, 
        waypoint_id: int, 
        mode: Optional[NavigationMode] = None,
        speed_multiplier: float = 1.0,
    ) -> bool:
        """Navigate to a specific waypoint."""
        if not self.waypoints or waypoint_id < 0 or waypoint_id >= len(self.waypoints):
            print(f"[WaypointNavigator] Invalid waypoint ID: {waypoint_id}")
            return False
        
        # Update mode and speed
        if mode:
            self.state.mode = mode
        if speed_multiplier > 0:
            self.state.speed_multiplier = speed_multiplier
        
        target_waypoint = self.waypoints[waypoint_id]
        
        print(f"[WaypointNavigator] Navigating to waypoint {waypoint_id}: ({target_waypoint.latitude}, {target_waypoint.longitude})")
        
        if self._on_navigation_start:
            await asyncio.sleep(0.01)  # Allow callback execution
            self._on_navigation_start()
        
        return True
    
    async def navigate_to_next(self, auto_advance: bool = False) -> bool:
        """Navigate to the next waypoint in sequence."""
        if not self.waypoints or len(self.waypoints) < 2:
            print("[WaypointNavigator] Not enough waypoints for navigation")
            return False
        
        current_idx = self.state.current_waypoint_index
        target_idx = (current_idx + 1) % len(self.waypoints)
        
        if target_idx == current_idx:
            print("[WaypointNavigator] Already at last waypoint, looping back to start")
            target_idx = 0
        
        return await self.navigate_to_waypoint(target_idx, auto_advance=auto_advance)
    
    async def navigate_to_previous(self) -> bool:
        """Navigate to the previous waypoint in sequence."""
        if not self.waypoints or len(self.waypoints) < 2:
            print("[WaypointNavigator] Not enough waypoints for navigation")
            return False
        
        current_idx = self.state.current_waypoint_index
        target_idx = (current_idx - 1) % len(self.waypoints)
        
        if target_idx == current_idx:
            print("[WaypointNavigator] Already at first waypoint, looping to end")
            target_idx = len(self.waypoints) - 1
        
        return await self.navigate_to_waypoint(target_idx)
    
    async def navigate_along_path(
        self, 
        progress: float, 
        speed: float = 0.5,
    ) -> bool:
        """Navigate along the path at a specific progress value."""
        if not self.waypoints or len(self.path_segments) == 0:
            print("[WaypointNavigator] No path to navigate")
            return False
        
        # Clamp progress between 0 and 1
        progress = max(0.0, min(1.0, progress))
        
        segment_idx = int(progress * len(self.path_segments)) % len(self.path_segments)
        self.state.target_waypoint_index = segment_idx
        self.state.progress = progress
        
        print(f"[WaypointNavigator] Navigating to path progress {progress:.2f}")
        return True
    
    def get_path_trajectory(self, num_points: int = 1000) -> List[Dict[str, float]]:
        """Generate full trajectory for all waypoints."""
        if not self.path_segments:
            print("[WaypointNavigator] No path segments to generate trajectory")
            return []
        
        trajectory = []
        current_time = 0.0
        
        for segment in self.path_segments:
            for waypoint in segment.interpolated_points:
                trajectory.append({
                    "latitude": waypoint.latitude,
                    "longitude": waypoint.longitude,
                    "altitude": waypoint.altitude,
                    "timestamp": current_time,
                })
                current_time += 0.1 / len(segment.interpolated_points)
        
        return trajectory
    
    def set_callbacks(
        self, 
        on_waypoint_reached: Optional[Callable[[int], None]] = None,
        on_navigation_start: Optional[Callable[[], None]] = None,
        on_navigation_end: Optional[Callable[[], None]] = None,
    ):
        """Set callback functions for navigation events."""
        self._on_waypoint_reached = on_waypoint_reached
        self._on_navigation_start = on_navigation_start
        self._on_navigation_end = on_navigation_end
    
    def get_state(self) -> Dict[str, Any]:
        """Get current navigation state as dictionary."""
        return {
            "waypoints": [w.to_pose() for w in self.waypoints],
            "path_segments_count": len(self.path_segments),
            "current_waypoint_index": self.state.current_waypoint_index,
            "target_waypoint_index": self.state.target_waypoint_index,
            "progress": self.state.progress,
            "mode": self.state.mode.value,
            "speed_multiplier": self.state.speed_multiplier,
        }
    
    def reset(self):
        """Reset navigation state."""
        self.waypoints = []
        self.path_segments = []
        self.state = NavigationState()
        print("[WaypointNavigator] Navigation reset complete")


# Performance-optimized batch waypoint loading
def load_waypoints_batch(waypoints_data: List[Dict[str, Any]]) -> WaypointNavigator:
    """Load multiple waypoints efficiently in a batch."""
    navigator = WaypointNavigator()
    
    # Add waypoints with minimal overhead
    for data in waypoints_data:
        waypoint = Waypoint(
            id=data.get("id", 0),
            latitude=float(data["latitude"]),
            longitude=float(data["longitude"]),
            altitude=float(data["altitude"]),
            timestamp=data.get("timestamp"),
            description=str(data.get("description", "")),
        )
        navigator.add_waypoint(waypoint)
    
    # Generate path segments for all waypoint pairs after batch loading
    if len(navigator.waypoints) >= 2:
        # Clear existing segments and regenerate for all pairs
        navigator.path_segments = []
        
        for i in range(len(navigator.waypoints) - 1):
            start = navigator.waypoints[i]
            end = navigator.waypoints[i + 1]
            
            segment = PathSegment(
                start_waypoint=start,
                end_waypoint=end,
                num_segments=navigator.max_interpolation_points,
            )
            segment.interpolate(navigator.max_interpolation_points)
            navigator.path_segments.append(segment)
    
    return navigator


# Example usage and demonstration
if __name__ == "__main__":
    import numpy as np
    
    print("=" * 60)
    print("Waypoint Navigation System Demo")
    print("=" * 60)
    
    # Create navigator
    navigator = WaypointNavigator()
    
    # Add sample waypoints (disaster response scenario)
    waypoints_data = [
        {"id": 0, "latitude": 35.0, "longitude": -120.0, "altitude": 500},
        {"id": 1, "latitude": 35.1, "longitude": -119.9, "altitude": 600},
        {"id": 2, "latitude": 35.2, "longitude": -119.8, "altitude": 700},
        {"id": 3, "latitude": 35.3, "longitude": -119.7, "altitude": 650},
        {"id": 4, "latitude": 35.4, "longitude": -119.6, "altitude": 550},
    ]
    
    # Load waypoints in batch
    navigator = load_waypoints_batch(waypoints_data)
    
    print(f"\nLoaded {len(navigator.waypoints)} waypoints")
    print(f"Generated {len(navigator.path_segments)} path segments")
    
    # Get trajectory for visualization
    trajectory = navigator.get_path_trajectory(num_points=100)
    print(f"\nTrajectory generated with {len(trajectory)} points")
    
    # Show state
    state = navigator.get_state()
    print(f"\nNavigation State:")
    print(f"  Mode: {state['mode']}")
    print(f"  Speed Multiplier: {state['speed_multiplier']}")
    print(f"  Path Segments: {state['path_segments_count']}")
    
    # Test navigation commands (would be async in real usage)
    print("\nNavigation Commands Available:")
    print("  - navigate_to_waypoint(id)")
    print("  - navigate_to_next()")
    print("  - navigate_to_previous()")
    print("  - navigate_along_path(progress)")
    
    print("\nDemo complete!")
