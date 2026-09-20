"""Unit Tests for Camera Module."""

import pytest
from unittest.mock import Mock, MagicMock, patch


class TestCameraPose:
    """Tests for CameraPose data class (matches src.visualization.camera)."""

    def test_initialization_default(self):
        """Test default initialization with defaults."""
        from src.visualization.camera import CameraPose
        
        pose = CameraPose()
        
        assert pose.latitude == 0.0
        assert pose.longitude == 0.0
        assert pose.altitude == 50000.0
        assert pose.heading == 0.0

    def test_initialization_with_values(self):
        """Test initialization with custom values."""
        from src.visualization.camera import CameraPose
        
        pose = CameraPose(
            latitude=45.0,
            longitude=-122.0,
            altitude=10000.0,
            heading=90.0,
            pitch=30.0,
            roll=15.0,
        )
        
        assert pose.latitude == 45.0
        assert pose.longitude == -122.0
        assert pose.altitude == 10000.0

    def test_to_dict(self):
        """Test converting CameraPose to dictionary."""
        from src.visualization.camera import CameraPose
        
        pose = CameraPose(
            latitude=45.0,
            longitude=-122.0,
            altitude=10000.0,
            heading=90.0,
            pitch=30.0,
            roll=15.0,
        )
        
        data = pose.to_dict()
        
        assert isinstance(data, dict)
        assert "latitude" in data

    def test_from_dict(self):
        """Test creating CameraPose from dictionary."""
        from src.visualization.camera import CameraPose
        
        data = {
            "latitude": 45.0,
            "longitude": -122.0,
            "altitude": 10000.0,
            "heading": 90.0,
            "pitch": 30.0,
            "roll": 15.0,
        }
        
        pose = CameraPose.from_dict(data)
        
        assert pose.latitude == 45.0

    def test_equality(self):
        """Test equality comparison."""
        from src.visualization.camera import CameraPose
        
        pose1 = CameraPose(latitude=45.0, longitude=-122.0, altitude=10000.0)
        pose2 = CameraPose(latitude=45.0, longitude=-122.0, altitude=10000.0)
        
        assert pose1 == pose2

    def test_inequality(self):
        """Test inequality comparison."""
        from src.visualization.camera import CameraPose
        
        pose = CameraPose(latitude=45.0, longitude=-122.0, altitude=10000.0)
        
        assert pose != CameraPose(latitude=46.0, longitude=-122.0, altitude=10000.0)


class TestCameraTransformations:
    """Tests for camera transformations."""

    def test_position_update(self):
        """Test updating camera position."""
        from src.visualization.camera import CameraPose
        
        pose = CameraPose(latitude=45.0, longitude=-122.0, altitude=10000.0)
        
        new_latitude = 46.0
        pose.latitude = new_latitude
        
        assert pose.latitude == new_latitude

    def test_heading_update(self):
        """Test updating camera heading."""
        from src.visualization.camera import CameraPose
        
        pose = CameraPose(heading=90.0)
        
        new_heading = 180.0
        pose.heading = new_heading
        
        assert pose.heading == new_heading

    def test_altitude_update(self):
        """Test updating camera altitude."""
        from src.visualization.camera import CameraPose
        
        pose = CameraPose(altitude=50000.0)
        
        new_altitude = 25000.0
        pose.altitude = new_altitude
        
        assert pose.altitude == new_altitude


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
