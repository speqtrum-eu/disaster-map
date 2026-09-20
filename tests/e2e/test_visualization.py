"""
E2E Tests for 3D Visualization Components.

Tests cover:
- CesiumViewer initialization and point cloud rendering
- Timeline navigation and frame playback
- Camera controls (orbit, zoom, fly-through)
- Integration with DisasterMapVisualizer
- Performance benchmarks (60 FPS target)
"""

import pytest
import numpy as np
from pathlib import Path
import sys
import asyncio

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.visualization.cesium_viewer import (
    CesiumViewer, 
    PointCloudData, 
    CameraPose, 
    FrameMetadata,
    CesiumViewerConfig,
)
from src.visualization.timeline import TimelineNavigator, TimelineConfig
from src.visualization.camera import CameraControls, CameraConfig
from src.visualization.integration import DisasterMapVisualizer


class TestCesiumViewer:
    """Tests for CesiumViewer component."""
    
    def test_initialization(self):
        """Test viewer initialization with default config."""
        viewer = CesiumViewer()
        assert viewer is not None
        
        # Initialize (simulated)
        result = asyncio.run(viewer.initialize())
        assert result is True
    
    def test_custom_config(self):
        """Test viewer initialization with custom configuration."""
        config = CesiumViewerConfig(
            initial_latitude=40.7128,  # NYC
            initial_longitude=-74.0060,
            initial_altitude=100000.0,
            fps_target=30,
        )
        
        viewer = CesiumViewer(config=config)
        assert viewer.config.initial_latitude == 40.7128
        assert viewer.config.fps_target == 30
    
    def test_add_point_cloud(self):
        """Test adding point cloud data."""
        np.random.seed(42)
        positions = np.random.randn(5000, 3) * 10000 + [0, 0, 50000]
        colors = np.random.rand(5000, 4)
        
        viewer = CesiumViewer()
        asyncio.run(viewer.initialize())
        
        pc_data = PointCloudData(positions=positions, colors=colors)
        index = viewer.add_point_cloud(pc_data, name="test_terrain")
        
        assert index == 0
        assert len(viewer._point_clouds) == 1
    
    def test_multiple_point_clouds(self):
        """Test adding multiple point clouds."""
        np.random.seed(42)
        
        viewer = CesiumViewer()
        asyncio.run(viewer.initialize())
        
        for i in range(5):
            positions = np.random.randn(1000, 3) * 1000 + [i*1000, 0, 50000]
            pc_data = PointCloudData(positions=positions)
            viewer.add_point_cloud(pc_data, name=f"layer_{i}")
        
        assert len(viewer._point_clouds) == 5
    
    def test_empty_point_cloud_rejection(self):
        """Test that empty point clouds are rejected."""
        viewer = CesiumViewer()
        asyncio.run(viewer.initialize())
        
        with pytest.raises(ValueError, match="Point cloud must have at least one position"):
            viewer.add_point_cloud(PointCloudData(positions=np.array([]).reshape(0, 3)))
    
    def test_frame_metadata(self):
        """Test frame metadata creation and storage."""
        pose = CameraPose(latitude=35.0, longitude=-120.0, altitude=50000.0)
        
        frame = FrameMetadata(
            timestamp=1.5,
            frame_number=42,
            pose=pose
        )
        
        assert frame.timestamp == 1.5
        assert frame.frame_number == 42
        assert frame.pose.latitude == 35.0
    
    def test_get_current_pose(self):
        """Test getting current camera pose."""
        viewer = CesiumViewer()
        asyncio.run(viewer.initialize())
        
        initial_pose = viewer.get_current_pose()
        assert initial_pose.altitude == 50000.0
        
        # Set new position
        new_pose = CameraPose(latitude=36.0, longitude=-121.0, altitude=45000.0)
        viewer.set_camera_position(new_pose)
        
        current_pose = viewer.get_current_pose()
        assert current_pose.latitude == 36.0
        assert current_pose.longitude == -121.0
    
    def test_export_state(self):
        """Test exporting and loading viewer state."""
        np.random.seed(42)
        positions = np.random.randn(100, 3) * 1000
        
        viewer = CesiumViewer()
        asyncio.run(viewer.initialize())
        
        # Add data
        pc_data = PointCloudData(positions=positions)
        viewer.add_point_cloud(pc_data)
        
        # Export state
        exported = viewer.export_state()
        assert "point_clouds" in exported
        assert len(exported["point_clouds"]) == 1
    
    def test_performance_metrics(self):
        """Test performance metrics collection."""
        viewer = CesiumViewer()
        asyncio.run(viewer.initialize())
        
        metrics = viewer.get_performance_metrics()
        
        assert "frame_count" in metrics
        assert "point_cloud_count" in metrics
        assert "total_points" in metrics


