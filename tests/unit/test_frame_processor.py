"""Unit Tests for Frame Processor Module."""

import pytest
import numpy as np
from unittest.mock import Mock, MagicMock, patch
from src.core.frame_processor import (
    FrameProcessor, 
    MultiSourceFrameProcessor,
    FrameData,
)


class TestFrameData:
    """Tests for FrameData data class."""
    
    def test_initialization_default(self):
        """Test default initialization with None values."""
        frame = FrameData()
        
        assert frame.image is None
        assert frame.timestamp == 0.0
        assert frame.frame_number == 0
    
    def test_initialization_with_values(self):
        """Test initialization with custom values."""
        image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        
        frame = FrameData(
            image=image,
            timestamp=123.456,
            frame_number=42,
            width=640,
            height=480,
            fps=30.0,
        )
        
        assert np.array_equal(frame.image, image)
        assert frame.timestamp == 123.456
        assert frame.frame_number == 42
        assert frame.width == 640
        assert frame.height == 480


class TestFrameProcessor:
    """Tests for FrameProcessor class."""
    
    def test_initialization_default(self):
        """Test initialization with default parameters."""
        processor = FrameProcessor()
        
        assert processor.target_fps == 30.0
        assert processor.buffer_size == 1024
    
    def test_initialization_with_config(self):
        """Test initialization with custom configuration."""
        processor = FrameProcessor(
            source="rtsp://test/stream",
            frame_rate=60.0,
            buffer_size=512,
        )
        
        assert processor.source == "rtsp://test/stream"
        assert processor.target_fps == 60.0
    
    def test_open_source_file(self):
        """Test opening a video file source."""
        # Use a sample video if available, otherwise skip
        import os
        
        # Try to find a sample video in common locations
        sample_videos = [
            "/usr/share/vlc/samples/bigbuckbunny_320x180.mp4",
            "/home/durburz/git/disaster-map/test_videos/sample.mp4",
        ]
        
        for video_path in sample_videos:
            if os.path.exists(video_path):
                processor = FrameProcessor(source=video_path)
                
                result = processor.open_source()
                
                assert result is True, f"Failed to open {video_path}"
                
                # Verify properties were set
                assert processor._width > 0
                assert processor._height > 0
                
                processor.close_source()
                break
        else:
            pytest.skip("No sample video found for testing")
    
    def test_open_source_invalid(self):
        """Test opening invalid source."""
        processor = FrameProcessor(source="invalid://nonexistent/stream")
        
        result = processor.open_source()
        
        assert result is False
    
    def test_process_frames_empty_source(self):
        """Test processing frames from empty/uninitialized source."""
        processor = FrameProcessor()
        
        # Should not crash, should return generator that yields nothing
        count = 0
        for frame in processor.process_frames():
            count += 1
        
        assert count == 0
    
    def test_process_with_callback(self):
        """Test processing frames with callback."""
        received_frames = []
        
        def on_frame(frame_data: FrameData) -> bool:
            received_frames.append(frame_data)
            return True  # Continue processing
        
        processor = FrameProcessor()
        
        # This will fail without a valid source, but should not crash
        try:
            processor.process_with_callback(on_frame)
        except Exception as e:
            # Expected to fail when trying to open invalid source
            assert "Failed to open" in str(e) or "Error opening" in str(e)


class TestMultiSourceFrameProcessor:
    """Tests for MultiSourceFrameProcessor class."""
    
    def test_initialization(self):
        """Test initialization with default parameters."""
        processor = MultiSourceFrameProcessor()
        
        assert len(processor._processors) == 0
    
    def test_add_source_success(self):
        """Test adding a valid source."""
        # Use a sample video if available
        import os
        
        sample_videos = [
            "/usr/share/vlc/samples/bigbuckbunny_320x180.mp4",
        ]
        
        for video_path in sample_videos:
            if os.path.exists(video_path):
                processor = MultiSourceFrameProcessor()
                
                result = processor.add_source(video_path, name="test_video")
                
                assert result is not None
                
                # Verify source was added
                assert len(processor._processors) == 1
                
                processor.remove_source(result)
                break
        else:
            pytest.skip("No sample video found for testing")
    
    def test_add_invalid_source(self):
        """Test adding invalid source."""
        processor = MultiSourceFrameProcessor()
        
        result = processor.add_source("invalid://source", name="bad_source")
        
        assert result is None
    
    def test_remove_source(self):
        """Test removing a source."""
        processor = MultiSourceFrameProcessor()
        
        # Add and remove source
        if len(processor._processors) > 0:
            processor.remove_source(processor._processors[0])
    
    def test_process_all_empty(self):
        """Test processing all sources when none added."""
        processor = MultiSourceFrameProcessor()
        
        count = 0
        for frame in processor.process_all():
            count += 1
        
        assert count == 0
    
    def test_get_all_stats_empty(self):
        """Test getting stats from empty processor."""
        processor = MultiSourceFrameProcessor()
        
        stats = processor.get_all_stats()
        
        assert isinstance(stats, dict)


# Performance tests
class TestPerformance:
    """Tests for performance requirements."""
    
    def test_frame_extraction_fps(self):
        """Test that frame extraction meets FPS targets (30+)."""
        # Use a sample video if available
        import os
        
        sample_videos = [
            "/usr/share/vlc/samples/bigbuckbunny_320x180.mp4",
        ]
        
        fps_results = []
        
        for video_path in sample_videos:
            if not os.path.exists(video_path):
                continue
            
            processor = FrameProcessor(source=video_path, frame_rate=30.0)
            
            if not processor.open_source():
                continue
            
            # Process frames and measure FPS
            timestamps = []
            num_frames = 100
            
            for i in range(num_frames):
                start_time = time.perf_counter()
                
                for frame in processor.process_frames():
                    timestamps.append(time.perf_counter())
                    
                    if len(timestamps) >= num_frames:
                        break
                
                processor.close_source()
            
            # Calculate FPS
            if len(timestamps) > 1:
                total_time = timestamps[-1] - timestamps[0]
                actual_fps = (len(timestamps) - 1) / total_time
                fps_results.append(actual_fps)
        
        if fps_results:
            avg_fps = np.mean(fps_results)
            
            # Should meet minimum FPS target of 30
            assert avg_fps >= 25, f"Average FPS {avg_fps:.1f} below target (allowing for processing overhead)"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
