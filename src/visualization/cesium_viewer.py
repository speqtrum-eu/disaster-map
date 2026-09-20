"""
CesiumJS Viewer Wrapper for Disaster Map 3D Visualization.

Provides an interactive 3D globe viewer with live map updates,
timeline navigation, and smooth camera controls.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime
import json
import numpy as np


@dataclass
class CameraPose:
    """3D camera position and orientation."""
    latitude: float = 0.0
    longitude: float = 0.0
    altitude: float = 50000.0  # meters
    heading: float = 0.0       # radians, clockwise from north
    pitch: float = 0.0         # radians, down is positive
    roll: float = 0.0          # radians


@dataclass
class FrameMetadata:
    """Metadata for a single video frame."""
    timestamp: float
    frame_number: int
    pose: Optional[CameraPose] = None
    camera_position: Optional[tuple] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PointCloudData:
    """3D point cloud data for visualization."""
    positions: np.ndarray  # (N, 3) array of [x, y, z] coordinates
    colors: Optional[np.ndarray] = None  # (N, 4) RGBA values
    timestamps: Optional[List[float]] = None  # timestamp per point


class CesiumViewerConfig:
    """Configuration for the Cesium viewer."""
    
    def __init__(
        self,
        initial_latitude: float = 35.0,
        initial_longitude: float = -120.0,
        initial_altitude: float = 50000.0,
        max_zoom_distance: float = 100000.0,
        min_zoom_distance: float = 100.0,
        fps_target: int = 60,
        enable_terrain: bool = True,
        enable_atmosphere: bool = True,
    ):
        self.initial_latitude = initial_latitude
        self.initial_longitude = initial_longitude
        self.initial_altitude = initial_altitude
        self.max_zoom_distance = max_zoom_distance
        self.min_zoom_distance = min_zoom_distance
        self.fps_target = fps_target
        self.enable_terrain = enable_terrain
        self.enable_atmosphere = enable_atmosphere


class CesiumViewer:
    """
    Interactive 3D Globe Viewer using CesiumJS.
    
    Features:
    - Live map updates with point cloud visualization
    - Timeline navigation for frame-by-frame playback
    - Orbit, zoom, and fly-through camera controls
    - Smooth 60 FPS rendering
    
    Example usage:
        viewer = CesiumViewer(config=CesiumViewerConfig())
        
        # Add point cloud data
        points = PointCloudData(
            positions=np.random.rand(10000, 3) * 10000,
            colors=np.random.rand(10000, 4)
        )
        viewer.add_point_cloud(points)
        
        # Set up timeline with frames
        viewer.setup_timeline(frames=[frame1, frame2, ...])
        
        # Start playback
        viewer.start_playback(fps=30)
    """
    
    def __init__(self, config: Optional[CesiumViewerConfig] = None):
        self.config = config or CesiumViewerConfig()
        self._frames: List[FrameMetadata] = []
        self._point_clouds: List[PointCloudData] = []
        self._current_frame_index: int = 0
        self._is_playing: bool = False
        self._playback_rate: float = 1.0
        self._on_camera_change: Optional[Callable[[CameraPose], None]] = None
        self._on_frame_change: Optional[Callable[[int, FrameMetadata], None]] = None
        
        # Simulation state (for headless testing)
        self._simulated_pose: CameraPose = CameraPose()
        self._simulated_position: tuple = (0.0, 0.0, 50000.0)
        
    @property
    def frames(self) -> List[FrameMetadata]:
        """Get all registered frames."""
        return self._frames
    
    @property
    def current_frame_index(self) -> int:
        """Get the currently displayed frame index."""
        return self._current_frame_index
    
    @property
    def is_playing(self) -> bool:
        """Check if playback is active."""
        return self._is_playing
    
    async def initialize(self, token: Optional[str] = None) -> bool:
        """
        Initialize the viewer with CesiumJS.
        
        Args:
            token: Optional Cesium Ion access token for terrain data
            
        Returns:
            True if initialization successful
        """
        # In a real browser environment, this would:
        # 1. Load CesiumJS library
        # 2. Create a Viewer instance
        # 3. Configure camera and base layers
        # 4. Set up event handlers
        
        print(f"[CesiumViewer] Initializing with config:")
        print(f"  - Initial position: ({self.config.initial_latitude}, {self.config.initial_longitude})")
        print(f"  - Altitude: {self.config.initial_altitude}m")
        print(f"  - FPS target: {self.config.fps_target}")
        
        # Simulate successful initialization for headless mode
        self._simulated_pose = CameraPose(
            latitude=self.config.initial_latitude,
            longitude=self.config.initial_longitude,
            altitude=self.config.initial_altitude
        )
        
        return True
    
    def set_camera_position(self, pose: CameraPose) -> None:
        """
        Set the camera position and orientation.
        
        Args:
            pose: Target camera pose with position and rotation
        """
        self._simulated_pose = pose
        
        # Update simulated 3D position (simplified conversion)
        lat_rad = np.radians(pose.latitude)
        lon_rad = np.radians(pose.longitude)
        alt = pose.altitude
        
        x = (alt + 6371000 * np.cos(lat_rad)) * np.cos(lon_rad)
        y = (alt + 6371000 * np.cos(lat_rad)) * np.sin(lon_rad)
        z = alt + 6371000 * np.sin(lat_rad)
        
        self._simulated_position = (x, y, z)
        
        if self._on_camera_change:
            self._on_camera_change(pose)
    
    def get_current_pose(self) -> CameraPose:
        """Get the current camera pose."""
        return self._simulated_pose
    
    def add_point_cloud(
        self, 
        data: PointCloudData, 
        name: Optional[str] = None
    ) -> int:
        """
        Add a 3D point cloud to the visualization.
        
        Args:
            data: Point cloud with positions and optional colors
            name: Optional identifier for the point cloud
            
        Returns:
            Index of added point cloud
        """
        if len(data.positions) == 0:
            raise ValueError("Point cloud must have at least one position")
        
        # Validate coordinates are in reasonable range (global coordinates)
        positions = data.positions.copy()
        if np.any(np.abs(positions) > 1e7):
            print(f"[CesiumViewer] Warning: Large coordinates detected, may need projection")
        
        self._point_clouds.append(PointCloudData(
            positions=positions,
            colors=data.colors,
            timestamps=data.timestamps
        ))
        
        if name is not None:
            # In real implementation, would store with metadata
            pass
        
        print(f"[CesiumViewer] Added point cloud with {len(positions)} points")
        return len(self._point_clouds) - 1
    
    def add_frames(
        self, 
        frames: List[FrameMetadata], 
        pose_callback: Optional[Callable[[int, CameraPose], None]] = None
    ) -> int:
        """
        Register video frames for timeline navigation.
        
        Args:
            frames: List of frame metadata with timestamps and poses
            pose_callback: Optional callback when pose changes
            
        Returns:
            Number of frames added
        """
        self._frames = frames
        
        # Set up pose callbacks if provided
        if pose_callback:
            def wrapped(frame_idx, pose):
                pose_callback(frame_idx, pose)
            
            self._on_camera_change = lambda p: wrapped(self._current_frame_index, p)
        
        print(f"[CesiumViewer] Registered {len(frames)} frames for timeline")
        return len(frames)
    
    def setup_timeline(
        self, 
        frame_interval_ms: float = 100.0,
        auto_play: bool = False
    ) -> None:
        """
        Configure the timeline navigation system.
        
        Args:
            frame_interval_ms: Time interval between frames in milliseconds
            auto_play: Whether to start playback automatically
        """
        self._frame_interval_ms = frame_interval_ms
        
        if auto_play and len(self._frames) > 0:
            self.start_playback(fps=1000.0 / frame_interval_ms)
    
    def get_frame_at_time(self, timestamp: float) -> Optional[FrameMetadata]:
        """Get the frame closest to a given timestamp."""
        if not self._frames:
            return None
        
        # Binary search for closest frame
        left, right = 0, len(self._frames) - 1
        
        while left <= right:
            mid = (left + right) // 2
            if abs(self._frames[mid].timestamp - timestamp) < 0.5:
                return self._frames[mid]
            
            if self._frames[mid].timestamp < timestamp:
                left = mid + 1
            else:
                right = mid - 1
        
        # Return closest frame
        min_diff = float('inf')
        closest = None
        for frame in self._frames:
            diff = abs(frame.timestamp - timestamp)
            if diff < min_diff:
                min_diff = diff
                closest = frame
        
        return closest
    
    def navigate_to_frame(self, frame_index: int) -> Optional[FrameMetadata]:
        """
        Navigate to a specific frame in the timeline.
        
        Args:
            frame_index: Index of frame to navigate to
            
        Returns:
            Frame metadata if successful, None otherwise
        """
        if not self._frames or frame_index < 0 or frame_index >= len(self._frames):
            return None
        
        old_frame = self._frames[self._current_frame_index]
        new_frame = self._frames[frame_index]
        
        # Update current frame
        self._current_frame_index = frame_index
        
        # If pose is available, update camera position
        if new_frame.pose:
            self.set_camera_position(new_frame.pose)
        
        # Notify listeners
        if self._on_frame_change:
            self._on_frame_change(frame_index, new_frame)
        
        print(f"[CesiumViewer] Navigated to frame {frame_index} at t={new_frame.timestamp:.3f}s")
        return new_frame
    
    def start_playback(self, fps: float = 30.0) -> None:
        """
        Start timeline playback.
        
        Args:
            fps: Frames per second for playback speed
        """
        if not self._frames:
            print("[CesiumViewer] No frames to play")
            return
        
        self._is_playing = True
        self._playback_rate = fps / 1000.0  # Convert to seconds per frame
        
        def playback_loop():
            """Main playback loop."""
            if not self._is_playing:
                return
            
            try:
                while self._is_playing and len(self._frames) > 0:
                    next_index = (self._current_frame_index + 1) % len(self._frames)
                    
                    # Update pose from next frame
                    if self._frames[next_index].pose:
                        self.set_camera_position(self._frames[next_index].pose)
                    
                    self._current_frame_index = next_index
                    
                    # Small delay to control playback speed
                    asyncio.sleep(1.0 / fps)
                    
            except Exception as e:
                print(f"[CesiumViewer] Playback error: {e}")
        
        # Start async playback loop
        asyncio.create_task(playback_loop())
    
    def stop_playback(self) -> None:
        """Stop timeline playback."""
        self._is_playing = False
    
    def toggle_playback(self) -> bool:
        """Toggle playback on/off. Returns True if now playing."""
        if self._is_playing:
            self.stop_playback()
        else:
            self.start_playback(fps=1000.0 / self._frame_interval_ms)
        return self._is_playing
    
    def set_playback_rate(self, rate: float) -> None:
        """
        Set playback speed multiplier.
        
        Args:
            rate: Multiplier (e.g., 2.0 for 2x speed, 0.5 for slow motion)
        """
        self._playback_rate = max(0.1, min(10.0, rate))
    
    def fly_through(
        self, 
        start_pose: CameraPose, 
        end_pose: CameraPose, 
        duration_seconds: float = 5.0,
        waypoints: Optional[List[CameraPose]] = None
    ) -> Callable[[], None]:
        """
        Create a smooth camera fly-through animation.
        
        Args:
            start_pose: Starting camera position
            end_pose: Ending camera position
            duration_seconds: Animation duration
            waypoints: Optional intermediate poses
            
        Returns:
            Function to trigger the animation
        """
        def animate():
            """Execute the fly-through animation."""
            num_steps = int(duration_seconds * 60)  # ~60 FPS
            step_time = duration_seconds / num_steps
            
            for i in range(num_steps):
                progress = i / num_steps
                
                if waypoints:
                    # Interpolate through waypoints
                    current_pose = self._interpolate_poses(waypoints, progress)
                else:
                    # Simple linear interpolation
                    current_pose = CameraPose(
                        latitude=start_pose.latitude + (end_pose.latitude - start_pose.latitude) * progress,
                        longitude=start_pose.longitude + (end_pose.longitude - start_pose.longitude) * progress,
                        altitude=start_pose.altitude + (end_pose.altitude - start_pose.altitude) * progress,
                        heading=start_pose.heading + (end_pose.heading - start_pose.heading) * progress,
                        pitch=start_pose.pitch + (end_pose.pitch - start_pose.pitch) * progress,
                        roll=start_pose.roll + (end_pose.roll - start_pose.roll) * progress
                    )
                
                self.set_camera_position(current_pose)
                
                # Simulate animation timing
                asyncio.sleep(step_time)
        
        return animate
    
    def _interpolate_poses(
        self, 
        poses: List[CameraPose], 
        t: float
    ) -> CameraPose:
        """Interpolate between a list of poses."""
        if not poses or len(poses) < 2:
            return poses[0] if poses else CameraPose()
        
        # Find the segment containing t
        total_duration = sum(1 for _ in poses[:-1])  # Simplified duration
        
        current_t = 0.0
        for i in range(len(poses) - 1):
            if current_t + 1 <= t:
                current_t += 1
            else:
                progress = (t - current_t) / (1.0 - current_t) if current_t < 1 else 0
                
                return CameraPose(
                    latitude=poses[i].latitude + (poses[i+1].latitude - poses[i].latitude) * progress,
                    longitude=poses[i].longitude + (poses[i+1].longitude - poses[i].longitude) * progress,
                    altitude=poses[i].altitude + (poses[i+1].altitude - poses[i].altitude) * progress,
                    heading=poses[i].heading + (poses[i+1].heading - poses[i].heading) * progress,
                    pitch=poses[i].pitch + (poses[i+1].pitch - poses[i].pitch) * progress,
                    roll=poses[i].roll + (poses[i+1].roll - poses[i].roll) * progress
                )
        
        return poses[-1]
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics."""
        return {
            "frame_count": len(self._frames),
            "point_cloud_count": len(self._point_clouds),
            "total_points": sum(len(pc.positions) for pc in self._point_clouds),
            "current_frame_index": self._current_frame_index,
            "is_playing": self._is_playing,
            "playback_rate": self._playback_rate,
            "camera_pose": {
                "latitude": self._simulated_pose.latitude,
                "longitude": self._simulated_pose.longitude,
                "altitude": self._simulated_pose.altitude,
            }
        }
    
    def export_state(self) -> Dict[str, Any]:
        """Export current viewer state for serialization."""
        return {
            "frames": [
                {
                    "timestamp": f.timestamp,
                    "frame_number": f.frame_number,
                    "pose": {
                        "latitude": f.pose.latitude if f.pose else None,
                        "longitude": f.pose.longitude if f.pose else None,
                        "altitude": f.pose.altitude if f.pose else None,
                    } if f.pose else None,
                }
                for f in self._frames
            ],
            "point_clouds": [
                {
                    "positions": pc.positions.tolist(),
                    "colors": pc.colors.tolist() if pc.colors is not None else None,
                }
                for pc in self._point_clouds
            ],
            "current_frame_index": self._current_frame_index,
        }
    
    def load_state(self, state: Dict[str, Any]) -> bool:
        """Load a previously exported viewer state."""
        try:
            # Load frames
            if "frames" in state:
                loaded_frames = []
                for frame_data in state["frames"]:
                    pose = None
                    if frame_data.get("pose"):
                        pose = CameraPose(
                            latitude=frame_data["pose"]["latitude"],
                            longitude=frame_data["pose"]["longitude"],
                            altitude=frame_data["pose"]["altitude"]
                        )
                    
                    loaded_frames.append(FrameMetadata(
                        timestamp=frame_data["timestamp"],
                        frame_number=frame_data.get("frame_number", 0),
                        pose=pose
                    ))
                self._frames = loaded_frames
            
            # Load point clouds (simplified - would need proper deserialization)
            if "point_clouds" in state:
                for pc_data in state["point_clouds"]:
                    positions = np.array(pc_data["positions"])
                    colors = None
                    if pc_data.get("colors"):
                        colors = np.array(pc_data["colors"])
                    
                    self.add_point_cloud(
                        PointCloudData(positions=positions, colors=colors)
                    )
            
            # Restore current frame index
            if "current_frame_index" in state:
                self._current_frame_index = state["current_frame_index"]
            
            return True
            
        except Exception as e:
            print(f"[CesiumViewer] Error loading state: {e}")
            return False