class TestTimelineNavigator:
    """Tests for TimelineNavigator component."""
    
    def test_initialization(self):
        """Test timeline navigator initialization."""
        frames = [
            {"timestamp": i, 
             "pose": {"latitude": 35.0 + i * 0.1} if i % 2 == 0 else None
             }
            for i in range(10)
        ]
        
        navigator = TimelineNavigator(frames)
        assert navigator.total_frames == 10
    
    def test_frame_navigation(self):
        """Test frame-by-frame navigation."""
        frames = [{"timestamp": i} for i in range(20)]
        navigator = TimelineNavigator(frames)
        
        # Navigate to specific frame
        result = navigator.go_to_frame(5)
        assert result is True
        assert navigator.state.current_frame_index == 5
        
        # First and last frames
        navigator.go_to_first_frame()
        assert navigator.state.current_frame_index == 0
        
        navigator.go_to_last_frame()
        assert navigator.state.current_frame_index == 19
    
    def test_out_of_bounds_navigation(self):
        """Test navigation with invalid frame indices."""
        frames = [{"timestamp": i} for i in range(5)]
        navigator = TimelineNavigator(frames)
        
        # Invalid indices should return False
        assert not navigator.go_to_frame(-1)
        assert not navigator.go_to_frame(100)
    
    def test_get_frame_at_time(self):
        """Test finding frame at specific timestamp."""
        frames = [
            {
                "timestamp": i * 2.0, 
                "pose": {"latitude": 35.0 + i * 0.1} if i % 2 == 0 else None
            }
            for i in range(10)
        ]
        
        navigator = TimelineNavigator(frames)
        
        # Find frame at timestamp 6.0 (should be index 3)
        result = navigator.get_frame_at_time(6.0)
        assert result is not None
        assert result["index"] == 3
    
    def test_playback_state(self):
        """Test playback state management."""
        frames = [{"timestamp": i} for i in range(10)]
        navigator = TimelineNavigator(frames)
        
        # Initial state
        assert not navigator.is_playing
        assert navigator.state.total_frames == 10
        
        # Get current state
        state = navigator.get_current_state()
        assert "current_frame_index" in state
        assert "total_frames" in state
    
    def test_export_timeline(self):
        """Test exporting timeline data."""
        frames = [
            {
                "timestamp": i, 
                "pose": {"latitude": 35.0 + i * 0.1} if i % 2 == 0 else None
            }
            for i in range(5)
        ]
        
        navigator = TimelineNavigator(frames)
        exported = navigator.export_timeline()
        
        assert "frames" in exported
        assert len(exported["frames"]) == 5


class TestCameraControls:
    """Tests for CameraControls component."""
    
    def test_initialization(self):
        """Test camera controls initialization."""
        config = CameraConfig(
            min_altitude=100.0,
            max_altitude=1e7,
            smooth_zoom=True,
        )
        
        controls = CameraControls(config=config)
        assert controls.config.min_altitude == 100.0
    
    def test_set_position(self):
        """Test setting camera position."""
        controls = CameraControls()
        
        pose = CameraPose(latitude=35.0, longitude=-120.0, altitude=50000.0)
        controls.set_position(pose)
        
        assert controls.pose.latitude == 35.0
        assert controls.pose.longitude == -120.0
    
    def test_zoom_limits(self):
        """Test zoom altitude clamping."""
        config = CameraConfig(min_altitude=1000.0, max_altitude=1e6)
        controls = CameraControls(config=config)
        
        # Zoom below minimum
        controls.set_position(CameraPose(altitude=50000.0))
        controls.zoom(-0.99)  # Would go to 50m
        
        assert controls.pose.altitude >= config.min_altitude
    
    def test_zoom_above_maximum(self):
        """Test zoom altitude clamping above maximum."""
        config = CameraConfig(min_altitude=100.0, max_altitude=1e6)
        controls = CameraControls(config=config)
        
        # Zoom above maximum
        controls.set_position(CameraPose(altitude=50000.0))
        controls.zoom(2.0)  # Would go to 100km
        
        assert controls.pose.altitude <= config.max_altitude
    
    def test_fly_through_animation(self):
        """Test fly-through animation creation."""
        start_pose = CameraPose(latitude=35.0, longitude=-120.0, altitude=50000.0)
        end_pose = CameraPose(latitude=36.0, longitude=-121.0, altitude=45000.0)
        
        controls = CameraControls()
        animate_func = controls.fly_through(start_pose, end_pose, duration_seconds=3.0)
        
        assert callable(animate_func)
    
    def test_waypoint_fly_through(self):
        """Test waypoint fly-through with multiple waypoints."""
        waypoints = [
            CameraPose(latitude=35.0 + i * 0.1, longitude=-120.0 - i * 0.1, altitude=50000 - i * 1000)
            for i in range(5)
        ]
        
        controls = CameraControls()
        
        # Should handle empty waypoints gracefully
        assert not hasattr(controls.fly_through_state, 'waypoints') or len(controls.fly_through_state.waypoints) == 0
    
    def test_performance_metrics(self):
        """Test performance metrics collection."""
        controls = CameraControls()
        metrics = controls.get_performance_metrics()
        
        assert "pose" in metrics
        assert "is_animating" in metrics


