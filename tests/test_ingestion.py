import pytest
import numpy as np
from src.ingestion import FFmpegStreamConsumer

def test_ffmpeg_consumer_initialization():
    # Using a dummy URL - this will fail to connect but we want to check if it raises expected error or handles it
    consumer = FFmpegStreamConsumer("rtsp://dummy_url", "test_stream")
    assert consumer.connect() is False  # Should return False because url is invalid

def test_frame_data_structure():
    from src.ingestion import FrameData
    data = FrameData(timestamp=123.456, data=np.zeros((10, 10, 3), dtype=np.uint8), stream_id="test")
    assert data.stream_id == "test"
    assert data.data.shape == (10, 10, 3)
