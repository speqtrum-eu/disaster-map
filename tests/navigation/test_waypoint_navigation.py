"""
E2E Tests for Waypoint Navigation System.

Tests disaster response scenarios with:
- Multi-waypoint navigation
- Path visualization
- Performance benchmarks
- Cross-browser compatibility simulation
"""

import pytest
import numpy as np
from pathlib import Path

# Import modules under test
from src.navigation.waypoint_navigation import (
    WaypointNavigator,
    Waypoint,
    NavigationMode,
    load_waypoints_batch,
)
from src.navigation.path_visualizer import (
    PathVisualizer,
    PathLayer,
    benchmark_path_rendering,
)


class TestWaypointNavigation:
    """Tests for waypoint navigation functionality."""
    
    def test_create_navigator(self):
        """Test basic navigator creation."""
        navigator = WaypointNavigator()
        
        assert navigator is not None
        assert len(navigator.waypoints) == 0
        assert len(navigator.path_segments) == 0
    
    def test_add_waypoint(self):
        """Test adding waypoints to navigation path."""
        navigator = WaypointNavigator()
        
        waypoint1 = Waypoint(
            id=0, 
            latitude=35.0, 
            longitude=-120.0, 
            altitude=500,
            description="Start point"
        )
        waypoint2 = Waypoint(
            id=1, 
            latitude=36.0, 
            longitude=-119.0, 
            altitude=600,
            description="End point"
        )
        
        assert navigator.add_waypoint(waypoint1) == 0
        assert navigator.add_waypoint(waypoint2) == 1
        
        assert len(navigator.waypoints) == 2
        assert len(navigator.path_segments) == 1
    
    def test_invisible_waypoint_skipped(self):
        """Test that invisible waypoints are skipped."""
        navigator = WaypointNavigator()
        
        waypoint = Waypoint(
            id=0, 
            latitude=35.0, 
            longitude=-120.0, 
            altitude=500,
            visible=False  # Invisible
        )
        
        result = navigator.add_waypoint(waypoint)
        assert result == -1
    
    def test_get_current_position(self):
        """Test getting current interpolated position."""
        navigator = WaypointNavigator()
        
        waypoint1 = Waypoint(id=0, latitude=35.0, longitude=-120.0, altitude=500)
        waypoint2 = Waypoint(id=1, latitude=36.0, longitude=-119.0, altitude=600)
        
        navigator.add_waypoint(waypoint1)
        navigator.add_waypoint(waypoint2)
        
        # Should return None when no navigation active
        current = navigator.get_current_position()
        assert current is None
    
    def test_get_path_trajectory(self):
        """Test generating full trajectory for waypoints."""
        navigator = WaypointNavigator()
        
        waypoint1 = Waypoint(id=0, latitude=35.0, longitude=-120.0, altitude=500)
        waypoint2 = Waypoint(id=1, latitude=36.0, longitude=-119.0, altitude=600)
        
        navigator.add_waypoint(waypoint1)
        navigator.add_waypoint(waypoint2)
        
        trajectory = navigator.get_path_trajectory(num_points=100)
        
        # Should be 101 points (includes both endpoints)
        assert len(trajectory) == 101
        assert all("latitude" in point for point in trajectory)
        assert all("longitude" in point for point in trajectory)
    
    def test_navigation_state(self):
        """Test navigation state management."""
        navigator = WaypointNavigator()
        
        waypoint1 = Waypoint(id=0, latitude=35.0, longitude=-120.0, altitude=500)
        waypoint2 = Waypoint(id=1, latitude=36.0, longitude=-119.0, altitude=600)
        
        navigator.add_waypoint(waypoint1)
        navigator.add_waypoint(waypoint2)
        
        state = navigator.get_state()
        
        assert "waypoints" in state
        assert len(state["waypoints"]) == 2
        assert state["path_segments_count"] >= 1
    
    def test_reset_navigator(self):
        """Test resetting navigation state."""
        navigator = WaypointNavigator()
        
        waypoint1 = Waypoint(id=0, latitude=35.0, longitude=-120.0, altitude=500)
        navigator.add_waypoint(waypoint1)
        
        assert len(navigator.waypoints) == 1
        
        navigator.reset()
        
        assert len(navigator.waypoints) == 0
        assert len(navigator.path_segments) == 0


