"""Unit Tests for Base SLAM Module."""

import pytest
import numpy as np
from unittest.mock import Mock, MagicMock
from src.core.slam.base_slam import (
    PoseEstimate, 
    MapState, 
    SLAMConfig, 
    BaseSLAMEngine,
)


class TestPoseEstimate:
    """Tests for PoseEstimate data class."""
    
    def test_initialization_default(self):
        """Test default initialization with zeros."""
        pose = PoseEstimate()
        
        assert np.allclose(pose.position, [0.0, 0.0, 0.0])
        assert pose.orientation is None
        assert pose.covariance is None
        assert pose.timestamp == 0.0
        assert pose.confidence == 0.0
    
    def test_initialization_with_values(self):
        """Test initialization with custom values."""
        position = np.array([1.5, -2.3, 45.7])
        orientation = np.array([0.98, 0.06, 0.02, 0.0])
        
        pose = PoseEstimate(
            position=position,
            orientation=orientation,
            timestamp=123.456,
            confidence=0.95
        )
        
        assert np.allclose(pose.position, position)
        assert np.allclose(pose.orientation, orientation)
        assert pose.timestamp == 123.456
        assert pose.confidence == 0.95
    
    def test_invalid_position_shape(self):
        """Test that invalid position shape raises error."""
        with pytest.raises(ValueError, match="Position must be a 3-element array"):
            PoseEstimate(position=np.array([1, 2]))
    
    def test_invalid_orientation_shape(self):
        """Test that invalid orientation shape raises error."""
        pose = PoseEstimate()
        
        with pytest.raises(ValueError, match="Orientation quaternion must be a 4-element array"):
            pose.orientation = np.array([1, 2])


class TestMapState:
    """Tests for MapState data class."""
    
    def test_initialization_default(self):
        """Test default initialization."""
        state = MapState()
        
        assert state.num_keyframes == 0
        assert state.num_features == 0
        assert state.num_points == 0
        assert state.volume == 0.0
        assert state.drift_error == 0.0
    
    def test_initialization_with_values(self):
        """Test initialization with custom values."""
        state = MapState(
            num_keyframes=150,
            num_features=50000,
            num_points=250000,
            volume=1234.56,
            drift_error=0.023
        )
        
        assert state.num_keyframes == 150
        assert state.num_features == 50000
        assert state.volume == 1234.56
    
    def test_to_dict(self):
        """Test serialization to dictionary."""
        state = MapState(
            num_keyframes=10,
            num_features=1000,
            volume=500.0,
            drift_error=0.01
        )
        
        data = state.to_dict()
        
        assert "num_keyframes" in data
        assert data["num_keyframes"] == 10
        assert isinstance(data["volume"], float)


class TestSLAMConfig:
    """Tests for SLAMConfig data class."""
    
    def test_initialization_default(self):
        """Test default configuration values."""
        config = SLAMConfig()
        
        assert config.camera_width == 640
        assert config.camera_height == 480
        assert config.frame_rate == 30.0
        assert config.max_keyframes == 1000
    
    def test_initialization_with_values(self):
        """Test initialization with custom values."""
        config = SLAMConfig(
            camera_width=1280,
            camera_height=720,
            focal_length=500.0,
            frame_rate=60.0
        )
        
        assert config.camera_width == 1280
        assert config.focal_length == 500.0
    
    def test_auto_focal_length_detection(self):
        """Test automatic focal length detection when not provided."""
        # Create a wide camera (width > height)
        config = SLAMConfig(camera_width=1920, camera_height=1080)
        
        # Focal length should be approximately max dimension * 0.5
        expected_focal = max(1920, 1080) * 0.5
        
        assert config.focal_length is not None
        assert abs(config.focal_length - expected_focal) < 0.1


class TestBaseSLAMEngine:
    """Tests for BaseSLAMEngine abstract class."""
    
    def test_initialization(self):
        """Test engine initialization with default config."""
        engine = Mock(spec=BaseSLAMEngine)
        
        # Verify it has required methods (abstract)
        assert hasattr(engine, 'initialize')
        assert hasattr(engine, 'process_frame')
        assert hasattr(engine, 'get_pose')
        assert hasattr(engine, 'reset')
    
    def test_get_map_state_default(self):
        """Test default map state returns valid MapState."""
        engine = Mock(spec=BaseSLAMEngine)
        
        # Create a minimal implementation for testing
        class TestEngine(BaseSLAMEngine):
            def initialize(self): return True
            def process_frame(self, frame, timestamp=0.0): 
                return PoseEstimate(timestamp=timestamp)
            def get_pose(self): return None
            def reset(self): pass
        
        engine = TestEngine()
        state = engine.get_map_state()
        
        assert isinstance(state, MapState)
        assert state.num_keyframes == 0
    
    def test_get_pose_history_empty(self):
        """Test empty pose history returns empty list."""
        class TestEngine(BaseSLAMEngine):
            def initialize(self): return True
            def process_frame(self, frame, timestamp=0.0): 
                return PoseEstimate(timestamp=timestamp)
            def get_pose(self): return None
            def reset(self): pass
        
        engine = TestEngine()
        poses = engine.get_pose_history(limit=100)
        
        assert isinstance(poses, list)
        assert len(poses) == 0
    
    def test_is_tracking_default(self):
        """Test default tracking state."""
        class TestEngine(BaseSLAMEngine):
            def initialize(self): return True
            def process_frame(self, frame, timestamp=0.0): 
                return PoseEstimate(timestamp=timestamp)
            def get_pose(self): return None
            def reset(self): pass
        
        engine = TestEngine()
        
        # Should not be tracking by default
        assert not engine.is_tracking()


# Integration test with mock video data
class TestFrameProcessing:
    """Integration tests for frame processing pipeline."""
    
    def test_process_frame_with_mock_engine(self):
        """Test complete frame processing flow with mock SLAM engine."""
        # Create mock SLAM engine
        class MockSLAMEngine(BaseSLAMEngine):
            def __init__(self):
                self.pose_history = []
                
            def initialize(self) -> bool:
                return True
            
            def process_frame(
                self, 
                frame: np.ndarray, 
                timestamp: float = 0.0
            ) -> PoseEstimate:
                # Simulate pose estimation
                pose = PoseEstimate(
                    position=np.array([0.1 * (timestamp % 10), 
                                       -0.1 * ((timestamp + 1) % 10), 
                                       50.0]),
                    timestamp=timestamp,
                    confidence=0.95
                )
                self.pose_history.append(pose)
                return pose
            
            def get_pose(self):
                if self.pose_history:
                    return self.pose_history[-1]
                return None
            
            def reset(self):
                self.pose_history.clear()
        
        # Create mock frame data
        engine = MockSLAMEngine()
        engine.initialize()
        
        # Process multiple frames
        for i in range(5):
            timestamp = float(i * 0.1)
            pose = engine.process_frame(np.random.randint(0, 255, (480, 640, 3)), timestamp)
            
            assert pose.timestamp == timestamp
            assert pose.confidence == 0.95
        
        # Verify trajectory was recorded
        assert len(engine.pose_history) == 5
        
        # Check trajectory progression
        positions = np.array([p.position for p in engine.pose_history])
        
        # Should have moved approximately 1 meter per frame
        distances = np.linalg.norm(positions[1:] - positions[:-1], axis=1)
        assert all(distances > 0.9 and distances < 1.2), f"Unexpected distances: {distances}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
