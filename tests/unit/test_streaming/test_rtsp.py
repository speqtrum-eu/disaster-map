"""Unit Tests for RTSP Streaming Module."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from src.streaming.rtsp_client import RTSPClient


class TestRTSPClient:
    """Tests for RTSPClient class."""

    def test_initialization_default(self):
        """Test initialization with default parameters."""
        client = RTSPClient()
        
        assert client.url is None
        assert client.is_connected is False

    def test_initialization_with_url(self):
        """Test initialization with URL parameter."""
        url = "rtsp://example.com/stream"
        client = RTSPClient(url=url)
        
        assert client.url == url

    def test_connect_success_mocked(self):
        """Test connecting to RTSP stream (mocked)."""
        url = "rtsp://example.com/stream"
        client = RTSPClient(url=url)
        
        with patch.object(client, "_connect_internal", return_value=True):
            result = client.connect()
            
            assert result is True

    def test_connect_failure_mocked(self):
        """Test connecting to RTSP stream fails (mocked)."""
        url = "rtsp://example.com/stream"
        client = RTSPClient(url=url)
        
        with patch.object(client, "_connect_internal", return_value=False):
            result = client.connect()
            
            assert result is False

    def test_disconnect(self):
        """Test disconnecting from RTSP stream."""
        url = "rtsp://example.com/stream"
        client = RTSPClient(url=url)
        
        with patch.object(client, "_disconnect_internal"):
            client.disconnect()


class TestRTSPStreamProperties:
    """Tests for RTSP stream properties."""

    def test_stream_url(self):
        """Test getting stream URL."""
        url = "rtsp://example.com/stream"
        client = RTSPClient(url=url)
        
        assert client.stream_url == url

    def test_connection_status(self):
        """Test connection status."""
        url = "rtsp://example.com/stream"
        client = RTSPClient(url=url)
        
        assert not client.is_connected


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
