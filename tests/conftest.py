"""Pytest Configuration and Fixtures."""

import pytest
import numpy as np
from unittest.mock import Mock, MagicMock, patch


@pytest.fixture(scope="session")
def sample_image():
    """Provide a sample image for testing."""
    return np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)


@pytest.fixture(scope="function")
def mock_pose_data():
    """Provide mock pose data for testing."""
    return {
        "position": [10.5, -20.3, 50.7],
        "orientation": {"x": 0.5, "y": -0.3, "z": 0.1, "w": 0.8},
        "timestamp": 123.456,
        "confidence": 0.95,
    }


@pytest.fixture(scope="function")
def mock_frame_data():
    """Provide mock frame data for testing."""
    import numpy as np
    
    return {
        "image": np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8),
        "timestamp": 123.456,
        "frame_number": 42,
        "width": 640,
        "height": 480,
    }


@pytest.fixture(scope="function")
def mock_slam_engine():
    """Provide a mock SLAM engine for testing."""
    
    class MockSLAMEngine:
        def __init__(self):
            self.pose_history = []
            self.initialized = False
        
        def initialize(self) -> bool:
            self.initialized = True
            return True
        
        def process_frame(
            self, frame: np.ndarray, timestamp: float = 0.0
        ):
            import numpy as np
            
            pose = {
                "position": [timestamp * 0.5, -timestamp * 0.3, 50.0],
                "orientation": {"x": 0.1, "y": -0.2, "z": 0.05, "w": 0.98},
                "timestamp": timestamp,
                "confidence": 0.95,
            }
            
            self.pose_history.append(pose)
            return pose
        
        def get_pose(self):
            if self.pose_history:
                return self.pose_history[-1]
            return None
        
        def reset(self):
            self.pose_history.clear()
    
    return MockSLAMEngine()


@pytest.fixture(scope="function")
def mock_rtsp_client():
    """Provide a mocked RTSP client for testing."""
    
    class MockRTSPClient:
        def __init__(self, url=None):
            self.url = url
            self.is_connected = False
        
        def connect(self):
            self.is_connected = True
            return True
        
        def disconnect(self):
            self.is_connected = False
    
    with patch('src.streaming.rtsp_client.RTSPClient') as mock_class:
        client = MockRTSPClient()
        mock_instance = MagicMock()
        mock_instance.connect.return_value = True
        mock_instance.disconnect.return_value = None
        
        return mock_instance


@pytest.fixture(scope="function")
def sample_trajectory():
    """Provide a sample trajectory for testing."""
    import numpy as np
    
    num_frames = 100
    trajectory = []
    
    x, y, z = 0.0, 0.0, 50.0
    
    for i in range(num_frames):
        dx = np.random.normal(0, 2)
        dy = np.random.normal(0, 2)
        dz = np.random.uniform(-1, 1)
        
        x += dx
        y += dy
        z += dz
        
        trajectory.append({
            "frame": i,
            "position": (x, y, z),
            "timestamp": float(i * 0.1),
        })
    
    return trajectory


@pytest.fixture(scope="function")
def sample_point_cloud():
    """Provide a sample point cloud for testing."""
    import numpy as np
    
    num_points = 1000
    points = np.random.randn(num_points, 3) * 10 + 50
    
    return {
        "points": points,
        "colors": np.random.rand(num_points, 3),
    }


@pytest.fixture(scope="function")
def temp_directory(tmp_path):
    """Provide a temporary directory for test files."""
    return tmp_path / "test_data"


@pytest.fixture(scope="function")
def mock_camera_params():
    """Provide mock camera parameters for testing."""
    return {
        "focal_length": 500.0,
        "principal_point": [320.0, 240.0],
        "distortion_coeffs": [0.0, 0.0, 0.0, 0.0, 0.0],
    }


@pytest.fixture(scope="function")
def mock_keyframe_data():
    """Provide mock keyframe data for testing."""
    import numpy as np
    
    return {
        "timestamp": 123.456,
        "pose": {"x": 10.0, "y": -20.0, "z": 50.0},
        "image": np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8),
        "frame_number": 42,
    }


# Performance test fixtures
@pytest.fixture(scope="function")
def performance_test_config():
    """Provide configuration for performance tests."""
    return {
        "num_iterations": 100,
        "warmup_iterations": 10,
        "target_fps": 30.0,
        "max_latency_ms": 50.0,
    }


# Markers for test categorization
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "unit: Unit tests"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests"
    )
    config.addinivalue_line(
        "markers", "performance: Performance benchmarks"
    )
    config.addinivalue_line(
        "markers", "regression: Regression tests"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers."""
    # Add default marker for all tests
    for item in items:
        if not any(marker in item.keywords for marker in ["unit", "integration", "performance"]):
            item.add_marker(pytest.mark.unit)
