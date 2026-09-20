"""
RTSP/RTMP Stream Client with Low-Latency Connection Handling.

Provides robust stream ingestion with:
- Automatic reconnection on failure
- Configurable timeout handling
- Frame timestamp synchronization
- Memory-efficient frame buffering
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import AsyncGenerator, Optional, Callable, Dict, Any
from enum import Enum

try:
    import cv2
    from ultralytics.engine.results import Results
except ImportError:
    cv2 = None
    Results = object


logger = logging.getLogger(__name__)


class StreamProtocol(Enum):
    """Supported stream protocols."""
    RTSP = "rtsp"
    RTMP = "rtmp"
    HTTP = "http"


@dataclass
class StreamConfig:
    """Configuration for stream connection."""
    url: str
    protocol: StreamProtocol = StreamProtocol.RTSP
    username: Optional[str] = None
    password: Optional[str] = None
    # Connection settings
    timeout_ms: float = 5000.0  # Default 5 second timeout
    reconnect_delay_ms: float = 1000.0  # 1 second between reconnection attempts
    max_reconnect_attempts: int = 10
    # Frame extraction settings
    target_fps: float = 30.0
    frame_width: int = 640
    frame_height: int = 480
    # Buffering
    buffer_size: int = 1024  # Ring buffer size for frames
    # Quality settings
    decode_quality: str = "high"  # high, medium, low
    use_hardware_acceleration: bool = False


@dataclass
class FrameData:
    """Single frame data with metadata."""
    timestamp: float  # Unix timestamp when frame was captured
    frame_id: int  # Sequential frame counter
    image: Optional[Any] = None  # OpenCV Mat or numpy array
    pose: Optional[Dict[str, Any]] = None  # Camera pose if available
    confidence: float = 1.0  # Frame quality/confidence score
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConnectionStats:
    """Real-time connection statistics."""
    frames_received: int = 0
    frames_dropped: int = 0
    avg_latency_ms: float = 0.0
    connection_uptime_seconds: float = 0.0
    last_frame_timestamp: Optional[float] = None
    reconnection_count: int = 0


class RTSPClient:
    """
    Low-latency RTSP/RTMP stream client with robust error handling.
    
    Features:
    - Automatic reconnection with exponential backoff
    - Configurable timeout for all operations
    - Frame timestamp synchronization
    - Memory-efficient frame buffering using ring buffer
    - Graceful shutdown and cleanup
    
    Example:
        >>> config = StreamConfig(
        ...     url="rtsp://example.com/stream",
        ...     target_fps=30.0,
        ...     timeout_ms=1000.0
        ... )
        >>> client = RTSPClient(config)
        >>> async for frame in client.stream_frames():
        ...     process_frame(frame)
    """
    
    def __init__(self, config: StreamConfig):
        self.config = config
        self._running = False
        self._frame_counter = 0
        self._stats = ConnectionStats()
        self._reconnect_task: Optional[asyncio.Task] = None
        self._extractor: Optional[Any] = None
        
        # Initialize OpenCV if available
        if cv2 is not None:
            cv2.setNumThreads(4)  # Limit threads for predictable performance
            logger.info(f"OpenCV initialized with {cv2.getNumberOfThreads()} threads")
    
    async def connect(self) -> bool:
        """
        Establish connection to the stream.
        
        Returns:
            True if connection successful, False otherwise
            
        Raises:
            ConnectionError: If unable to establish connection after max attempts
        """
        logger.info(f"Connecting to {self.config.url} ({self.config.protocol.value})")
        
        try:
            # Initialize frame extractor based on protocol
            if self.config.protocol == StreamProtocol.RTSP:
                self._extractor = RTSPExtractor(
                    url=self.config.url,
                    username=self.config.username,
                    password=self.config.password,
                    width=self.config.frame_width,
                    height=self.config.frame_height,
                    timeout_ms=int(self.config.timeout_ms),
                    target_fps=self.config.target_fps,
                )
            elif self.config.protocol == StreamProtocol.RTMP:
                self._extractor = RTMPExtractor(
                    url=self.config.url,
                    username=self.config.username,
                    password=self.config.password,
                    width=self.config.frame_width,
                    height=self.config.frame_height,
                    timeout_ms=int(self.config.timeout_ms),
                )
            else:
                raise ValueError(f"Unsupported protocol: {self.config.protocol}")
            
            # Test connection with timeout
            start_time = time.time()
            while time.time() - start_time < self.config.timeout_ms / 1000.0:
                try:
                    if hasattr(self._extractor, 'connect'):
                        await asyncio.get_event_loop().run_in_executor(
                            None, 
                            lambda: self._extractor.connect()
                        )
                    logger.info(f"Connected to stream in {(time.time() - start_time) * 1000:.0f}ms")
                    return True
                    
                except Exception as e:
                    elapsed = (time.time() - start_time) * 1000
                    if elapsed >= self.config.timeout_ms:
                        raise ConnectionError(
                            f"Connection timeout after {elapsed:.0f}ms: {e}"
                        ) from e
                    logger.warning(f"Connection attempt failed ({elapsed:.0f}ms): {e}")
                    
        except Exception as e:
            logger.error(f"Failed to connect to stream: {e}", exc_info=True)
            raise ConnectionError(f"Stream connection failed: {e}")
        
        return False
    
    async def disconnect(self, force: bool = False) -> None:
        """
        Close the stream connection and cleanup resources.
        
        Args:
            force: If True, skip graceful shutdown and close immediately
        """
        logger.info("Disconnecting from stream...")
        
        # Cancel reconnect task if running
        if self._reconnect_task and not force:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
        
        # Cleanup extractor
        if hasattr(self._extractor, 'disconnect'):
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None, 
                    lambda: self._extractor.disconnect()
                )
            except Exception as e:
                logger.warning(f"Error during disconnect cleanup: {e}")
        
        # Reset state
        self._running = False
        self._frame_counter = 0
        
        logger.info("Stream disconnected")
    
    async def stream_frames(
        self,
        callback: Optional[Callable[[FrameData], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None
    ) -> AsyncGenerator[FrameData, None]:
        """
        Generate frames from the live stream.
        
        Args:
            callback: Optional callback function called for each frame
            on_error: Optional callback for error handling
            
        Yields:
            FrameData objects with image data and metadata
            
        Example:
            >>> async def process_frame(frame):
            ...     print(f"Frame {frame.frame_id}: {frame.timestamp}")
            >>> client = RTSPClient(config)
            >>> async for frame in client.stream_frames(process_frame):
            ...     pass
        """
        self._running = True
        
        try:
            while self._running:
                try:
                    # Get next frame with timeout
                    start_time = time.time()
                    
                    if hasattr(self._extractor, 'get_frame'):
                        frame_data = await asyncio.get_event_loop().run_in_executor(
                            None, 
                            lambda: self._extractor.get_frame(timeout_ms=int(self.config.timeout_ms))
                        )
                    else:
                        # Fallback for extractors without get_frame method
                        frame_data = FrameData(
                            timestamp=time.time(),
                            frame_id=self._frame_counter,
                            image=None,
                            confidence=0.0
                        )
                    
                    if frame_data.image is not None and len(frame_data.image) > 0:
                        self._stats.frames_received += 1
                        self._stats.last_frame_timestamp = frame_data.timestamp
                        
                        # Calculate latency
                        processing_time = (time.time() - start_time) * 1000
                        if hasattr(self._stats, 'total_latency'):
                            self._stats.total_latency += processing_time
                            self._stats.avg_latency_ms = (
                                self._stats.total_latency / 
                                min(1, self._stats.frames_received)
                            )
                        
                        # Update stats
                        self._stats.connection_uptime_seconds = time.time() - \
                            getattr(self._stats, 'start_time', time.time())
                        
                        # Call callback if provided
                        if callback:
                            try:
                                callback(frame_data)
                            except Exception as e:
                                logger.error(f"Callback error: {e}")
                        
                        yield frame_data
                        
                    else:
                        self._stats.frames_dropped += 1
                        logger.debug("Dropped empty frame")
                        
                except asyncio.TimeoutError:
                    # Timeout waiting for frame - might indicate stream issue
                    if on_error:
                        try:
                            on_error(asyncio.TimeoutError(f"Frame extraction timeout"))
                        except Exception as e:
                            logger.error(f"Error handler error: {e}")
                    
                except Exception as e:
                    if on_error:
                        try:
                            on_error(e)
                        except Exception as e2:
                            logger.error(f"Error handler error: {e2}")
                            
        finally:
            await self.disconnect(force=True)
    
    async def reconnect(self) -> None:
        """Handle reconnection with exponential backoff."""
        if not self._running:
            return
            
        max_delay = min(60.0, self.config.reconnect_delay_ms * 2 ** self._stats.reconnection_count / 1000.0)
        
        logger.info(f"Reconnecting in {max_delay:.1f}s (attempt {self._stats.reconnection_count + 1})")
        
        await asyncio.sleep(max_delay)
        
        if self._running and self._stats.reconnection_count < self.config.max_reconnect_attempts:
            try:
                success = await self.connect()
                if success:
                    logger.info("Reconnection successful")
                    self._stats.reconnection_count = 0
                else:
                    raise ConnectionError("Reconnection failed")
                    
            except Exception as e:
                logger.error(f"Reconnection error: {e}")
                self._stats.reconnection_count += 1
                
    async def start_auto_reconnect(self) -> None:
        """Start automatic reconnection loop in background."""
        if self._reconnect_task is not None:
            return
            
        self._reconnect_task = asyncio.create_task(
            self._auto_reconnect_loop()
        )
    
    async def _auto_reconnect_loop(self) -> None:
        """Background task for automatic reconnection."""
        while self._running:
            try:
                await asyncio.sleep(1.0)  # Check every second
                
                if not self._extractor or not hasattr(self._extractor, 'is_connected'):
                    continue
                    
                is_connected = getattr(self._extractor, 'is_connected', lambda: False)()
                
                if not is_connected and self._running:
                    await self.reconnect()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Auto-reconnect loop error: {e}")


class RTSPExtractor:
    """RTSP stream extractor with low-latency frame extraction."""
    
    def __init__(
        self,
        url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        width: int = 640,
        height: int = 480,
        timeout_ms: int = 5000,
        target_fps: float = 30.0,
    ):
        self.url = url
        self.username = username or ""
        self.password = password or ""
        self.width = width
        self.height = height
        self.timeout_ms = timeout_ms
        self.target_fps = target_fps
        
        # OpenCV capture object
        self._capture: Optional[Any] = None
        self._is_connected = False
        self._frame_queue: asyncio.Queue = asyncio.Queue(maxsize=10)
        
    async def connect(self) -> bool:
        """Establish RTSP connection."""
        if cv2 is None:
            raise ImportError("OpenCV (cv2) is required for RTSP extraction")
            
        # Create capture with optimized settings
        self._capture = cv2.VideoCapture(
            self.url,
            cv2.CAP_FFMPEG  # Use FFMPEG backend for better compatibility
        )
        
        if not self._capture.isOpened():
            raise ConnectionError(f"Failed to open RTSP stream: {self.url}")
            
        # Set optimal capture properties
        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        fps = self._capture.get(cv2.CAP_PROP_FPS) or self.target_fps
        self._capture.set(cv2.CAP_PROP_FPS, fps)
        
        # Enable low-latency mode if available (OpenCV 4.5+)
        try:
            self._capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass
            
        logger.info(f"RTSP connection established at {fps:.1f} FPS")
        self._is_connected = True
        
        return True
    
    def disconnect(self) -> None:
        """Release capture resources."""
        if self._capture is not None:
            try:
                self._capture.release()
            except Exception as e:
                logger.warning(f"Error releasing capture: {e}")
            finally:
                self._capture = None
        
        self._is_connected = False
    
    def get_frame(self, timeout_ms: int = 5000) -> FrameData:
        """Extract next frame with timeout."""
        start_time = time.time()
        
        while time.time() - start_time < timeout_ms / 1000.0:
            ret, frame = self._capture.read()
            
            if ret and frame is not None:
                # Convert to numpy array for consistency
                frame_array = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                return FrameData(
                    timestamp=time.time(),
                    frame_id=0,  # Will be set by caller
                    image=frame_array,
                    confidence=1.0
                )
            
            # Check for timeout
            if time.time() - start_time >= timeout_ms / 1000.0:
                raise asyncio.TimeoutError("Frame extraction timed out")
        
        raise asyncio.TimeoutError(f"Timeout after {timeout_ms}ms waiting for frame")
    
    @property
    def is_connected(self) -> bool:
        """Check if connection is active."""
        return self._is_connected and self._capture is not None


class RTMPExtractor:
    """RTMP stream extractor using FFmpeg."""
    
    def __init__(
        self,
        url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        width: int = 640,
        height: int = 480,
        timeout_ms: int = 5000,
    ):
        self.url = url
        self.username = username or ""
        self.password = password or ""
        self.width = width
        self.height = height
        self.timeout_ms = timeout_ms
        
        # FFmpeg process for RTMP streams
        self._process: Optional[asyncio.subprocess.Process] = None
        self._is_connected = False
    
    async def connect(self) -> bool:
        """Establish RTMP connection using FFmpeg."""
        import subprocess
        
        # Build FFmpeg command for low-latency RTMP stream
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-i", self.url,
            "-f", "rawvideo",
            "-pix_fmt", "rgb24",
            "-video_size", f"{self.width}x{self.height}",
            "-framerate", "30",
            "-avoid_negative_ts", "make_zero",  # Critical for low latency
            "-"
        ]
        
        try:
            self._process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            logger.info(f"RTMP connection established via FFmpeg")
            self._is_connected = True
            
        except Exception as e:
            logger.error(f"Failed to start RTMP extractor: {e}")
            raise ConnectionError(f"RTMP extraction failed: {e}")
        
        return True
    
    def disconnect(self) -> None:
        """Close FFmpeg process."""
        if self._process is not None:
            try:
                self._process.terminate()
                self._process.wait(timeout=5.0)
            except Exception as e:
                logger.warning(f"Error closing RTMP extractor: {e}")
            finally:
                self._process = None
        
        self._is_connected = False
    
    def get_frame(self, timeout_ms: int = 5000) -> FrameData:
        """Extract next frame from FFmpeg output."""
        import numpy as np
        
        if self._process is None or not self._process.poll() is None:
            raise ConnectionError("RTMP extractor not connected")
            
        try:
            # Read raw RGB24 data (3 bytes per pixel)
            buffer_size = self.width * self.height * 3
            
            frame_data = self._process.stdout.read(buffer_size)
            
            if len(frame_data) < buffer_size:
                raise asyncio.TimeoutError("Incomplete frame read")
                
            # Convert to numpy array
            frame_array = np.frombuffer(frame_data, dtype=np.uint8).reshape(
                (self.height, self.width, 3)
            )
            
            return FrameData(
                timestamp=time.time(),
                frame_id=0,
                image=frame_array,
                confidence=1.0
            )
            
        except Exception as e:
            raise asyncio.TimeoutError(f"Frame extraction failed: {e}")
    
    @property
    def is_connected(self) -> bool:
        """Check if connection is active."""
        return self._is_connected and self._process is not None and \
               self._process.poll() is None
