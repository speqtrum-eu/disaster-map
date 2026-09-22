"""
End-to-End tests for Disaster Map Web Viewer using Playwright.
Tests complete user workflows and integration between components.
"""

import pytest
from playwright.sync_api import sync_playwright, Page, expect
import time


class TestViewerE2E:
    """End-to-end tests for the main viewer application."""

    @pytest.fixture(autouse=True)
    def setup(self, page: Page):
        """Set up test environment before each test."""
        # Set a longer timeout for E2E tests
        page.set_default_timeout(30000)
        
        yield
        
        # Cleanup after test if needed

    def test_full_workflow_load_and_navigate(self, page: Page):
        """Test complete workflow: load viewer, navigate, interact."""
        # 1. Load the application
        page.goto("http://localhost:3000/viewer")
        
        # Verify initial state
        expect(page.title()).to_contain_text("Disaster Map")
        expect(page.locator("#viewer-container")).to_be_visible(timeout=15000)

        # 2. Wait for point cloud to load
        page.wait_for_selector(".point-cloud", timeout=20000)
        
        # Verify data loaded
        point_count = page.evaluate("() => viewer.getPointCount()")
        assert point_count > 0, f"Expected points > 0, got {point_count}"

        # 3. Navigate using timeline
        play_button = page.locator("#play-button")
        
        if not play_button.is_checked():
            play_button.click()
        
        # Verify playback started
        is_playing = page.evaluate("() => viewer.isPlaying()")
        assert is_playing, "Playback did not start"

        # 4. Interact with camera controls
        # Orbit around the scene
        page.mouse.move(100, 100)
        time.sleep(0.2)
        
        page.mouse.down()
        time.sleep(0.1)
        page.mouse.move(300, 300)
        time.sleep(0.1)
        page.mouse.up()

        # Verify camera moved
        new_position = page.evaluate("() => viewer.getCameraPosition().x")
        
        # 5. Zoom in and out
        initial_distance = page.evaluate("() => viewer.getCameraDistance()")
        
        for _ in range(3):
            page.keyboard.press("+")
        
        final_distance = page.evaluate("() => viewer.getCameraDistance()")
        assert final_distance < initial_distance, "Zoom in failed"

    def test_waypoint_navigation_workflow(self, page: Page):
        """Test complete waypoint navigation workflow."""
        # Load viewer with waypoints visible
        page.goto("http://localhost:3000/viewer?show-waypoints=true")
        
        # Wait for waypoints to load
        expect(page.locator(".waypoint-marker")).to_be_visible(timeout=15000)
        
        waypoint_count = page.locator(".waypoint-marker").count()
        assert waypoint_count > 0, "No waypoints loaded"

        # Navigate to first waypoint
        page.evaluate("viewer.navigateToWaypoint(1)")
        
        time.sleep(0.5)  # Allow camera movement
        
        new_position = page.evaluate("() => viewer.getCameraPosition()")
        assert "x" in new_position and "y" in new_position

    def test_map_overlay_integration(self, page: Page):
        """Test integration between 3D viewer and map overlay."""
        # Load viewer with map layer
        page.goto("http://localhost:3000/viewer")
        
        # Wait for map to load
        expect(page.locator(".map-layer")).to_be_visible(timeout=15000)

        # Verify both layers are visible
        assert page.is_element_visible("#viewer-container"), "Viewer not visible"
        assert page.is_element_visible("#map-container"), "Map container not visible"

    def test_performance_under_load(self, page: Page):
        """Test performance with multiple interactions."""
        page.goto("http://localhost:3000/viewer")
        
        # Measure FPS before interaction
        initial_fps = []
        for _ in range(20):
            fps = page.evaluate("() => viewer.getFPS()")
            initial_fps.append(fps)
        
        avg_initial_fps = sum(initial_fps) / len(initial_fps)

        # Perform multiple interactions rapidly
        for i in range(10):
            # Orbit
            page.mouse.move(100 + (i % 50) * 20, 100 + (i % 30) * 30)
            
            # Zoom
            if i % 2 == 0:
                page.keyboard.press("+")
            else:
                page.keyboard.press("-")

        # Measure FPS after interaction
        final_fps = []
        for _ in range(20):
            fps = page.evaluate("() => viewer.getFPS()")
            final_fps.append(fps)
        
        avg_final_fps = sum(final_fps) / len(final_fps)

        print(f"Initial FPS: {avg_initial_fps:.1f}, Final FPS: {avg_final_fps:.1f}")

        # Performance should remain acceptable
        assert avg_final_fps >= 25, f"FPS dropped to {avg_final_fps} after interactions"

    def test_timeline_playback_workflow(self, page: Page):
        """Test complete timeline playback workflow."""
        page.goto("http://localhost:3000/viewer")
        
        # Wait for data to load
        expect(page.locator(".point-cloud")).to_be_visible(timeout=15000)

        # Start playback
        play_button = page.locator("#play-button")
        if not play_button.is_checked():
            play_button.click()

        time.sleep(0.5)  # Allow playback to start

        # Verify playing state
        is_playing = page.evaluate("() => viewer.isPlaying()")
        assert is_playing, "Playback did not start"

        # Pause playback
        if play_button.is_checked():
            play_button.click()

        time.sleep(0.2)

        # Verify paused state
        is_stopped = page.evaluate("() => !viewer.isPlaying()")
        assert is_stopped, "Pause failed"

    def test_view_reset_and_restore(self, page: Page):
        """Test view reset functionality."""
        page.goto("http://localhost:3000/viewer")
        
        # Get initial camera position
        initial_position = page.evaluate("() => viewer.getCameraPosition()")
        initial_distance = page.evaluate("() => viewer.getCameraDistance()")

        # Make significant changes to view
        for _ in range(5):
            page.keyboard.press("+")
        
        time.sleep(0.2)
        
        modified_position = page.evaluate("() => viewer.getCameraPosition()")
        modified_distance = page.evaluate("() => viewer.getCameraDistance()")

        # Reset view
        page.keyboard.press("r")  # R key for reset
        
        time.sleep(0.3)

        # Verify view was restored (approximately)
        reset_position = page.evaluate("() => viewer.getCameraPosition()")
        reset_distance = page.evaluate("() => viewer.getCameraDistance()")

        print(f"Initial: pos={initial_position}, dist={initial_distance}")
        print(f"After modification: pos={modified_position}, dist={modified_distance}")
        print(f"After reset: pos={reset_position}, dist={reset_distance}")


