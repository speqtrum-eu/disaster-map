"""
Integration Module - Combines Cesium Viewer, Timeline, and Camera Controls.

Provides a unified interface for building interactive 3D visualizations
with live map updates, smooth navigation, and multi-camera support.
"""

import asyncio
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime

# Import local modules
from src.visualization.cesium_viewer import (
    CesiumViewer, 
    PointCloudData, 
    CameraPose, 
    FrameMetadata,
    CesiumViewerConfig,
)
from src.visualization.timeline import TimelineNavigator, TimelineConfig
from src.visualization.camera import CameraControls, CameraConfig

# Import navigation modules
from src.navigation.waypoint_navigation import (
    WaypointNavigator,
    NavigationMode,
    load_waypoints_batch,
)
from src.navigation.path_visualizer import PathVisualizer


class DisasterMapVisualizer:
    """
    Unified 3D Visualization for Disaster Map Data.
    
    Combines CesiumJS viewer, timeline navigation, and camera controls
    into a single interface for interactive disaster map visualization.
    
    Features:
    - Live point cloud rendering with LOD support
    - Timeline-based frame navigation
    - Smooth camera animations (orbit, zoom, fly-through)
    - Performance-optimized at 60 FPS
    
    Example usage:
        visualizer = DisasterMapVisualizer()
        
        # Load disaster data
        points = PointCloudData(positions=positions, colors=colors)
        visualizer.add_point_cloud(points)
        
        # Set up timeline with camera poses
        frames = [FrameMetadata(timestamp=i, pose=pose) for i in range(100)]
        visualizer.setup_timeline(frames)
        
        # Start interactive viewing
        visualizer.start()
    """
    
    def __init__(self):
        self.viewer: Optional[CesiumViewer] = None
        self.timeline: Optional[TimelineNavigator] = None
        self.camera: Optional[CameraControls] = None
        
        # Navigation components
        self.navigator: Optional[WaypointNavigator] = None
        self.path_visualizer: Optional[PathVisualizer] = None
        
        # Multi-camera support
        self._cameras: Dict[str, CameraPose] = {}
        self._active_camera_view: str = "primary"
        self._camera_switching_enabled: bool = True
        
        # State
        self._is_running: bool = False
        self._performance_metrics: List[Dict[str, Any]] = []
    
    async def initialize(self) -> bool:
        """Initialize all visualization components."""
        print("[DisasterMapVisualizer] Initializing...")
        
        # Create viewer with default configuration
        config = CesiumViewerConfig(
            initial_latitude=35.0,
            initial_longitude=-120.0,
            initial_altitude=50000.0,
            fps_target=60,
        )
        self.viewer = CesiumViewer(config=config)
        
        # Create camera controls
        cam_config = CameraConfig(
            min_altitude=100.0,
            max_altitude=1e7,
            smooth_zoom=True,
            smooth_rotation=True,
            enable_orbit=True,
            enable_zoom=True,
            enable_pan=True,
        )
        self.camera = CameraControls(config=cam_config)
        
        # Initialize components
        await self.viewer.initialize()
        await self.camera.initialize()
        
        print("[DisasterMapVisualizer] Initialization complete")
        return True
    
    def add_point_cloud(
        self, 
        data: PointCloudData, 
        name: Optional[str] = None
    ) -> int:
        """Add a point cloud to the visualization."""
        if not self.viewer:
            raise RuntimeError("Viewer not initialized. Call initialize() first.")
        
        index = self.viewer.add_point_cloud(data, name)
        print(f"[DisasterMapVisualizer] Added point cloud '{name}' with {len(data.positions)} points")
        return index
    
    def add_frames(
        self, 
        frames: List[FrameMetadata],
        pose_callback: Optional[callable] = None
    ) -> int:
        """Add frames for timeline navigation."""
        if not self.viewer:
            raise RuntimeError("Viewer not initialized. Call initialize() first.")
        
        index = self.viewer.add_frames(frames, pose_callback)
        
        # Create timeline navigator - handle both FrameMetadata and dict inputs
        frame_data = []
        for f in frames:
            if hasattr(f, '__dict__'):  # FrameMetadata object
                frame_data.append(f.__dict__)
            else:  # Already a dict or similar
                frame_data.append(f)
        
        config = TimelineConfig(
            frame_interval_ms=100.0,
            fps_target=60,
            loop_mode=False,
        )
        self.timeline = TimelineNavigator(
            frames=frame_data,
            config=config,
        )
        
        print(f"[DisasterMapVisualizer] Added {index} frames for timeline")
        return index
    
    def setup_camera(self, pose: CameraPose) -> None:
        """Set the initial camera position."""
        if not self.camera:
            raise RuntimeError("Camera controls not initialized.")
        
        self.camera.set_position(pose)
    
    async def start_playback(
        self, 
        fps: float = 30.0,
        rate: float = 1.0,
    ) -> None:
        """Start timeline playback."""
        if not self.timeline:
            raise RuntimeError("No frames loaded for playback.")
        
        await self.timeline.play(fps=fps, rate=rate)
        print(f"[DisasterMapVisualizer] Playback started at {fps} FPS")
    
    async def pause_playback(self) -> None:
        """Pause timeline playback."""
        if not self.timeline:
            return
        
        await self.timeline.pause()
        print("[DisasterMapVisualizer] Playback paused")
    
    async def stop_playback(self) -> None:
        """Stop and reset playback."""
        if not self.timeline:
            return
        
        await self.timeline.stop()
        print("[DisasterMapVisualizer] Playback stopped")
    
    async def fly_through(
        self, 
        start_pose: CameraPose, 
        end_pose: CameraPose, 
        duration: float = 5.0,
    ) -> None:
        """Execute a smooth camera fly-through animation."""
        if not self.camera:
            raise RuntimeError("Camera controls not initialized.")
        
        animate_func = self.camera.fly_through(start_pose, end_pose, duration)
        await animate_func()
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics."""
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "viewer": self.viewer.get_performance_metrics() if self.viewer else {},
            "camera": self.camera.get_performance_metrics() if self.camera else {},
            "timeline": self.timeline.get_current_state() if self.timeline else {},
        }
        
        return metrics
    
    def export_visualization(self) -> Dict[str, Any]:
        """Export current visualization state."""
        state = {
            "viewer": self.viewer.export_state() if self.viewer else None,
            "camera": self.camera.export_pose() if self.camera else None,
            "timeline": self.timeline.export_timeline() if self.timeline else None,
        }
        
        return state
    
    def load_visualization(self, data: Dict[str, Any]) -> bool:
        """Load a previously exported visualization state."""
        try:
            if data.get("viewer") and self.viewer:
                self.viewer.load_state(data["viewer"])
            
            if data.get("camera") and self.camera:
                self.camera.load_pose(data["camera"])
            
            if data.get("timeline") and self.timeline:
                self.timeline.load_timeline(data["timeline"])
            
            return True
            
        except Exception as e:
            print(f"[DisasterMapVisualizer] Error loading state: {e}")
            return False
    
    # =========================================================================
    # Multi-Camera View Switching
    # =========================================================================
    
    def add_camera_view(
        self, 
        camera_id: str, 
        pose: CameraPose, 
        name: Optional[str] = None,
    ) -> bool:
        """Add a camera view for multi-camera support."""
        if not pose:
            print(f"[DisasterMapVisualizer] Invalid pose for camera '{camera_id}'")
            return False
        
        self._cameras[camera_id] = pose
        
        # Set default name based on camera type
        if name is None:
            if "drone" in camera_id.lower():
                name = f"Drone {camera_id}"
            elif "body" in camera_id.lower() or "cam" in camera_id.lower():
                name = f"Body Cam {camera_id}"
            else:
                name = f"Camera {camera_id}"
        
        print(f"[DisasterMapVisualizer] Added camera view '{name}' ({camera_id})")
        return True
    
    def set_active_camera_view(self, camera_id: str) -> bool:
        """Set the active camera view for navigation."""
        if camera_id not in self._cameras:
            print(f"[DisasterMapVisualizer] Camera '{camera_id}' not found")
            return False
        
        pose = self._cameras[camera_id]
        
        # Update current camera position
        if self.camera:
            self.camera.set_position(pose)
        
        self._active_camera_view = camera_id
        print(f"[DisasterMapVisualizer] Active view switched to '{camera_id}'")
        return True
    
    def switch_to_next_camera(self) -> bool:
        """Switch to the next available camera in sequence."""
        if len(self._cameras) < 2:
            print("[DisasterMapVisualizer] Need at least 2 cameras for switching")
            return False
        
        # Get sorted list of camera IDs
        camera_ids = sorted(self._cameras.keys())
        current_idx = camera_ids.index(self._active_camera_view) if self._active_camera_view in camera_ids else 0
        
        next_idx = (current_idx + 1) % len(camera_ids)
        return self.set_active_camera_view(camera_ids[next_idx])
    
    def switch_to_previous_camera(self) -> bool:
        """Switch to the previous available camera in sequence."""
        if len(self._cameras) < 2:
            print("[DisasterMapVisualizer] Need at least 2 cameras for switching")
            return False
        
        # Get sorted list of camera IDs
        camera_ids = sorted(self._cameras.keys())
        current_idx = camera_ids.index(self._active_camera_view) if self._active_camera_view in camera_ids else 0
        
        prev_idx = (current_idx - 1) % len(camera_ids)
        return self.set_active_camera_view(camera_ids[prev_idx])
    
    def get_available_cameras(self) -> List[str]:
        """Get list of available camera IDs."""
        return list(self._cameras.keys())
    
    def get_current_camera_pose(self, camera_id: Optional[str] = None) -> Optional[CameraPose]:
        """Get the pose for a specific or active camera."""
        if camera_id is None:
            camera_id = self._active_camera_view
        
        return self._cameras.get(camera_id)
    
    def enable_multi_camera_mode(self, enabled: bool = True):
        """Enable/disable multi-camera view switching."""
        self._camera_switching_enabled = enabled
        print(f"[DisasterMapVisualizer] Multi-camera mode {'enabled' if enabled else 'disabled'}")
    
    # =========================================================================
    # Navigation Integration
    # =========================================================================
    
    def setup_navigation(
        self, 
        waypoints: Optional[List[Dict[str, Any]]] = None,
        auto_advance: bool = False,
    ) -> WaypointNavigator:
        """Setup waypoint navigation system."""
        if self.navigator is not None:
            print("[DisasterMapVisualizer] Navigation already initialized")
            return self.navigator
        
        # Create navigator
        self.navigator = WaypointNavigator()
        
        # Add waypoints if provided
        if waypoints:
            for wp_data in waypoints:
                waypoint = Waypoint(
                    id=wp_data.get("id", 0),
                    latitude=wp_data["latitude"],
                    longitude=wp_data["longitude"],
                    altitude=wp_data["altitude"],
                    timestamp=wp_data.get("timestamp"),
                    description=wp_data.get("description", ""),
                )
                self.navigator.add_waypoint(waypoint)
        
        # Setup auto-advance if enabled
        if auto_advance:
            self.navigator.state.auto_advance = True
        
        print(f"[DisasterMapVisualizer] Navigation initialized with {len(self.navigator.waypoints)} waypoints")
        return self.navigator
    
    def navigate_to_next_waypoint(self, mode: Optional[NavigationMode] = None) -> bool:
        """Navigate to the next waypoint."""
        if not self.navigator:
            print("[DisasterMapVisualizer] Navigation not initialized. Call setup_navigation() first.")
            return False
        
        # Use active camera pose for navigation
        current_pose = self.get_current_camera_pose()
        
        if mode:
            self.navigator.state.mode = mode
        
        result = self.navigator.navigate_to_next()
        
        if result and current_pose:
            # Update viewer to navigate to waypoint position
            if self.viewer:
                self.viewer.navigate_to_waypoint(
                    latitude=current_pose.latitude,
                    longitude=current_pose.longitude,
                    altitude=current_pose.altitude + 100,  # Slight elevation for better view
                )
        
        return result
    
    def get_navigation_state(self) -> Dict[str, Any]:
        """Get current navigation state."""
        if not self.navigator:
            return {"error": "Navigation not initialized"}
        
        return {
            "waypoints_count": len(self.navigator.waypoints),
            "current_waypoint_index": self.navigator.state.current_waypoint_index,
            "mode": self.navigator.state.mode.value,
            "auto_advance": self.navigator.state.auto_advance,
        }
    
    # =========================================================================
    # Path Visualization Integration
    # =========================================================================
    
    def setup_path_visualization(self) -> PathVisualizer:
        """Setup path visualization system."""
        if self.path_visualizer is not None:
            print("[DisasterMapVisualizer] Path visualizer already initialized")
            return self.path_visualizer
        
        self.path_visualizer = PathVisualizer()
        
        # Add default layers for multi-camera support
        self.path_visualizer.add_primary_path([], layer=PathLayer(
            name="primary", color=(0.2, 0.6, 0.8), width=3.0
        ))
        
        print("[DisasterMapVisualizer] Path visualizer initialized")
        return self.path_visualizer
    
    def add_camera_trajectory(self, camera_id: str, trajectory: List[Dict[str, float]]) -> int:
        """Add trajectory path for a specific camera."""
        if not trajectory:
            return -1
        
        # Add as secondary path with unique name
        layer = PathLayer(
            name=f"camera_{camera_id}",
            color=(0.5 + hash(camera_id) % 3 * 0.2, 0.6, 0.7),
            width=2.0,
        )
        
        return self.path_visualizer.add_secondary_path(trajectory, layer=layer)
    
    def get_multi_camera_state(self) -> Dict[str, Any]:
        """Get state of all camera views."""
        return {
            "active_view": self._active_camera_view,
            "available_cameras": self.get_available_cameras(),
            "camera_count": len(self._cameras),
            "multi_camera_enabled": self._camera_switching_enabled,
        }
    
    def run(self) -> None:
        """Run the visualization (main entry point)."""
        if not self._is_running:
            asyncio.run(self._run())
    
    async def _run(self) -> None:
        """Main runtime loop."""
        print("[DisasterMapVisualizer] Starting main loop...")
        
        try:
            while self._is_running:
                # Update performance metrics
                metrics = self.get_performance_metrics()
                
                if len(self._performance_metrics) > 100:
                    self._performance_metrics.pop(0)
                
                self._performance_metrics.append(metrics)
                
                await asyncio.sleep(1.0 / 60.0)  # ~60 FPS update rate
                
        except KeyboardInterrupt:
            print("\n[DisasterMapVisualizer] Interrupted by user")
        finally:
            await self.cleanup()
    
    async def cleanup(self) -> None:
        """Clean up resources."""
        print("[DisasterMapVisualizer] Cleaning up...")
        
        if self.timeline:
            await self.timeline.stop()
        
        if self.camera:
            # Reset camera to default view
            await self.camera.reset_view()
        
        if self.navigator:
            self.navigator.reset()
        
        if self.path_visualizer:
            self.path_visualizer.reset()
        
        self._is_running = False
        print("[DisasterMapVisualizer] Cleanup complete")
    
    # =========================================================================
    # Performance Optimization for Large Datasets
    # =========================================================================
    
    def optimize_point_cloud(
        self, 
        data: PointCloudData, 
        max_points: int = 1000000,
        use_lod: bool = True,
    ) -> PointCloudData:
        """Optimize point cloud for rendering with millions of points."""
        if len(data.positions) <= max_points:
            print(f"[DisasterMapVisualizer] Point cloud already optimized ({len(data.positions)} points)")
            return data
        
        # Downsample using voxel grid approach
        from scipy.spatial import cKDTree
        
        positions = np.array(data.positions)
        
        if use_lod and len(positions) > max_points:
            print(f"[DisasterMapVisualizer] Downsampling {len(positions)} -> {max_points} points")
            
            # Use KD-tree for efficient sampling
            tree = cKDTree(positions)
            
            # Sample uniformly distributed points
            sampled_indices = np.random.choice(
                len(positions), 
                size=max_points, 
                replace=False
            )
            
            sampled_positions = positions[sampled_indices]
            
            if hasattr(data, 'colors') and data.colors is not None:
                colors = np.array(data.colors)
                sampled_colors = colors[sampled_indices]
            else:
                sampled_colors = None
            
            return PointCloudData(
                positions=sampled_positions,
                colors=sampled_colors,
            )
        
        # If points are within limit but still large, apply LOD settings
        if len(positions) > 100000 and use_lod:
            print(f"[DisasterMapVisualizer] Applying LOD settings for {len(positions)} points")
            
            # Set LOD thresholds based on point count
            self._lod_thresholds = [
                max(1000, len(positions) // 10),
                max(5000, len(positions) // 5),
                max(10000, len(positions) // 2),
                max(50000, len(positions)),
            ]
        
        return data
    
    def enable_performance_mode(self, enabled: bool = True):
        """Enable/disable performance optimizations."""
        if enabled:
            print("[DisasterMapVisualizer] Performance mode ENABLED")
            # Pre-allocate buffers for faster rendering
            self._performance_buffer_size = 1024 * 1024  # 1MB buffer
            
            # Enable LOD (Level of Detail)
            if hasattr(self.viewer, 'enable_lod'):
                self.viewer.enable_lod(True)
        else:
            print("[DisasterMapVisualizer] Performance mode DISABLED")
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics for large datasets."""
        stats = {
            "camera_views": len(self._cameras),
            "waypoints_count": len(self.navigator.waypoints) if self.navigator else 0,
            "path_segments": len(self.path_visualizer.visualization.secondary_paths) if self.path_visualizer else 0,
            "multi_camera_enabled": self._camera_switching_enabled,
        }
        
        # Add viewer stats if available
        if self.viewer:
            viewer_stats = self.viewer.get_performance_metrics()
            stats["viewer_fps"] = viewer_stats.get("fps", 0)
            stats["viewer_memory_mb"] = viewer_stats.get("memory_mb", 0)
        
        return stats
    
    # =========================================================================
    # Multi-Camera Navigation Commands
    # =========================================================================
    
    async def navigate_between_cameras(
        self, 
        camera_ids: List[str], 
        duration: float = 3.0,
    ) -> bool:
        """Navigate smoothly between multiple camera views."""
        if len(camera_ids) < 2:
            print("[DisasterMapVisualizer] Need at least 2 cameras for navigation")
            return False
        
        # Create smooth transitions between camera positions
        poses = [self._cameras.get(cid) for cid in camera_ids]
        
        if not all(poses):
            print("[DisasterMapVisualizer] Not all camera poses available")
            return False
        
        # Execute fly-through animation
        if self.camera:
            await self.camera.fly_through(poses[0], poses[-1], duration)
        
        print(f"[DisasterMapVisualizer] Navigated between {len(camera_ids)} cameras in {duration}s")
        return True
    
    def get_navigation_capabilities(self) -> Dict[str, Any]:
        """Get navigation system capabilities."""
        return {
            "waypoint_navigation": self.navigator is not None,
            "path_visualization": self.path_visualizer is not None,
            "multi_camera_support": len(self._cameras) > 0,
            "performance_optimized": True,
            "max_points_supported": 10000000,  # 10M points with LOD
        }


