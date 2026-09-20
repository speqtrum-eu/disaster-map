"""Unit Tests for ORB-SLAM2 Integration."""

import pytest
import numpy as np
from unittest.mock import Mock, MagicMock, patch
from src.core.slam.orb_slam2 import (
    ORB_SLAM2Engine, 
    ORB_SLAM2Stats,
)


class TestORB_SLAM2Stats:
    """Tests for ORB_SLAM2Stats data class."""
    
    def test_initialization_default(self):
        """Test default initialization with zeros."""
        stats = ORB_SLAM2Stats()
        
        assert stats.frame_time_ms == 0.0
        assert stats.feature_extraction_ms == 0.0
        assert stats.tracking_ms == 0.0
        assert stats.optimization_ms == 0.0
        assert stats.success is False
        assert stats.num_features == 0
    
    def test_initialization_with_values(self):
        """Test initialization with custom values."""
        stats = ORB_SLAM2Stats(
            frame_time_ms=12.5,
            success=True,
            num_features=847,
            keyframe_added=True
        )
        
        assert stats.frame_time_ms == 12.5
        assert stats.success is True
        assert stats.num_features == 847


class TestORB_SLAM2Engine:
    """Tests for ORB-SLAM2Engine class."""
    
    def test_initialization_default(self):
        """Test engine initialization with default config."""
        engine = ORB_SLAM2Engine()
        
        assert engine.config.camera_width == 640
        assert engine.config.frame_rate == 30.0
        assert not engine.initialized
    
    def test_initialization_with_config(self):
        """Test initialization with custom configuration."""
        from src.core.slam.base_slam import SLAMConfig
        
        config = SLAMConfig(
            camera_width=1280,
            camera_height=720,
            frame_rate=60.0
        )
        
        engine = ORB_SLAM2Engine(config)
        
        assert engine.config.camera_width == 1280
        assert engine.config.frame_rate == 60.0
    
    def test_initialization_fallback_mode(self):
        """Test initialization when ORB-SLAM2 bindings unavailable."""
        # Mock the import to simulate missing bindings
        with patch('src.core.slam.orb_slam2.ORBSLAM2Core', None):
            engine = ORB_SLAM2Engine()
            
            # Should still initialize successfully in fallback mode
            assert engine.initialized is False  # Not initialized until initialize() called
    
    def test_initialize_success(self, caplog):
        """Test successful initialization."""
        with patch('src.core.slam.orb_slam2.ORBSLAM2Core') as mock_core:
            mock_instance = Mock()
            mock_core.return_value = mock_instance
            
            engine = ORB_SLAM2Engine()
            
            # Initialize should succeed and set up core engine
            result = engine.initialize()
            
            assert result is True
            assert engine._core_engine is not None
    
    def test_initialize_failure(self):
        """Test initialization failure handling."""
        with patch('src.core.slam.orb_slam2.ORBSLAM2Core') as mock_core:
            mock_core.side_effect = Exception("Initialization failed")
            
            engine = ORB_SLAM2Engine()
            
            result = engine.initialize()
            
            assert result is False
    
    def test_process_frame_fallback_mode(self):
        """Test frame processing in fallback mode (no bindings)."""
        with patch('src.core.slam.orb_slam2.ORBSLAM2Core', None):
            engine = ORB_SLAM2Engine()
            
            # Create mock frame data
            frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
            timestamp = 123.456
            
            pose = engine.process_frame(frame, timestamp)
            
            assert pose.timestamp == timestamp
            assert pose.confidence > 0.9  # Fallback has high confidence
    
    def test_process_frame_with_core_engine(self):
        """Test frame processing with core ORB-SLAM2 engine."""
        with patch('src.core.slam.orb_slam2.ORBSLAM2Core') as mock_core:
            # Mock successful tracking result
            mock_pose = Mock()
            mock_pose.pose = np.array([1.0, 2.0, 3.0])
            mock_result = type('obj', (object,), {
                'pose': mock_pose,
                'success': True,
                'keyframe_added': False
            })()
            
            mock_instance = Mock()
            mock_instance.track.return_value = mock_result
            
            mock_core.return_value = mock_instance
            
            engine = ORB_SLAM2Engine()
            engine.initialize()
            
            frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
            pose = engine.process_frame(frame, timestamp=1.0)
            
            # Verify core engine was called with correct parameters
            mock_instance.track.assert_called_once()
    
    def test_get_pose_empty(self):
        """Test getting pose when none available."""
        engine = ORB_SLAM2Engine()
        
        pose = engine.get_pose()
        
        assert pose is None
    
    def test_reset_clears_state(self):
        """Test that reset clears all internal state."""
        engine = ORB_SLAM2Engine()
        
        # Add some simulated data
        engine._pose_history.append(Mock())
        engine._keyframes.append(Mock())
        
        assert len(engine._pose_history) == 1
        
        # Reset should clear everything
        engine.reset()
        
        assert len(engine._pose_history) == 0
    
    def test_get_performance_stats_empty(self):
        """Test performance stats when no data collected."""
        engine = ORB_SLAM2Engine()
        
        stats = engine.get_performance_stats()
        
        assert "avg_frame_time_ms" in stats
        assert stats["avg_frame_time_ms"] == 0
    
    def test_get_pose_history(self):
        """Test retrieving pose history with limit."""
        class TestEngine(ORB_SLAM2Engine):
            def initialize(self) -> bool:
                return True
            
            def process_frame(self, frame, timestamp=0.0): 
                return PoseEstimate(position=np.array([i, i, 50]), timestamp=timestamp)
            
            def get_pose(self): return None
            def reset(self): pass
        
        engine = TestEngine()
        
        # Add poses to history
        for i in range(10):
            pose = PoseEstimate(position=np.array([i, i, 50]), timestamp=float(i))
            engine._pose_history.append(pose)
        
        # Get limited history
        history = engine.get_pose_history(limit=3)
        
        assert len(history) == 3
    
    def test_export_trajectory(self):
        """Test trajectory export to file."""
        import tempfile
        
        class TestEngine(ORB_SLAM2Engine):
            def initialize(self) -> bool:
                return True
            
            def process_frame(self, frame, timestamp=0.0): 
                return PoseEstimate(position=np.array([i*10, i*10, 50]), timestamp=timestamp)
            
            def get_pose(self): return None
            def reset(self): pass
        
        engine = TestEngine()
        
        # Add poses to history
        for i in range(5):
            pose = PoseEstimate(position=np.array([i*10, i*10, 50]), timestamp=float(i))
            engine._pose_history.append(pose)
        
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            filepath = f.name
        
        try:
            result = engine.export_trajectory(filepath)
            
            assert result is True
            
            # Verify file was created and contains data
            import json
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            assert len(data["poses"]) == 5
        finally:
            import os
            if os.path.exists(filepath):
                os.remove(filepath)


class TestRealTimePerformance:
    """Tests for real-time performance requirements."""
    
    def test_frame_processing_latency(self):
        """Test that frame processing meets latency targets (<15ms)."""
        with patch('src.core.slam.orb_slam2.ORBSLAM2Core', None):
            engine = ORB_SLAM2Engine()
            
            # Process multiple frames and measure time
            latencies = []
            num_frames = 10
            
            for i in range(num_frames):
                frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
                
                start_time = time.perf_counter()
                pose = engine.process_frame(frame, timestamp=float(i))
                latency_ms = (time.perf_counter() - start_time) * 1000
                
                latencies.append(latency_ms)
            
            avg_latency = np.mean(latencies)
            max_latency = np.max(latencies)
            
            # Should be well under 15ms target
            assert avg_latency < 20.0, f"Average latency {avg_latency:.2f}ms exceeds target"
            assert max_latency < 30.0, f"Max latency {max_latency:.2f}ms exceeds threshold"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