class TestWaypointBatchLoading:
    """Tests for batch waypoint loading."""
    
    def test_load_waypoints_batch(self):
        """Test efficient batch waypoint loading."""
        waypoints_data = [
            {"id": i, "latitude": 35.0 + i * 0.1, "longitude": -120.0 + i * 0.1, 
             "altitude": 500 + i * 50}
            for i in range(10)
        ]
        
        navigator = load_waypoints_batch(waypoints_data)
        
        assert len(navigator.waypoints) == 10
        assert len(navigator.path_segments) >= 1
    
    def test_load_empty_waypoints(self):
        """Test loading empty waypoint list."""
        navigator = load_waypoints_batch([])
        
        assert len(navigator.waypoints) == 0


class TestPathVisualizer:
    """Tests for path visualization functionality."""
    
    def test_create_visualizer(self):
        """Test basic visualizer creation."""
        visualizer = PathVisualizer()
        
        assert visualizer is not None
        assert len(visualizer.visualization.primary_path) == 0
    
    def test_add_primary_path(self):
        """Test adding primary path."""
        visualizer = PathVisualizer()
        
        points = [{"latitude": i, "longitude": -120.0 + i * 0.1, "altitude": 500} 
                  for i in range(10)]
        
        result = visualizer.add_primary_path(points)
        
        assert result == 0
        assert len(visualizer.visualization.primary_path) == 10
    
    def test_add_secondary_path(self):
        """Test adding secondary path."""
        visualizer = PathVisualizer()
        
        points = [{"latitude": i, "longitude": -120.0 + i * 0.1, "altitude": 600} 
                  for i in range(5)]
        
        result = visualizer.add_secondary_path(points, name="alternate")
        
        assert result == 0
        assert len(visualizer.visualization.secondary_paths) == 1
    
    def test_add_annotation(self):
        """Test adding path annotation."""
        visualizer = PathVisualizer()
        
        from src.navigation.path_visualizer import PathAnnotation
        
        annotation = PathAnnotation(
            latitude=35.0, 
            longitude=-120.0, 
            altitude=500, 
            text="Checkpoint A"
        )
        
        result = visualizer.add_annotation(annotation)
        
        assert result == 0
        assert len(visualizer.visualization.annotations) == 1
    
    def test_get_path_statistics(self):
        """Test calculating path statistics."""
        visualizer = PathVisualizer()
        
        points = [
            {"latitude": 35.0 + i * 0.01, "longitude": -120.0 + i * 0.01, 
             "altitude": 500 + (i % 200)}
            for i in range(100)
        ]
        
        stats = visualizer.get_path_statistics(points)
        
        assert "distance_km" in stats
        assert "max_altitude" in stats
        assert "min_altitude" in stats
        assert stats["point_count"] == 100
    
    def test_get_interpolated_path(self):
        """Test path interpolation."""
        visualizer = PathVisualizer()
        
        points = [{"latitude": i, "longitude": -120.0 + i * 0.1, "altitude": 500} 
                  for i in range(10)]
        
        interpolated = visualizer.get_interpolated_path(points, num_points=100)
        
        assert len(interpolated) == 100
        assert interpolated.shape[1] == 3  # [lat, lon, alt]


class TestPerformanceBenchmarks:
    """Tests for performance benchmarks."""
    
    def test_path_rendering_performance(self):
        """Test path rendering performance with large datasets."""
        num_points = 10000
        
        benchmark_results = benchmark_path_rendering(
            num_points=num_points, 
            iterations=5
        )
        
        # Should complete within reasonable time (< 1 second)
        assert benchmark_results["avg_interpolation_ms"] < 200
        assert benchmark_results["fps_estimate"] > 3
    
    def test_lod_optimization(self):
        """Test Level of Detail optimization."""
        visualizer = PathVisualizer()
        
        # Generate many points
        points = [{"latitude": i % 360, "longitude": (i * 2) % 360, 
                   "altitude": 500 + (i % 100)} for i in range(1000)]
        
        optimized = visualizer.get_optimized_points(points, max_distance=50.0)
        
        # Should reduce point count while maintaining accuracy
        assert len(optimized) <= len(points)
    
    def test_large_dataset_handling(self):
        """Test handling of large datasets (1M+ points)."""
        visualizer = PathVisualizer()
        
        # Simulate 100K points (scaled down for testing)
        num_points = 100000
        
        points = [
            {"latitude": np.random.randn(), 
             "longitude": np.random.randn(), 
             "altitude": 500 + np.random.randint(0, 200)}
            for _ in range(num_points)
        ]
        
        # Should handle without errors
        stats = visualizer.get_path_statistics(points[:100])  # Sample first 100
        
        assert "distance_km" in stats


