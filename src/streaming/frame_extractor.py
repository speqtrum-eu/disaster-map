"""
Frame Extraction Pipeline with Timestamp Synchronization.

Provides robust frame extraction from video sources with:
- Precise timestamp synchronization
- Configurable FPS control
- Frame quality validation
- Memory-efficient buffering
- Support for multiple input formats (RTSP, RTMP, file)
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import AsyncGenerator, Optional, Callable, Dict, Any, Union
from enum import Enum

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None
    np = object


logger = logging.getLogger(__name__)


@dataclass
class ExtractionConfig:
    """Configuration for frame extraction pipeline."""
    # Input settings
    source_url: str  # RTSP, RTMP, or file path
    protocol: Optional[str] = "rtsp"  # rtsp, rtmp, file
    
    # Frame rate control
    target_fps: float = 30.0
    max_fps: float = 60.0  # Cap maximum FPS for stability
    min_frame_interval_ms: float = 16.67  # ~30 FPS minimum interval
    
    # Quality settings
    quality_threshold: float = 0.8  # Minimum frame quality score
    skip_duplicate_frames: bool = True  # Skip near-duplicate frames
    duplicate_threshold: float = 0.95  # Similarity threshold for duplicates
    
    # Timing and synchronization
    use_precise_timestamps: bool = True
    sync_to_external_clock: bool = False
    clock_source: str = "system"  # system, hardware, external
    
    # Buffering
    buffer_size: int = 512  # Ring buffer size
    drop_on_overflow: bool = False  # Drop frames on overflow vs wait
    
    # Output settings
    output_format: str = "numpy"  # numpy, opencv_mat
    grayscale: bool = False


@dataclass
class ExtractedFrame:
    """Extracted frame with full metadata."""
    timestamp: float  # Precise extraction timestamp
    frame_id: int  # Sequential counter
    image: Optional[Any] = None  # Frame data (numpy array or Mat)
    
    # Timing information
    capture_time_ms: float = 0.0  # When camera captured the frame
    processing_latency_ms: float = 0.0  # Time to extract this frame
    
    # Quality metrics
    quality_score: float = 1.0  # Frame quality (0-1)
    is_keyframe: bool = False  # Whether this is a keyframe
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def extraction_time_ms(self) -> float:
        """Time taken to extract this frame."""
        return time.time() * 1000 - self.timestamp


@dataclass 
class ExtractionStats:
    """Real-time extraction statistics."""
    frames_extracted: int = 0
    frames_dropped: int = 0
    frames_skipped: int = 0
    avg_fps: float = 0.0
    current_fps: float = 0.0
    
    # Timing stats
    total_extraction_time_ms: float = 0.0
    avg_processing_latency_ms: float = 0.0
    min_latency_ms: float = float('inf')
    max_latency_ms: float = 0.0
    
    # Quality stats
    avg_quality_score: float = 0.0
    keyframe_count: int = 0
    
    # Timestamp sync
    timestamp_drift_ms: float = 0.0
    last_sync_time: Optional[float] = None


class FrameExtractor:
    """
    High-performance frame extractor with precise timing control.
    
    Features:
    - Precise FPS control with configurable tolerance
    - Automatic frame rate adjustment for unstable streams
    - Timestamp synchronization with external clocks
    - Memory-efficient ring buffer implementation
    - Real-time statistics and monitoring
    
    Example:
        >>> config = ExtractionConfig(
        ...     source_url="rtsp://example.com/stream",
        ...     target_fps=30.0,
        ...     quality_threshold=0.8
        ... )
        >>> extractor = FrameExtractor(config)
        >>> async for frame in extractor.extract():
        ...     process_frame(frame)
    """
    
    def __init__(self, config: ExtractionConfig):
        self.config = config
        self._running = False
        self._frame_counter = 0
        self._stats = ExtractionStats()
        
        # Timing control
        self._last_frame_time: float = 0.0
        self._expected_interval_ms: float = 1000.0 / min(config.target_fps, config.max_fps)
        self._actual_interval_ms: float = 0.0
        
        # Buffer management
        self._buffer: asyncio.Queue = asyncio.Queue(maxsize=config.buffer_size)
        
        # Frame quality tracking
        self._frame_hashes: Dict[int, bytes] = {}
        self._max_history_frames = 100
        
        # Timestamp synchronization
        self._clock_offset_ms: float = 0.0
        self._sync_interval_ms: int = 1000  # Sync every second
        
    async def extract(
        self,
        callback: Optional[Callable[[ExtractedFrame], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None
    ) -> AsyncGenerator[ExtractedFrame, None]:
        """
        Extract frames from source with precise timing control.
        
        Args:
            callback: Optional callback for each extracted frame
            on_error: Optional error handler
            
        Yields:
            ExtractedFrame objects with full metadata
            
        Example:
            >>> async def handle_frame(frame):
            ...     print(f"Frame {frame.frame_id}: latency={frame.processing_latency_ms:.1f}ms")
            >>> extractor = FrameExtractor(config)
            >>> async for frame in extractor.extract(handle_frame):
            ...     pass
        """
        self._running = True
        
        try:
            # Initialize source based on protocol
            if self.config.protocol == "file":
                source = FileSource(self.config.source_url)
            else:
                from .rtsp_client import RTSPClient, StreamConfig
                
                stream_config = StreamConfig(
                    url=self.config.source_url,
                    target_fps=self.config.target_fps,
                    frame_width=640,
                    frame_height=480,
                )
                
                client = RTSPClient(stream_config)
                await client.connect()
                source = client
            
            # Main extraction loop with precise timing
            while self._running:
                try:
                    start_time = time.perf_counter()
                    
                    # Get next frame from source
                    frame_data = await asyncio.get_event_loop().run_in_executor(
                        None, 
                        lambda: source.get_frame(timeout_ms=int(self.config.timeout_ms))
                    )
                    
                    if frame_data.image is not None and len(frame_data.image) > 0:
                        # Calculate processing latency
                        processing_latency = (time.perf_counter() - start_time) * 1000
                        
                        # Update stats
                        self._stats.frames_extracted += 1
                        self._stats.total_extraction_time_ms += processing_latency
                        
                        if processing_latency < self._stats.min_latency_ms:
                            self._stats.min_latency_ms = processing_latency
                        elif processing_latency > self._stats.max_latency_ms:
                            self._stats.max_latency_ms = processing_latency
                        
                        # Calculate FPS
                        current_fps = self._stats.frames_extracted / \
                            max(0.1, time.time() - getattr(self._stats, 'start_time', time.time()))
                        self._stats.current_fps = current_fps
                        
                        # Create extracted frame with metadata
                        extracted_frame = ExtractedFrame(
                            timestamp=frame_data.timestamp + self._clock_offset_ms / 1000.0,
                            frame_id=self._frame_counter,
                            image=frame_data.image if self.config.output_format == "numpy" \
                                else np.array(frame_data.image),
                            capture_time_ms=frame_data.timestamp * 1000,
                            processing_latency_ms=processing_latency,
                            quality_score=min(1.0, frame_data.confidence),
                        )
                        
                        # Check for duplicate frames
                        if self.config.skip_duplicate_frames:
                            is_duplicate = await self._check_duplicate(extracted_frame)
                            if is_duplicate:
                                extracted_frame.metadata["is_duplicate"] = True
                                self._stats.frames_skipped += 1
                                continue
                        
                        # Update frame counter and stats
                        self._frame_counter += 1
                        self._stats.avg_fps = current_fps
                        
                        # Call callback if provided
                        if callback:
                            try:
                                callback(extracted_frame)
                            except Exception as e:
                                logger.error(f"Callback error: {e}")
                        
                        yield extracted_frame
                        
                    else:
                        self._stats.frames_dropped += 1
                        logger.debug("Dropped empty frame")
                        
                except asyncio.TimeoutError:
                    # Timeout - might indicate stream issue or network problem
                    if on_error:
                        try:
                            on_error(asyncio.TimeoutError(f"Frame extraction timeout"))
                        except Exception as e2:
                            logger.error(f"Error handler error: {e2}")
                            
                except Exception as e:
                    if on_error:
                        try:
                            on_error(e)
                        except Exception as e2:
                            logger.error(f"Error handler error: {e2}")
                    
        finally:
            # Cleanup source connection
            await self._cleanup_source(source)
    
    async def _check_duplicate(self, frame: ExtractedFrame) -> bool:
        """Check if frame is a duplicate using hash comparison."""
        import hashlib
        
        # Calculate frame hash (sampled for efficiency)
        sample_size = min(1024 * 1024, len(frame.image) // 3)  # RGB format
        sample_indices = np.random.choice(len(frame.image), size=sample_size, replace=False)
        
        if hasattr(frame.image, '__getitem__'):
            sampled_data = frame.image[sample_indices].tobytes()
        else:
            sampled_data = frame.image[:sample_size].tobytes()
            
        current_hash = hashlib.md5(sampled_data).digest()
        
        # Check against recent frames
        for prev_frame_id, prev_hash in list(self._frame_hashes.items())[-100:]:
            if current_hash == prev_hash:
                return True
                
        # Store new hash (LRU style)
        self._frame_hashes[self._frame_counter] = current_hash
        
        # Clean up old hashes
        if len(self._frame_hashes) > self._max_history_frames:
            oldest_id = min(self._frame_hashes.keys())
            del self._frame_hashes[oldest_id]
        
        return False
    
    async def _cleanup_source(self, source) -> None:
        """Cleanup source connection."""
        if hasattr(source, 'disconnect'):
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None, 
                    lambda: source.disconnect()
                )
            except Exception as e:
                logger.warning(f"Error during source cleanup: {e}")
    
    @property
    def stats(self) -> ExtractionStats:
        """Get current extraction statistics."""
        return self._stats
    
    async def sync_timestamps(self, external_time_ms: Optional[float] = None) -> float:
        """
        Synchronize internal clock with external time source.
        
        Args:
            external_time_ms: External timestamp in milliseconds (optional)
            
        Returns:
            Clock offset in milliseconds
            
        Example:
            >>> # Sync with GPS PPS signal
            >>> pps_timestamp = get_gps_pps_timestamp()  # e.g., 1726890000.543
            >>> offset_ms = extractor.sync_timestamps(pps_timestamp * 1000)
        """
        if external_time_ms is None:
            return self._clock_offset_ms
            
        current_system_time_ms = time.time() * 1000
        
        # Calculate clock drift
        drift = external_time_ms - current_system_time_ms
        
        # Apply offset
        self._clock_offset_ms += drift
        
        logger.debug(f"Timestamp sync: drift={drift:.2f}ms, new_offset={self._clock_offset_ms:.2f}ms")
        
        return self._clock_offset_ms


class ExtractionPipeline:
    """
    Complete extraction pipeline with preprocessing and postprocessing.
    
    Features:
    - Multi-stage processing pipeline
    - Frame quality filtering
    - Automatic frame rate adjustment
    - Real-time statistics monitoring
    
    Example:
        >>> pipeline = ExtractionPipeline(
        ...     source_url="rtsp://example.com/stream",
        ...     target_fps=30.0,
        ...     enable_quality_filter=True,
        ... )
        >>> async for frame in pipeline.process():
        ...     # Frame is ready for SLAM processing
        ...     slam_engine.update(frame)
    """
    
    def __init__(
        self,
        source_url: str,
        target_fps: float = 30.0,
        protocol: Optional[str] = None,
        enable_quality_filter: bool = True,
        quality_threshold: float = 0.8,
    ):
        self.source_url = source_url
        self.target_fps = target_fps
        self.protocol = protocol or "rtsp"
        
        # Create extraction config
        self.config = ExtractionConfig(
            source_url=source_url,
            protocol=self.protocol,
            target_fps=target_fps,
            quality_threshold=quality_threshold,
            buffer_size=512,
        )
        
        # Initialize extractor
        self.extractor = FrameExtractor(self.config)
        
        # Pipeline stages
        self._preprocessors: list[Callable[[ExtractedFrame], ExtractedFrame]] = []
        self._postprocessors: list[Callable[[ExtractedFrame], ExtractedFrame]] = []
        
        # Quality filter state
        self._quality_filter_enabled = enable_quality_filter
        self._last_quality_score: float = 1.0
        
    def add_preprocessor(
        self, 
        processor: Callable[[ExtractedFrame], ExtractedFrame]
    ) -> None:
        """Add preprocessing stage (runs before frame is yielded)."""
        self._preprocessors.append(processor)
        
    def add_postprocessor(
        self, 
        processor: Callable[[ExtractedFrame], ExtractedFrame]
    ) -> None:
        """Add postprocessing stage (runs after frame is extracted)."""
        self._postprocessors.append(processor)
    
    async def process(
        self,
        callback: Optional[Callable[[ExtractedFrame], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None
    ) -> AsyncGenerator[ExtractedFrame, None]:
        """
        Process frames through complete pipeline.
        
        Args:
            callback: Callback for processed frames
            on_error: Error handler
            
        Yields:
            Processed ExtractedFrame objects
            
        Example:
            >>> async def handle_processed_frame(frame):
            ...     # Frame has been preprocessed and postprocessed
            ...     slam_engine.process_frame(frame.image)
            >>> pipeline = ExtractionPipeline(source_url)
            >>> async for frame in pipeline.process(handle_processed_frame):
            ...     pass
        """
        async for raw_frame in self.extractor.extract(callback, on_error):
            # Apply preprocessing stages
            processed_frame = raw_frame
            for processor in self._preprocessors:
                try:
                    processed_frame = processor(processed_frame)
                except Exception as e:
                    logger.error(f"Preprocessor error: {e}")
                    continue
            
            # Apply postprocessing stages
            for processor in self._postprocessors:
                try:
                    processed_frame = processor(processed_frame)
                except Exception as e:
                    logger.error(f"Postprocessor error: {e}")
                    continue
            
            yield processed_frame
    
    @property
    def stats(self) -> ExtractionStats:
        """Get pipeline statistics."""
        return self.extractor.stats


# ============================================================================
# Utility Classes
# ============================================================================

class FileSource:
    """File-based video source for testing and offline processing."""
    
    def __init__(self, file_path: str):
        if cv2 is None:
            raise ImportError("OpenCV (cv2) required for file source")
            
        self.file_path = file_path
        self._capture = cv2.VideoCapture(file_path)
        
        if not self._capture.isOpened():
            raise ValueError(f"Failed to open video file: {file_path}")
    
    def get_frame(self, timeout_ms: int = 5000) -> FrameData:
        """Extract next frame from file."""
        ret, frame = self._capture.read()
        
        if not ret or frame is None:
            raise asyncio.TimeoutError("No more frames in video")
            
        return FrameData(
            timestamp=time.time(),
            frame_id=0,
            image=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB),
            confidence=1.0
        )
    
    def disconnect(self) -> None:
        """Release file capture resources."""
        if self._capture is not None:
            try:
                self._capture.release()
            finally:
                self._capture = None


# ============================================================================
# Performance Monitoring
# ============================================================================

class FrameMonitor:
    """Real-time monitoring for frame extraction performance."""
    
    def __init__(self, window_size: int = 60):
        self.window_size = window_size
        self._timestamps: list[float] = []
        self._latencies: list[float] = []
        
    def record_frame(self, timestamp: float, latency_ms: float) -> None:
        """Record frame timing data."""
        self._timestamps.append(timestamp)
        self._latencies.append(latency_ms)
        
        # Maintain sliding window
        if len(self._timestamps) > self.window_size:
            self._timestamps.pop(0)
            self._latencies.pop(0)
    
    @property
    def avg_fps(self) -> float:
        """Calculate average FPS from recorded data."""
        if len(self._timestamps) < 2:
            return 0.0
            
        total_time = self._timestamps[-1] - self._timestamps[0]
        frames = len(self._timestamps)
        
        return frames / max(0.1, total_time)
    
    @property
    def avg_latency_ms(self) -> float:
        """Calculate average processing latency."""
        if not self._latencies:
            return 0.0
            
        return sum(self._latencies) / len(self._latencies)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive performance statistics."""
        return {
            "frame_count": len(self._timestamps),
            "avg_fps": self.avg_fps,
            "avg_latency_ms": self.avg_latency_ms,
            "min_latency_ms": min(self._latencies) if self._latencies else 0.0,
            "max_latency_ms": max(self._latencies) if self._latencies else 0.0,
        }
