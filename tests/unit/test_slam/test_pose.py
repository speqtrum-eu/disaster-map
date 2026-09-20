"""Unit Tests for Pose Estimation Module."""

import pytest
import numpy as np
from unittest.mock import Mock, MagicMock, patch


class TestPoseEstimate:
    """Tests for PoseEstimate data class (matches src.core.slam.base_slam)."""

    def test_initialization_default(self):
        """Test default initialization with zeros."""
        from src.core.slam.base_slam import PoseEstimate
        
        pose = PoseEstimate()
        
        assert pose.position.shape == (3,)
        assert np.allclose(pose.position, [0.0, 0.0, 0.0])
        assert pose.timestamp == 0.0
        assert pose.confidence == 0.0

    def test_initialization_with_values(self):
        """Test initialization with custom values."""
        from src.core.slam.base_slam import PoseEstimate
        
        position = np.array([10.5, -20.3, 50.7])
        orientation = np.array([0.8, 0.5, -0.3, 0.1])  # [w, x, y, z]
        
        pose = PoseEstimate(
            position=position,
            orientation=orientation,
            timestamp=123.456,
            confidence=0.95,
        )
        
        assert np.array_equal(pose.position, position)
        assert np.allclose(pose.orientation, orientation)
        assert pose.timestamp == 123.456

    def test_position_validation(self):
        """Test that invalid position shape raises error."""
        from src.core.slam.base_slam import PoseEstimate
        
        with pytest.raises(ValueError, match="Position must be a 3-element array"):
            PoseEstimate(position=np.array([1, 2]))

    def test_orientation_validation(self):
        """Test that invalid orientation shape raises error."""
        from src.core.slam.base_slam import PoseEstimate
        
        pose = PoseEstimate()
        
        with pytest.raises(ValueError, match="Orientation quaternion must be a 4-element array"):
            PoseEstimate(orientation=np.array([1, 2]))

    def test_to_dict(self):
        """Test converting PoseEstimate to dictionary."""
        from src.core.slam.base_slam import PoseEstimate
        
        pose = PoseEstimate(
            position=np.array([10.5, -20.3, 50.7]),
            orientation=np.array([0.8, 0.5, -0.3, 0.1]),
            timestamp=123.456,
            confidence=0.95,
        )
        
        # Use dataclass asdict for serialization
        from dataclasses import asdict
        
        data = asdict(pose)
        
        assert isinstance(data, dict)
        assert "position" in data

    def test_equality(self):
        """Test equality comparison with numpy arrays."""
        from src.core.slam.base_slam import PoseEstimate
        
        pose1 = PoseEstimate(
            position=np.array([10.5, -20.3, 50.7]),
            orientation=np.array([0.8, 0.5, -0.3, 0.1]),
            timestamp=123.456,
        )
        
        pose2 = PoseEstimate(
            position=np.array([10.5, -20.3, 50.7]),
            orientation=np.array([0.8, 0.5, -0.3, 0.1]),
            timestamp=123.456,
        )
        
        # Compare using numpy arrays directly
        assert np.array_equal(pose1.position, pose2.position)

    def test_inequality(self):
        """Test inequality comparison."""
        from src.core.slam.base_slam import PoseEstimate
        
        pose = PoseEstimate(
            position=np.array([10.5, -20.3, 50.7]),
            orientation=np.array([0.8, 0.5, -0.3, 0.1]),
            timestamp=123.456,
        )
        
        new_pose = PoseEstimate(
            position=np.array([11.0, -20.3, 50.7]),
            orientation=np.array([0.8, 0.5, -0.3, 0.1]),
            timestamp=123.456,
        )
        
        assert not np.array_equal(pose.position, new_pose.position)


class TestPoseOperations:
    """Tests for pose operations and transformations."""

    def test_position_addition(self):
        """Test adding two positions."""
        position1 = np.array([1.0, 2.0, 3.0])
        position2 = np.array([4.0, 5.0, 6.0])
        
        result = position1 + position2
        
        expected = np.array([5.0, 7.0, 9.0])
        assert np.array_equal(result, expected)

    def test_position_norm(self):
        """Test calculating position norm."""
        position = np.array([3.0, 4.0, 0.0])
        
        result = np.linalg.norm(position)
        
        assert abs(result - 5.0) < 1e-6

    def test_position_distance(self):
        """Test calculating distance between two positions."""
        position1 = np.array([0.0, 0.0, 0.0])
        position2 = np.array([3.0, 4.0, 0.0])
        
        result = np.linalg.norm(position2 - position1)
        
        assert abs(result - 5.0) < 1e-6


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
