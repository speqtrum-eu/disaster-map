"""
Camera Controls for 3D Visualization.

Provides orbit, zoom, pan, and fly-through camera controls with smooth
interpolation and user interaction support.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable, Awaitable
from datetime import datetime
import numpy as np


@dataclass
class CameraPose:
    """3D camera position and orientation."""
    latitude: float = 0.0
    longitude: float = 0.0
    altitude: float = 50000.0  # meters above surface
    
    heading: float = 0.0       # radians, clockwise from north
    pitch: float = 0.0         # radians, down is positive
    roll: float = 0.0          # radians
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert pose to dictionary."""
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "altitude": self.altitude,
            "heading": self.heading,
            "pitch": self.pitch,
            "roll": self.roll,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CameraPose":
        """Create pose from dictionary."""
        return cls(
            latitude=data.get("latitude", 0.0),
            longitude=data.get("longitude", 0.0),
            altitude=data.get("altitude", 50000.0),
            heading=data.get("heading", 0.0),
            pitch=data.get("pitch", 0.0),
            roll=data.get("roll", 0.0),
        )


@dataclass
class CameraConfig:
    """Configuration for camera controls."""
    # Zoom limits
    min_altitude: float = 100.0
    max_altitude: float = 1e7
    
    # Rotation limits
    min_heading: float = -np.pi
    max_heading: float = np.pi
    min_pitch: float = -np.pi / 2 + 0.1
    max_pitch: float = np.pi / 2 - 0.1
    
    # Smoothness settings
    smooth_zoom: bool = True
    smooth_rotation: bool = True
    zoom_speed: float = 50.0
    rotation_speed: float = 1.0
    
    # Interaction settings
    enable_orbit: bool = True
    enable_zoom: bool = True
    enable_pan: bool = True
    enable_fly_through: bool = True
    
    # Animation settings
    animation_easing: str = "ease_out"  # ease_in, ease_out, linear, ease_in_out


@dataclass
class OrbitState:
    """State for orbit camera controls."""
    center_latitude: float = 0.0
    center_longitude: float = 0.0
    radius: float = 50000.0
    
    # Rotation state
    is_rotating: bool = False
    rotation_speed: float = 1.0
    target_heading: float = 0.0
    current_heading: float = 0.0
    
    # Zoom state
    zoom_delta: float = 0.0
    target_radius: float = 50000.0


@dataclass
class FlyThroughState:
    """State for fly-through animations."""
    is_flying: bool = False
    start_pose: Optional[CameraPose] = None
    end_pose: Optional[CameraPose] = None
    
    # Waypoints for complex paths
    waypoints: List[CameraPose] = field(default_factory=list)
    
    # Animation state
    progress: float = 0.0
    current_pose: Optional[CameraPose] = None
    animation_speed: float = 1.0


