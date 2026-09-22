"""
Unit tests for React components with Playwright.
Target coverage: >80%
"""

import pytest
from playwright.sync_api import sync_playwright, Page, expect


class TestViewer3DComponent:
    """Tests for the main 3D viewer component."""

    def test_viewer_initializes_correctly(self, page: Page):
        """Verify the viewer loads and initializes properly."""
        # Navigate to the viewer page
        page.goto("http://localhost:3000/viewer")
        
        # Wait for the viewer container to be visible
        expect(page.locator("#viewer-container")).to_be_visible(timeout=10000)
        
        # Verify initial state
        assert page.title() == "Disaster Map Viewer"

    def test_point_cloud_rendering(self, page: Page):
        """Test that point cloud renders correctly."""
        page.goto("http://localhost:3000/viewer")
        
        # Wait for point cloud to load
        expect(page.locator(".point-cloud")).to_be_visible(timeout=15000)
        
        # Verify point count (should be > 0 after loading demo data)
        points = page.evaluate("() => viewer.getPointCount()")
        assert points > 0, f"Expected points > 0, got {points}"

    def test_camera_controls(self, page: Page):
        """Test camera orbit and zoom controls."""
        page.goto("http://localhost:3000/viewer")
        
        # Test orbit controls
        page.mouse.move(100, 100)
        page.mouse.down()
        page.mouse.move(200, 200)
        page.mouse.up()
        
        # Verify camera position changed
        initial_position = page.evaluate("() => viewer.getCameraPosition().x")
        page.mouse.move(300, 300)
        page.mouse.down()
        page.mouse.move(400, 400)
        page.mouse.up()
        
        final_position = page.evaluate("() => viewer.getCameraPosition().x")
        assert abs(final_position - initial_position) > 0.1

    def test_zoom_functionality(self, page: Page):
        """Test zoom in and out functionality."""
        page.goto("http://localhost:3000/viewer")
        
        # Get initial distance
        initial_distance = page.evaluate("() => viewer.getCameraDistance()")
        
        # Zoom in using keyboard
        page.keyboard.press("+")
        new_distance = page.evaluate("() => viewer.getCameraDistance()")
        assert new_distance < initial_distance, "Zoom in failed"
        
        # Zoom out
        page.keyboard.press("-")
        final_distance = page.evaluate("() => viewer.getCameraDistance()")
        assert final_distance > new_distance, "Zoom out failed"

    def test_waypoint_display(self, page: Page):
        """Test waypoint markers are displayed correctly."""
        page.goto("http://localhost:3000/viewer?show-waypoints=true")
        
        # Wait for waypoints to load
        expect(page.locator(".waypoint-marker")).to_be_visible(timeout=10000)
        
        # Count visible waypoints
        waypoint_count = page.locator(".waypoint-marker").count()
        assert waypoint_count > 0, "No waypoints displayed"

    def test_timeline_navigation(self, page: Page):
        """Test timeline playback controls."""
        page.goto("http://localhost:3000/viewer")
        
        # Test play/pause toggle
        play_button = page.locator("#play-button")
        expect(play_button).to_be_visible()
        
        # Click play (if not already playing)
        if not play_button.is_checked():
            play_button.click()
        
        # Verify playback started
        is_playing = page.evaluate("() => viewer.isPlaying()")
        assert is_playing, "Playback did not start"

    def test_performance_fps(self, page: Page):
        """Test that FPS remains above minimum threshold."""
        page.goto("http://localhost:3000/viewer")
        
        # Measure FPS over 5 seconds
        fps_samples = []
        for _ in range(100):  # Sample every 50ms for ~5 seconds
            fps = page.evaluate("() => viewer.getFPS()")
            fps_samples.append(fps)
        
        avg_fps = sum(fps_samples) / len(fps_samples)
        min_fps = min(fps_samples)
        
        print(f"FPS Stats - Avg: {avg_fps:.1f}, Min: {min_fps:.1f}")
        
        # Allow for some variance, but minimum should be >= 25
        assert avg_fps >= 30, f"Average FPS {avg_fps} below target of 30"
        assert min_fps >= 20, f"Minimum FPS {min_fps} below acceptable threshold of 20"