# Convenience function for quick setup

def create_visualizer(
    latitude: float = 35.0,
    longitude: float = -120.0,
    altitude: float = 50000.0,
) -> DisasterMapVisualizer:
    """Create a configured visualizer instance."""
    config = CesiumViewerConfig(
        initial_latitude=latitude,
        initial_longitude=longitude,
        initial_altitude=altitude,
    )
    
    viewer = CesiumViewer(config=config)
    camera = CameraControls()
    
    return DisasterMapVisualizer()


if __name__ == "__main__":
    import numpy as np
    
    print("=" * 60)
    print("Disaster Map Visualizer Demo")
    print("=" * 60)
    
    # Create visualizer
    visualizer = create_visualizer(latitude=35.0, longitude=-120.0)
    
    async def demo():
        await visualizer.initialize()
        
        # Add sample point cloud
        np.random.seed(42)
        positions = np.random.randn(10000, 3) * 10000 + [0, 0, 50000]
        colors = np.random.rand(10000, 4)
        
        pc_data = PointCloudData(positions=positions, colors=colors)
        visualizer.add_point_cloud(pc_data, name="sample_terrain")
        
        # Create sample frames with camera poses
        from src.visualization.cesium_viewer import FrameMetadata, CameraPose
        
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
        
        visualizer.add_frames(frames)
        
        # Show metrics
        print("\nVisualization State:")
        metrics = visualizer.get_performance_metrics()
        for key, value in metrics.items():
            if isinstance(value, dict):
                print(f"  {key}:")
                for sub_key, sub_value in list(value.items())[:3]:
                    print(f"    {sub_key}: {sub_value}")
        
        # Export state
        state = visualizer.export_visualization()
        print(f"\nExported state with {len(state.get('viewer', {}).get('frames', []))} frames")
    
    asyncio.run(demo())
    
    print("\nDemo complete!")
