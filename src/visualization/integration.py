"""
Integration Module - Combines Cesium Viewer, Timeline, and Camera Controls.

Provides a unified interface for building interactive 3D visualizations
with live map updates and smooth navigation.
"""

import asyncio
from typing import Optional, List, Dict, Any
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
        
        self._is_running = False
        print("[DisasterMapVisualizer] Cleanup complete")


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