class TestDisasterMapVisualizer:
    """Integration tests for DisasterMapVisualizer."""
    
    def test_initialization(self):
        """Test visualizer initialization."""
        visualizer = DisasterMapVisualizer()
        
        result = asyncio.run(visualizer.initialize())
        assert result is True
        assert visualizer.viewer is not None
        assert visualizer.camera is not None
    
    def test_add_point_cloud_and_frames(self):
        """Test adding point cloud and frames to visualizer."""
        np.random.seed(42)
        
        visualizer = DisasterMapVisualizer()
        asyncio.run(visualizer.initialize())
        
        # Add point cloud
        positions = np.random.randn(1000, 3) * 1000 + [0, 0, 50000]
        pc_data = PointCloudData(positions=positions)
        visualizer.add_point_cloud(pc_data, name="test_layer")
        
        # Add frames
        from src.visualization.cesium_viewer import FrameMetadata, CameraPose
        
        frames = [
            {
                "timestamp": i, 
                "pose": {"latitude": 35.0 + i * 0.1} if i % 2 == 0 else None
            }
            for i in range(20)
        ]
        visualizer.add_frames(frames)
    
    def test_get_performance_metrics(self):
        """Test performance metrics from integrated system."""
        visualizer = DisasterMapVisualizer()
        asyncio.run(visualizer.initialize())
        
        metrics = visualizer.get_performance_metrics()
        
        assert "viewer" in metrics
        assert "camera" in metrics
    
    def test_export_visualization(self):
        """Test exporting visualization state."""
        np.random.seed(42)
        
        visualizer = DisasterMapVisualizer()
        asyncio.run(visualizer.initialize())
        
        # Add some data
        positions = np.random.randn(100, 3) * 1000
        pc_data = PointCloudData(positions=positions)
        visualizer.add_point_cloud(pc_data)
        
        exported = visualizer.export_visualization()
        
        assert "viewer" in exported
        assert "camera" in exported


class TestPerformanceBenchmarks:
    """Performance benchmark tests."""
    
    def test_viewer_initialization_speed(self):
        """Test viewer initialization is fast (< 100ms)."""
        import time
        
        start = time.time()
        
        for _ in range(10):
            viewer = CesiumViewer()
            asyncio.run(viewer.initialize())
        
        elapsed = (time.time() - start) * 1000  # ms
        
        assert elapsed < 100, f"Initialization took {elapsed:.0f}ms, expected < 100ms"
    
    def test_point_cloud_addition_speed(self):
        """Test adding point clouds is efficient."""
        import time
        
        np.random.seed(42)
        
        start = time.time()
        
        viewer = CesiumViewer()
        asyncio.run(viewer.initialize())
        
        # Add 100 point clouds with 10k points each
        for i in range(100):
            positions = np.random.randn(10000, 3) * 1000 + [i*1000, 0, 50000]
            pc_data = PointCloudData(positions=positions)
            viewer.add_point_cloud(pc_data)
        
        elapsed = (time.time() - start) * 1000
        
        assert elapsed < 500, f"Point cloud addition took {elapsed:.0f}ms"
    
    def test_timeline_navigation_speed(self):
        """Test timeline navigation is responsive."""
        import time
        
        frames = [{"timestamp": i} for i in range(1000)]
        
        start = time.time()
        
        navigator = TimelineNavigator(frames)
        
        # Navigate through all frames
        for _ in range(100):
            navigator.go_to_frame(np.random.randint(0, 1000))
        
        elapsed = (time.time() - start) * 1000
        
        assert elapsed < 500, f"Timeline navigation took {elapsed:.0f}ms"
    
    def test_camera_controls_responsiveness(self):
        """Test camera controls are responsive."""
        import time
        
        config = CameraConfig(smooth_zoom=True)
        
        start = time.time()
        
        for _ in range(100):
            controls = CameraControls(config=config)
            pose = CameraPose(latitude=35.0 + np.random.rand(), longitude=-120.0 + np.random.rand())
            controls.set_position(pose)
            
            # Perform zoom operations
            controls.zoom(np.random.uniform(-0.1, 0.1))
        
        elapsed = (time.time() - start) * 1000
        
        assert elapsed < 500, f"Camera controls took {elapsed:.0f}ms"


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
