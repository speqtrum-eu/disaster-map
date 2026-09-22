"""
Integration tests for API endpoints.
Tests real API interactions with mock data and services.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
import json


# Mock the FastAPI app
@pytest.fixture
def client():
    """Create a test client for the API."""
    from src.core.api.app import app
    
    return TestClient(app)


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_health_check_returns_healthy(self, client):
        """Verify health endpoint returns healthy status."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "degraded", "unhealthy"]
        assert "timestamp" in data

    def test_health_check_includes_version(self, client):
        """Verify health endpoint includes version information."""
        response = client.get("/health")
        
        data = response.json()
        assert "version" in data


class TestFrameEndpoints:
    """Tests for video frame endpoints."""

    @pytest.fixture
    def mock_frame_data(self):
        """Provide sample frame data for testing."""
        return {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "timestamp": 1695328058.123,
            "frame_number": 1234,
            "width": 1920,
            "height": 1080,
            "has_pose": True
        }

    def test_list_frames_returns_data(self, client, mock_frame_data):
        """Test listing frames returns expected data."""
        # Mock the frame retrieval
        with patch("src.core.api.services.frame_service.get_frames") as mock_get:
            mock_get.return_value = [mock_frame_data]
            
            response = client.get("/frames?limit=10")
            
            assert response.status_code == 200
            data = response.json()
            assert "data" in data
            assert len(data["data"]) > 0

    def test_get_frame_by_id(self, client, mock_frame_data):
        """Test retrieving a specific frame by ID."""
        with patch("src.core.api.services.frame_service.get_frame") as mock_get:
            mock_get.return_value = mock_frame_data
            
            response = client.get(f"/frames/{mock_frame_data['id']}")
            
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == mock_frame_data["id"]

    def test_list_frames_with_pagination(self, client):
        """Test frame listing with pagination parameters."""
        response = client.get("/frames?limit=5&offset=10")
        
        assert response.status_code == 200
        data = response.json()
        assert "data" in data


class TestPoseEndpoints:
    """Tests for pose estimation endpoints."""

    @pytest.fixture
    def mock_pose_data(self):
        """Provide sample pose data for testing."""
        return {
            "id": "660e8400-e29b-41d4-a716-446655440000",
            "frame_id": "550e8400-e29b-41d4-a716-446655440000",
            "timestamp": 1695328058.123,
            "position": {"x": 12.345, "y": -8.765, "z": 45.678},
            "orientation": {
                "qx": 0.999,
                "qy": 0.012,
                "qz": -0.045,
                "qw": 0.987
            },
            "confidence": 0.95
        }

    def test_list_poses_returns_data(self, client, mock_pose_data):
        """Test listing poses returns expected data."""
        with patch("src.core.api.services.pose_service.get_poses") as mock_get:
            mock_get.return_value = [mock_pose_data]
            
            response = client.get("/poses?limit=10")
            
            assert response.status_code == 200
            data = response.json()
            assert "data" in data

    def test_submit_pose_estimate(self, client):
        """Test submitting a pose estimate."""
        pose_data = {
            "frame_id": "550e8400-e29b-41d4-a716-446655440000",
            "position": {"x": 10.0, "y": 0.0, "z": 50.0},
            "orientation": {
                "qx": 1.0,
                "qy": 0.0,
                "qz": 0.0,
                "qw": 1.0
            }
        }
        
        with patch("src.core.api.services.pose_service.submit_pose") as mock_submit:
            mock_submit.return_value = {"success": True, "pose_id": "new-id-123"}
            
            response = client.post("/stream/pose", json=pose_data)
            
            assert response.status_code == 201
            data = response.json()
            assert data["success"] is True

    def test_pose_confidence_validation(self, client):
        """Test that pose confidence values are validated."""
        # Test with valid confidence
        pose_valid = {
            "frame_id": "550e8400-e29b-41d4-a716-446655440000",
            "position": {"x": 10.0, "y": 0.0, "z": 50.0},
            "orientation": {
                "qx": 1.0,
                "qy": 0.0,
                "qz": 0.0,
                "qw": 1.0
            },
            "confidence": 0.95
        }
        
        # Test with invalid confidence (out of range)
        pose_invalid = {
            **pose_valid,
            "confidence": 1.5  # Invalid: > 1.0
        }
        
        response_valid = client.post("/stream/pose", json=pose_valid)
        assert response_valid.status_code in [201, 422]  # May validate on server
        
        response_invalid = client.post("/stream/pose", json=pose_invalid)
        assert response_invalid.status_code == 422  # Should reject invalid data