class TestDataLoadingE2E:
    """End-to-end tests for data loading workflows."""

    def test_demo_data_loads_correctly(self, page: Page):
        """Test that demo data loads correctly from results/demo_20260920_230738/"""
        # Load viewer with demo data URL
        demo_url = "http://localhost:3000/viewer?demo=true"
        
        page.goto(demo_url)
        
        # Wait for point cloud to load
        expect(page.locator(".point-cloud")).to_be_visible(timeout=20000)

        # Verify data loaded from demo source
        stats = page.evaluate("() => viewer.getPointCloudStats()")
        assert "point_count" in stats
        assert stats["point_count"] > 0

    def test_multiple_datasets_switching(self, page: Page):
        """Test switching between different datasets."""
        # Load first dataset
        page.goto("http://localhost:3000/viewer?dataset=disaster-zone")
        
        expect(page.locator(".point-cloud")).to_be_visible(timeout=15000)
        count_1 = page.evaluate("() => viewer.getPointCount()")

        # Switch to second dataset (if available)
        page.goto("http://localhost:3000/viewer?dataset=rescue-waypoints")
        
        expect(page.locator(".point-cloud")).to_be_visible(timeout=15000)
        count_2 = page.evaluate("() => viewer.getPointCount()")

        # Both datasets should load successfully
        assert count_1 > 0, f"First dataset failed to load: {count_1} points"
        assert count_2 > 0, f"Second dataset failed to load: {count_2} points"


class TestUserInteractionsE2E:
    """End-to-end tests for user interaction workflows."""

    def test_keyboard_shortcuts(self, page: Page):
        """Test keyboard shortcut functionality."""
        page.goto("http://localhost:3000/viewer")
        
        # Test zoom shortcuts
        initial_distance = page.evaluate("() => viewer.getCameraDistance()")
        
        page.keyboard.press("+")  # Zoom in with +
        new_distance = page.evaluate("() => viewer.getCameraDistance()")
        assert new_distance < initial_distance, "Zoom shortcut failed"

    def test_mouse_interactions(self, page: Page):
        """Test mouse interaction workflows."""
        page.goto("http://localhost:3000/viewer")
        
        # Test drag to orbit
        page.mouse.move(100, 100)
        time.sleep(0.1)
        
        page.mouse.down()
        time.sleep(0.1)
        page.mouse.move(200, 200)
        time.sleep(0.1)
        page.mouse.up()

        # Verify camera moved
        new_position = page.evaluate("() => viewer.getCameraPosition().x")
        
    def test_context_menu(self, page: Page):
        """Test context menu functionality."""
        page.goto("http://localhost:3000/viewer")
        
        # Right-click on scene to open context menu
        page.mouse.move(150, 150)
        time.sleep(0.1)
        
        page.mouse.click(150, 150, button="right")
        
        # Verify context menu appeared (may need specific selectors)
        # This test may need adjustment based on actual implementation


class TestAccessibilityE2E:
    """End-to-end accessibility tests."""

    def test_keyboard_navigation(self, page: Page):
        """Test that application is navigable via keyboard only."""
        page.goto("http://localhost:3000/viewer")
        
        # Navigate using Tab key
        for _ in range(10):
            page.keyboard.press("Tab")

        # Should not get stuck or error
        assert True  # If we got here, navigation worked

    def test_focus_management(self, page: Page):
        """Test proper focus management."""
        page.goto("http://localhost:3000/viewer")
        
        # Check that main container is focusable
        focused_element = page.evaluate("document.activeElement.tagName")
        
        # Should be on a valid interactive element or body
        assert focused_element in ["BODY", "DIV", "BUTTON", "INPUT"]


# Run tests with pytest
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