class CameraControls:
    """
    Interactive camera controls for 3D visualization.
    
    Features:
    - Orbit around a center point with smooth rotation
    - Zoom in/out with configurable limits
    - Pan across the globe surface
    - Fly-through animations between poses
    - Keyboard and mouse interaction support
    
    Example usage:
        controls = CameraControls(config=CameraConfig())
        
        # Set initial position
        controls.set_position(CameraPose(latitude=35, longitude=-120))
        
        # Start orbiting
        controls.start_orbit(rotation_speed=1.0)
        
        # Create fly-through animation
        # animate_func = controls.fly_through(start_pose, end_pose, duration=5)
    """
    
    def __init__(self, config: Optional[CameraConfig] = None):
        """
        Initialize camera controls.
        
        Args:
            config: Camera configuration options
        """
        self.config = config or CameraConfig()
        
        # Current pose
        self._pose = CameraPose()
        
        # Orbit state
        self.orbit_state = OrbitState()
        
        # Fly-through state
        self.fly_through_state = FlyThroughState()
        
        # Animation state
        self._is_animating: bool = False
        self._animation_type: str = ""
        self._interpolation_progress: float = 0.0
        
        # Callbacks
        self._on_pose_change: Optional[Callable[[CameraPose], Awaitable[None]]] = None
        self._on_animation_start: Optional[Callable[[], Awaitable[None]]] = None
        self._on_animation_end: Optional[Callable[[], Awaitable[None]]] = None
        
        # Timing control
        self._animation_timer: Optional[asyncio.Task] = None
        self._delta_time: float = 1.0 / 60.0  # ~60 FPS
        
    @property
    def pose(self) -> CameraPose:
        """Get the current camera pose."""
        return self._pose
    
    @property
    def is_animating(self) -> bool:
        """Check if an animation is in progress."""
        return self._is_animating
    
    async def initialize(self) -> bool:
        """Initialize camera controls."""
        print(f"[CameraControls] Initialized with config:")
        print(f"  - Min altitude: {self.config.min_altitude}")
        print(f"  - Max altitude: {self.config.max_altitude}")
        print(f"  - Smooth zoom: {self.config.smooth_zoom}")
        
        return True
    
    def set_position(self, pose: CameraPose) -> None:
        """Set the camera position."""
        self._pose = pose
        
        # Clamp altitude to configured limits
        if pose.altitude < self.config.min_altitude:
            pose.altitude = self.config.min_altitude
        elif pose.altitude > self.config.max_altitude:
            pose.altitude = self.config.max_altitude
        
        print(f"[CameraControls] Position set to ({pose.latitude:.4f}, {pose.longitude:.4f}, "
              f"{pose.altitude:.0f}m)")
    
    def get_position(self) -> CameraPose:
        """Get the current camera position."""
        return self._pose
    
    async def orbit(
        self, 
        center_latitude: float = 0.0,
        center_longitude: float = 0.0,
        radius: float = 50000.0,
        rotation_speed: float = 1.0,
    ) -> None:
        """
        Start orbiting around a center point.
        
        Args:
            center_latitude: Center latitude in degrees
            center_longitude: Center longitude in degrees
            radius: Orbit radius in meters
            rotation_speed: Rotation speed multiplier
        """
        self.orbit_state.center_latitude = center_latitude
        self.orbit_state.center_longitude = center_longitude
        self.orbit_state.radius = max(self.config.min_altitude, min(radius, self.config.max_altitude))
        self.orbit_state.rotation_speed = rotation_speed
        
        print(f"[CameraControls] Starting orbit at ({center_latitude}, {center_longitude}) "
              f"with radius {radius:.0f}m")
    
    async def zoom(self, delta: float) -> None:
        """
        Zoom in/out by a delta amount.
        
        Args:
            delta: Positive to zoom out (increase altitude), negative to zoom in
            
        Example:
            # Zoom in by 10%
            await controls.zoom(-0.1)
            
            # Zoom out by 20%
            await controls.zoom(0.2)
        """
        if not self.config.enable_zoom:
            return
        
        current_altitude = self._pose.altitude
        new_altitude = current_altitude * (1 + delta)
        
        # Clamp to limits
        new_altitude = max(self.config.min_altitude, min(new_altitude, self.config.max_altitude))
        
        if abs(delta) < 0.001:
            return
        
        self._pose.altitude = new_altitude
        
        print(f"[CameraControls] Zoomed from {current_altitude:.0f}m to {new_altitude:.0f}m")
    
    async def pan(
        self, 
        latitude_delta: float = 0.0,
        longitude_delta: float = 0.0,
    ) -> None:
        """
        Pan the camera across the globe surface.
        
        Args:
            latitude_delta: Change in latitude (degrees)
            longitude_delta: Change in longitude (degrees)
        """
        if not self.config.enable_pan:
            return
        
        new_latitude = np.clip(self._pose.latitude + latitude_delta, -90, 90)
        new_longitude = np.clip(self._pose.longitude + longitude_delta, -180, 180)
        
        # Normalize longitude to [-180, 180]
        while new_longitude > 180:
            new_longitude -= 360
        while new_longitude < -180:
            new_longitude += 360
        
        self._pose.latitude = new_latitude
        self._pose.longitude = new_longitude
        
        print(f"[CameraControls] Panned to ({new_latitude:.4f}, {new_longitude:.4f})")
    
    async def rotate(
        self, 
        heading_delta: float = 0.0,
        pitch_delta: float = 0.0,
        roll_delta: float = 0.0,
    ) -> None:
        """
        Rotate the camera orientation.
        
        Args:
            heading_delta: Change in heading (radians)
            pitch_delta: Change in pitch (radians)
            roll_delta: Change in roll (radians)
        """
        if not self.config.enable_pan:
            return
        
        new_heading = np.clip(
            self._pose.heading + heading_delta, 
            self.config.min_heading, 
            self.config.max_heading
        )
        
        new_pitch = np.clip(
            self._pose.pitch + pitch_delta,
            self.config.min_pitch,
            self.config.max_pitch
        )
        
        # Roll typically stays small for camera controls
        new_roll = np.clip(self._pose.roll + roll_delta, -0.5, 0.5)
        
        self._pose.heading = new_heading
        self._pose.pitch = new_pitch
        self._pose.roll = new_roll
        
        print(f"[CameraControls] Rotated (heading={new_heading:.2f}, pitch={new_pitch:.2f})")
    
    def fly_through(
        self,
        start_pose: CameraPose,
        end_pose: CameraPose,
        duration_seconds: float = 5.0,
        easing: str = "ease_out",
    ) -> Callable[[], None]:
        """
        Create a smooth fly-through animation between two poses.
        
        Args:
            start_pose: Starting camera position
            end_pose: Ending camera position
            duration_seconds: Animation duration
            easing: Easing function for smoothness
            
        Returns:
            Async function to trigger the animation (await to execute)
            
        Example:
            animate_func = controls.fly_through(start, end, 5.0)
            await animate_func()  # Execute the animation
        """
        async def animate():
            """Execute the fly-through animation."""
            num_steps = int(duration_seconds * 60)  # ~60 FPS
            step_time = duration_seconds / num_steps
            
            self._is_animating = True
            self._animation_type = "fly_through"
            
            if self._on_animation_start:
                asyncio.create_task(self._on_animation_start())
            
            try:
                for i in range(num_steps):
                    progress = i / num_steps
                    
                    # Apply easing function
                    eased_progress = self._apply_easing(progress, easing)
                    
                    # Interpolate pose
                    current_pose = CameraPose(
                        latitude=self._interpolate(start_pose.latitude, end_pose.latitude, eased_progress),
                        longitude=self._interpolate(start_pose.longitude, end_pose.longitude, eased_progress),
                        altitude=self._interpolate(start_pose.altitude, end_pose.altitude, eased_progress),
                        heading=self._interpolate(start_pose.heading, end_pose.heading, eased_progress),
                        pitch=self._interpolate(start_pose.pitch, end_pose.pitch, eased_progress),
                        roll=self._interpolate(start_pose.roll, end_pose.roll, eased_progress),
                    )
                    
                    # Update current pose
                    self.set_position(current_pose)
                    
                    # Notify listeners
                    if self._on_pose_change:
                        asyncio.create_task(self._on_pose_change(current_pose))
                    
                    await asyncio.sleep(step_time / self.fly_through_state.animation_speed)
                
            finally:
                self._is_animating = False
                self._animation_type = ""
                
                if self._on_animation_end:
                    asyncio.create_task(self._on_animation_end())
        
        return animate
    
    def _apply_easing(self, t: float, easing: str) -> float:
        """Apply an easing function to animation progress."""
        if easing == "linear":
            return t
        
        elif easing == "ease_in":
            return t * t
        
        elif easing == "ease_out":
            return 1 - (1 - t) * (1 - t)
        
        elif easing == "ease_in_out":
            if t < 0.5:
                return 2 * t * t
            else:
                return 1 - (-2 * t + 4) * (-2 * t + 4) / 8
        
        return t
    
    def _interpolate(self, start: float, end: float, t: float) -> float:
        """Linear interpolation between two values."""
        return start + (end - start) * t
    
    async def waypoint_fly_through(
        self,
        waypoints: List[CameraPose],
        duration_seconds: float = 10.0,
    ) -> None:
        """
        Fly through a series of waypoints with smooth transitions.
        
        Args:
            waypoints: List of camera poses to visit in order
            duration_seconds: Total animation duration
        """
        if not waypoints or len(waypoints) < 2:
            print("[CameraControls] Need at least 2 waypoints for fly-through")
            return
        
        self.fly_through_state.waypoints = waypoints
        self.fly_through_state.is_flying = True
        self._is_animating = True
        self._animation_type = "waypoint_path"
        
        total_duration = duration_seconds
        num_waypoints = len(waypoints)
        time_per_waypoint = total_duration / (num_waypoints - 1)
        
        print(f"[CameraControls] Starting waypoint fly-through with {num_waypoints} waypoints")
        
        try:
            for i, pose in enumerate(waypoints):
                # Fly to this waypoint
                await self.fly_through(
                    start_pose=self.fly_through_state.current_pose or pose,
                    end_pose=pose,
                    duration_seconds=time_per_waypoint,
                )
                
                print(f"[CameraControls] Arrived at waypoint {i+1}/{num_waypoints}")
            
        finally:
            self._is_animating = False
            self.fly_through_state.is_flying = False
    
    async def smooth_transition(
        self,
        target_pose: CameraPose,
        transition_time: float = 2.0,
    ) -> None:
        """
        Smoothly transition to a target pose over time.
        
        Args:
            target_pose: Target camera position
            transition_time: Time for smooth transition (seconds)
        """
        if not self.config.smooth_zoom or not self.config.smooth_rotation:
            # Direct jump if smoothing disabled
            self.set_position(target_pose)
            return
        
        async def smooth_transition():
            num_steps = int(transition_time * 60)
            step_time = transition_time / num_steps
            
            for i in range(num_steps):
                progress = i / num_steps
                
                # Smoothly interpolate altitude (zoom)
                current_altitude = self._pose.altitude
                target_altitude = target_pose.altitude
                
                if self.config.smooth_zoom:
                    eased_progress = self._apply_easing(progress, "ease_out")
                    new_altitude = current_altitude + (target_altitude - current_altitude) * eased_progress
                    
                    # Clamp to limits
                    new_altitude = max(self.config.min_altitude, min(new_altitude, self.config.max_altitude))
                    
                    if abs(target_altitude - current_altitude) > 1:
                        self._pose.altitude = new_altitude
                
                # Smoothly interpolate heading (rotation)
                if self.config.smooth_rotation and i % 3 == 0:  # Throttle rotation updates
                    current_heading = self._pose.heading
                    target_heading = target_pose.heading
                    
                    # Normalize angle difference to [-pi, pi]
                    diff = np.arctan2(np.sin(target_heading - current_heading), 
                                     np.cos(target_heading - current_heading))
                    
                    eased_rotation = self._apply_easing(progress, "ease_out")
                    new_heading = current_heading + diff * eased_rotation
                    
                    if abs(diff) > 0.1:
                        self._pose.heading = new_heading
                
                await asyncio.sleep(step_time)
        
        asyncio.create_task(smooth_transition())
    
    async def reset_view(
        self,
        latitude: float = 35.0,
        longitude: float = -120.0,
        altitude: float = 50000.0,
    ) -> None:
        """Reset camera to a default view."""
        pose = CameraPose(latitude=latitude, longitude=longitude, altitude=altitude)
        self.set_position(pose)
        
        # Reset orbit state
        self.orbit_state.center_latitude = latitude
        self.orbit_state.center_longitude = longitude
        
        print(f"[CameraControls] View reset to ({latitude}, {longitude}, {altitude})")
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current camera performance metrics."""
        return {
            "pose": self._pose.to_dict(),
            "is_animating": self._is_animating,
            "animation_type": self._animation_type,
            "orbit_state": {
                "center": (self.orbit_state.center_latitude, self.orbit_state.center_longitude),
                "radius": self.orbit_state.radius,
                "rotation_speed": self.orbit_state.rotation_speed,
            },
            "fly_through_state": {
                "is_flying": self.fly_through_state.is_flying,
                "waypoint_count": len(self.fly_through_state.waypoints),
            }
        }
    
    def export_pose(self) -> Dict[str, Any]:
        """Export current pose for serialization."""
        return {
            "pose": self._pose.to_dict(),
            "orbit_center": (self.orbit_state.center_latitude, self.orbit_state.center_longitude),
            "orbit_radius": self.orbit_state.radius,
        }
    
    def load_pose(self, data: Dict[str, Any]) -> bool:
        """Load a previously exported pose."""
        try:
            if "pose" in data:
                pose_data = data["pose"]
                self._pose = CameraPose.from_dict(pose_data)
            
            if "orbit_center" in data:
                center = data["orbit_center"]
                self.orbit_state.center_latitude = center[0]
                self.orbit_state.center_longitude = center[1]
            
            return True
            
        except Exception as e:
            print(f"[CameraControls] Error loading pose: {e}")
            return False


# Keyboard input handler for camera controls

class CameraInputHandler:
    """Handle keyboard and mouse input for camera controls."""
    
    def __init__(self, controls: CameraControls):
        self.controls = controls
    
    async def on_key_press(self, key: str) -> None:
        """Handle a keyboard press event."""
        # Zoom shortcuts
        if key == "+":
            await self.controls.zoom(-0.1)  # Zoom in (decrease altitude)
        elif key == "-":
            await self.controls.zoom(0.1)   # Zoom out (increase altitude)
        
        # Pan shortcuts
        elif key == "w":
            await self.controls.pan(latitude_delta=0.5)
        elif key == "s":
            await self.controls.pan(latitude_delta=-0.5)
        elif key == "a":
            await self.controls.pan(longitude_delta=-0.5)
        elif key == "d":
            await self.controls.pan(longitude_delta=0.5)
        
        # Reset view
        elif key == "r":
            await self.controls.reset_view()


# Convenience functions

def create_camera_controls(config: Optional[CameraConfig] = None) -> CameraControls:
    """Create a configured camera controls instance."""
    return CameraControls(config=config)


if __name__ == "__main__":
    print("=" * 60)
    print("Camera Controls Demo")
    print("=" * 60)
    
    # Create camera controls
    config = CameraConfig(
        min_altitude=100.0,
        max_altitude=1e7,
        smooth_zoom=True,
        smooth_rotation=True,
    )
    controls = create_camera_controls(config)
    
    async def demo():
        await controls.initialize()
        
        # Set initial position
        start_pose = CameraPose(latitude=35.0, longitude=-120.0, altitude=50000.0)
        controls.set_position(start_pose)
        
        print(f"\nInitial pose: {controls.pose.to_dict()}")
        
        # Test zoom
        print("\nTesting zoom:")
        await controls.zoom(-0.3)  # Zoom in
        await controls.zoom(0.5)   # Zoom out
        
        # Test pan
        print("\nTesting pan:")
        await controls.pan(latitude_delta=1.0, longitude_delta=-2.0)
        
        # Test rotation
        print("\nTesting rotation:")
        await controls.rotate(heading_delta=np.pi / 4, pitch_delta=0.1)
        
        # Test fly-through animation
        print("\nTesting fly-through animation:")
        end_pose = CameraPose(latitude=36.0, longitude=-121.0, altitude=45000.0)
        
        animate_func = controls.fly_through(start_pose, end_pose, duration_seconds=3.0)
        print(f"Animation function created: {animate_func}")
        
        # Test waypoint fly-through
        print("\nTesting waypoint fly-through:")
        waypoints = [
            CameraPose(latitude=35.0 + i * 0.1, longitude=-120.0 - i * 0.1, altitude=50000 - i * 1000)
            for i in range(5)
        ]
        
        print(f"Waypoints: {len(waypoints)}")
        
        # Test smooth transition
        print("\nTesting smooth transition:")
        target_pose = CameraPose(latitude=37.0, longitude=-122.0, altitude=40000.0)
        await controls.smooth_transition(target_pose, transition_time=2.0)
        
        # Show metrics
        print("\nPerformance metrics:")
        metrics = controls.get_performance_metrics()
        for key, value in metrics.items():
            if isinstance(value, dict):
                print(f"  {key}: {value}")
            else:
                print(f"  {key}: {value}")
        
        # Export pose
        print("\nExported pose:")
        exported = controls.export_pose()
        for key, value in exported.items():
            if isinstance(value, tuple):
                print(f"  {key}: ({value[0]:.4f}, {value[1]:.4f})")
            else:
                print(f"  {key}: {value}")
    
    asyncio.run(demo())
    
    print("\nDemo complete!")