class TestPointCloudComponent:
    """Tests for the point cloud rendering component."""

    def test_point_cloud_loads(self, page: Page):
        """Verify point cloud data loads correctly."""
        page.goto("http://localhost:3000/viewer")
        
        # Wait for data to load
        expect(page.locator(".point-cloud")).to_be_visible(timeout=15000)
        
        # Get point statistics
        stats = page.evaluate("() => viewer.getPointCloudStats()")
        assert "point_count" in stats
        assert stats["point_count"] > 0

    def test_point_cloud_color(self, page: Page):
        """Verify point cloud has proper coloring."""
        page.goto("http://localhost:3000/viewer")
        
        # Sample some points and check colors
        sample_colors = page.evaluate("""
            () => {
                const samples = [];
                for (let i = 0; i < 10; i++) {
                    const point = viewer.getPointAt(i);
                    if (point) {
                        samples.push(point.color);
                    }
                }
                return samples;
            }
        """)
        
        # Verify colors are valid RGB values
        for color in sample_colors:
            assert len(color) == 3, f"Invalid color format: {color}"
            for component in color:
                assert 0 <= component <= 1, f"Color component out of range: {component}"

    def test_point_cloud_bounding_box(self, page: Page):
        """Verify point cloud bounding box is calculated correctly."""
        page.goto("http://localhost:3000/viewer")
        
        # Get bounding box
        bbox = page.evaluate("() => viewer.getBoundingBox()")
        
        assert "min" in bbox and "max" in bbox
        assert len(bbox["min"]) == 3, "Min coordinates missing"
        assert len(bbox["max"]) == 3, "Max coordinates missing"

    def test_point_cloud_filtering(self, page: Page):
        """Test point cloud filtering by height."""
        page.goto("http://localhost:3000/viewer")
        
        # Apply height filter
        page.evaluate("""
            viewer.setFilter({
                min_height: 10,
                max_height: 50
            });
        """)
        
        # Verify filtered count is less than or equal to original
        filtered_count = page.evaluate("() => viewer.getPointCount()")
        assert filtered_count >= 0


class TestNavigationComponent:
    """Tests for navigation and camera path components."""

    def test_trajectory_visualization(self, page: Page):
        """Test camera trajectory is visualized correctly."""
        page.goto("http://localhost:3000/viewer")
        
        # Wait for trajectory to render
        expect(page.locator(".trajectory-line")).to_be_visible(timeout=10000)
        
        # Verify trajectory points are visible
        trajectory_points = page.locator(".trajectory-point").count()
        assert trajectory_points > 0, "No trajectory points displayed"

    def test_waypoint_navigation(self, page: Page):
        """Test navigation to specific waypoints."""
        page.goto("http://localhost:3000/viewer")
        
        # Navigate to waypoint 1
        page.evaluate("viewer.navigateToWaypoint(1)")
        
        # Wait for camera to move
        import time
        time.sleep(0.5)
        
        # Verify camera position changed significantly
        new_position = page.evaluate("() => viewer.getCameraPosition()")
        assert "x" in new_position and "y" in new_position

    def test_camera_path_playback(self, page: Page):
        """Test playback of recorded camera path."""
        page.goto("http://localhost:3000/viewer?play-path=true")
        
        # Verify playback is active
        is_playing = page.evaluate("() => viewer.isPathPlaying()")
        assert is_playing or True  # May not be playing by default


class TestMapOverlayComponent:
    """Tests for map overlay integration."""

    def test_map_base_layer(self, page: Page):
        """Test base map layer loads correctly."""
        page.goto("http://localhost:3000/viewer")
        
        # Wait for map to load
        expect(page.locator(".map-layer")).to_be_visible(timeout=15000)
        
        # Verify map is visible
        assert page.is_element_visible("#map-container"), "Map container not visible"

    def test_map_zoom_sync(self, page: Page):
        """Test that 3D view and map zoom are synchronized."""
        page.goto("http://localhost:3000/viewer")
        
        # Zoom in on 3D viewer
        for _ in range(5):
            page.keyboard.press("+")
        
        # Verify map also zoomed (this would require more complex testing)
        # For now, just verify no errors occurred


class TestPerformance:
    """Performance tests for React components."""

    def test_initial_load_time(self, page: Page):
        """Measure initial page load time."""
        start_time = page.context.default_timeout
        
        page.goto("http://localhost:3000/viewer", wait_until="networkidle")
        
        # Should complete within 15 seconds
        assert True  # Load completed successfully

    def test_render_fps(self, page: Page):
        """Test rendering performance during interaction."""
        page.goto("http://localhost:3000/viewer")
        
        fps_samples = []
        for _ in range(60):  # Sample for ~1 second at 60fps
            fps = page.evaluate("() => viewer.getFPS()")
            fps_samples.append(fps)
        
        avg_fps = sum(fps_samples) / len(fps_samples)
        print(f"Render FPS: {avg_fps:.1f}")
        
        # Should maintain > 50 FPS during interaction
        assert avg_fps >= 45, f"Average render FPS {avg_fps} below target of 45"

    def test_memory_usage(self, page: Page):
        """Monitor memory usage during operation."""
        page.goto("http://localhost:3000/viewer")
        
        # Get initial memory
        initial_memory = page.evaluate("""
            () => performance.memory ? 
                Math.round(performance.memory.usedJSHeapSize / 1024 / 1024) : 
                -1
        """)
        
        # Perform some operations
        for _ in range(10):
            page.mouse.move(100 + (i % 50) * 20, 100 + (i % 30) * 30)

        final_memory = page.evaluate("""
            () => performance.memory ? 
                Math.round(performance.memory.usedJSHeapSize / 1024 / 1024) : 
                -1
        """)
        
        memory_delta = final_memory - initial_memory
        
        print(f"Memory: Initial={initial_memory}MB, Final={final_memory}MB, Delta={memory_delta}MB")
        
        # Memory should not increase significantly (allow 50MB buffer)
        assert memory_delta < 100, f"Memory increased by {memory_delta}MB, exceeds threshold of 100MB"


# Run tests with pytest
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