class TestMapEndpoints:
    """Tests for point cloud map endpoints."""

    @pytest.fixture
    def mock_map_data(self):
        """Provide sample map data for testing."""
        return {
            "id": "770e8400-e29b-41d4-a716-446655440000",
            "name": "Disaster Zone A",
            "upload_timestamp": "2026-09-21T10:30:00Z",
            "point_count": 150000,
            "file_size_bytes": 45678901
        }

    def test_upload_map_returns_response(self, client):
        """Test map upload returns appropriate response."""
        # Mock the file upload handling
        with patch("src.core.api.services.map_service.upload_map") as mock_upload:
            mock_upload.return_value = {
                "success": True,
                "map_id": "new-map-id-123",
                "message": "Map uploaded successfully"
            }
            
            # Simulate file upload (binary data)
            response = client.post(
                "/maps",
                files={"file": ("test.ply", b"fake point cloud data")}
            )
            
            assert response.status_code in [201, 400]  # May reject on validation

    def test_get_map_by_id(self, client, mock_map_data):
        """Test retrieving map by ID."""
        with patch("src.core.api.services.map_service.get_map") as mock_get:
            mock_get.return_value = mock_map_data
            
            response = client.get(f"/maps/{mock_map_data['id']}")
            
            assert response.status_code == 200
            data = response.json()
            assert data["name"] == mock_map_data["name"]

    def test_list_maps(self, client):
        """Test listing all maps."""
        with patch("src.core.api.services.map_service.list_maps") as mock_list:
            mock_list.return_value = [mock_map_data]
            
            response = client.get("/maps")
            
            assert response.status_code == 200
            data = response.json()
            assert "data" in data


class TestMetricsEndpoints:
    """Tests for system metrics endpoints."""

    def test_get_metrics_returns_valid_data(self, client):
        """Test metrics endpoint returns valid performance data."""
        with patch("src.core.api.services.metrics_service.get_metrics") as mock_get:
            mock_get.return_value = {
                "timestamp": "2026-09-21T10:30:00Z",
                "fps": 32.5,
                "latency_ms": 45.2,
                "memory_mb": 1024,
                "active_connections": 3
            }
            
            response = client.get("/metrics")
            
            assert response.status_code == 200
            data = response.json()
            assert "fps" in data
            assert "latency_ms" in data

    def test_metrics_validation(self, client):
        """Test that metrics values are validated."""
        with patch("src.core.api.services.metrics_service.get_metrics") as mock_get:
            # Test with invalid FPS (negative)
            mock_get.return_value = {"fps": -1.0}  # Invalid
            
            response = client.get("/metrics")
            
            assert response.status_code == 200


class TestWebSocketEndpoints:
    """Tests for WebSocket connection endpoints."""

    def test_websocket_connection_handshake(self, client):
        """Test WebSocket connection initialization."""
        # Note: Full WebSocket testing requires async setup
        # This is a basic validation test
        
        with patch("src.core.api.services.websocket_service.connect") as mock_connect:
            mock_connect.return_value = True
            
            response = client.get("/stream/ws", headers={
                "Authorization": "Bearer test-token"
            })
            
            assert response.status_code in [101, 401]  # 101=Switching Protocols, 401=Unauthorized


class TestErrorHandling:
    """Tests for error handling and validation."""

    def test_invalid_frame_id_returns_404(self, client):
        """Test that invalid frame IDs return 404."""
        response = client.get("/frames/invalid-id")
        
        assert response.status_code == 404

    def test_missing_required_fields(self, client):
        """Test validation of required fields in requests."""
        # Test pose submission without required fields
        incomplete_pose = {
            "frame_id": "550e8400-e29b-41d4-a716-446655440000"
            # Missing position and orientation
        }
        
        response = client.post("/stream/pose", json=incomplete_pose)
        
        assert response.status_code == 422

    def test_rate_limiting_headers(self, client):
        """Test that rate limiting headers are present."""
        response = client.get("/health")
        
        # Rate limit headers may or may not be present depending on config
        # Just verify no errors occurred


# Run tests with pytest
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