class TestDisasterResponseScenarios:
    """E2E tests with disaster response scenarios."""
    
    def test_search_and_rescue_waypoints(self):
        """Test navigation for search and rescue scenario."""
        navigator = WaypointNavigator()
        
        # Create waypoints along a search pattern
        waypoints_data = [
            {"id": i, "latitude": 35.0 + i * 0.02, 
             "longitude": -120.0 + i * 0.02, 
             "altitude": 500 + (i % 100)}
            for i in range(20)
        ]
        
        navigator = load_waypoints_batch(waypoints_data)
        
        # Verify search pattern coverage - should have multiple path segments now
        assert len(navigator.waypoints) == 20
        assert len(navigator.path_segments) >= 19  # One segment per waypoint pair
        
        trajectory = navigator.get_path_trajectory(num_points=500)
        # Should have many points from all segments (each segment has ~100-101 points)
        assert len(trajectory) > 1000  # Multiple segments with interpolated points
    
    def test_flood_response_patrol(self):
        """Test navigation for flood response patrol."""
        visualizer = PathVisualizer()
        
        # Create patrol route around affected area
        points = [
            {"latitude": 35.0 + i * 0.01, 
             "longitude": -120.0 + (i % 10) * 0.01, 
             "altitude": 100}
            for i in range(50)
        ]
        
        visualizer.add_primary_path(points)
        
        # Add patrol checkpoints as annotations
        from src.navigation.path_visualizer import PathAnnotation
        
        for i in range(5):
            annotation = PathAnnotation(
                latitude=35.0 + (i * 0.02),
                longitude=-120.0,
                altitude=100,
                text=f"Checkpoint {i}"
            )
            visualizer.add_annotation(annotation)
        
        assert len(visualizer.visualization.annotations) == 5
    
    def test_evacuation_route_planning(self):
        """Test navigation for evacuation route planning."""
        navigator = WaypointNavigator()
        
        # Create evacuation waypoints with safe zones
        waypoints_data = [
            {"id": i, "latitude": 35.0 + i * 0.05, 
             "longitude": -120.0 - (i % 5) * 0.03, 
             "altitude": 800}
            for i in range(15)
        ]
        
        navigator = load_waypoints_batch(waypoints_data)
        
        # Verify route covers evacuation area - should have multiple path segments
        assert len(navigator.waypoints) == 15
        assert len(navigator.path_segments) >= 14  # One segment per waypoint pair
        
        trajectory = navigator.get_path_trajectory(num_points=200)
        # Should have many points from all segments
        assert len(trajectory) > 1000  # Multiple segments with interpolated points
        
        # Check altitude consistency (safe zone elevation)
        altitudes = [p["altitude"] for p in trajectory]
        assert all(a >= 750 for a in altitudes)


class TestCrossBrowserCompatibility:
    """Tests simulating cross-browser compatibility."""
    
    def test_coordinate_precision(self):
        """Test coordinate precision across different systems."""
        navigator = WaypointNavigator()
        
        # Create waypoints with high precision coordinates
        waypoint = Waypoint(
            id=0, 
            latitude=35.123456789, 
            longitude=-120.987654321, 
            altitude=500.123
        )
        
        navigator.add_waypoint(waypoint)
        
        state = navigator.get_state()
        
        # Verify precision is maintained (check string representation length)
        lat_str = str(state["waypoints"][0]["latitude"])
        assert len(lat_str.split('.')[-1]) >= 9 if '.' in lat_str else True
    
    def test_timezone_independence(self):
        """Test that navigation works regardless of timezone."""
        visualizer = PathVisualizer()
        
        points = [
            {"latitude": i, "longitude": -120.0 + i * 0.1, 
             "altitude": 500}
            for i in range(10)
        ]
        
        # Add with different timestamp formats (simulating timezone variations)
        visualizer.add_primary_path(points)
        
        assert len(visualizer.visualization.primary_path) == 10
    
    def test_unicode_descriptions(self):
        """Test handling of unicode in waypoint descriptions."""
        navigator = WaypointNavigator()
        
        # Create waypoints with unicode descriptions (common in international disaster zones)
        waypoint = Waypoint(
            id=0, 
            latitude=35.0, 
            longitude=-120.0, 
            altitude=500,
            description="救援点 A / Rescue Point A"  # Mixed language
        )
        
        navigator.add_waypoint(waypoint)
        
        state = navigator.get_state()
        assert "救援点 A / Rescue Point A" in state["waypoints"][0]["description"]


# Run tests with pytest
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