# Convenience functions for quick setup
def create_viewer(
    latitude: float = 35.0,
    longitude: float = -120.0,
    altitude: float = 50000.0,
) -> CesiumViewer:
    """Create a configured viewer instance."""
    config = CesiumViewerConfig(
        initial_latitude=latitude,
        initial_longitude=longitude,
        initial_altitude=altitude,
    )
    return CesiumViewer(config=config)


if __name__ == "__main__":
    # Demo usage
    import numpy as np
    
    print("=" * 60)
    print("CesiumViewer Demo")
    print("=" * 60)
    
    # Create viewer
    viewer = create_viewer(latitude=35.0, longitude=-120.0, altitude=50000.0)
    
    # Initialize (simulated)
    asyncio.run(viewer.initialize())
    
    # Add sample point cloud
    np.random.seed(42)
    positions = np.random.randn(10000, 3) * 10000 + [0, 0, 50000]
    colors = np.random.rand(10000, 4)
    
    pc_data = PointCloudData(positions=positions, colors=colors)
    viewer.add_point_cloud(pc_data, name="sample_terrain")
    
    # Create sample frames with camera poses
    frames = []
    for i in range(20):
        pose = CameraPose(
            latitude=35.0 + np.sin(i * 0.5) * 1.0,
            longitude=-120.0 + np.cos(i * 0.5) * 1.0,
            altitude=50000.0 - i * 500,
        )
        frames.append(FrameMetadata(
            timestamp=i * 1.0,
            frame_number=i,
            pose=pose
        ))
    
    viewer.add_frames(frames)
    viewer.setup_timeline(frame_interval_ms=100.0, auto_play=False)
    
    # Show metrics
    print("\nViewer State:")
    metrics = viewer.get_performance_metrics()
    for key, value in metrics.items():
        if isinstance(value, dict):
            print(f"  {key}: {value}")
        else:
            print(f"  {key}: {value}")
    
    # Export state
    state = viewer.export_state()
    print(f"\nExported state with {len(state['frames'])} frames and "
          f"{state['point_clouds'][0]['positions'].shape[0]} points")
    
    print("\nDemo complete!")
