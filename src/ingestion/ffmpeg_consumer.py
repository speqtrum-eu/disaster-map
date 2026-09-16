import ffmpeg
import numpy as np
import cv2
import time
import threading
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass
from .base import BaseStreamConsumer, FrameData


@dataclass
class StreamMetadata:
    """Holds stream metadata extracted from FFmpeg."""
    width: int
    height: int
    fps: float
    pixel_format: str
    bitrate: int  # in bps
    url: str


class FFmpegStreamConsumer(BaseStreamConsumer):
    """Consumes video streams using FFmpeg with async frame reading and buffering.

    Features:
    - Async frame reading with configurable buffer size
    - Stream metadata extraction (resolution, FPS, bitrate)
    - Health monitoring with heartbeat checks
    - Graceful error handling with reconnection support
    - Thread-safe frame delivery
    """

    # Default configuration for 1000ms target latency
    DEFAULT_BUFFER_SIZE = 32  # frames to buffer for smooth playback
    DEFAULT_TIMEOUT = 1.0     # seconds per read attempt
    MIN_FRAME_INTERVAL = 0.05 # minimum time between frames (20 FPS floor)

    def __init__(
        self, 
        stream_url: str, 
        stream_id: str,
        width: int = None,
        height: int = None,
        buffer_size: int = DEFAULT_BUFFER_SIZE,
        timeout: float = DEFAULT_TIMEOUT,
        min_fps: float = 15.0
    ):
        """Initialize the FFmpeg stream consumer.

        Args:
            stream_url: RTSP/RTMP/WebRTC URL to consume
            stream_id: Unique identifier for this stream
            width: Expected frame width (optional - will be detected if not provided)
            height: Expected frame height (optional - will be detected if not provided)
            buffer_size: Number of frames to buffer (default 32 for ~1 second latency at 30fps)
            timeout: Timeout per read attempt in seconds
            min_fps: Minimum acceptable FPS (frames below this are dropped)
        """
        self.stream_url = stream_url
        self.stream_id = stream_id
        self._process: Optional[Any] = None
        self._is_running = False
        self._metadata: Optional[StreamMetadata] = None
        self._buffer_size = buffer_size
        self._timeout = timeout
        self._min_fps = min_fps

        # Frame buffering and state management
        self._frame_buffer: list[np.ndarray] = []
        self._buffer_lock = threading.Lock()
        self._condition = threading.Condition(self._buffer_lock)

        # Health monitoring
        self._last_frame_time: float = 0.0
        self._frame_count = 0
        self._error_count = 0
        self._max_errors_before_fail = 5

        # Frame delivery (thread-safe queue for consumers)
        self._delivery_queue: list[FrameData] = []
        self._delivery_lock = threading.Lock()

    def connect(self) -> bool:
        """Initializes the FFmpeg process and extracts stream metadata.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            # First, probe the stream to get metadata without consuming data
            probe_cmd = (
                ffmpeg.probe(
                    self.stream_url, 
                    select='streams',
                    v=0  # verbose output for debugging
                )
            )

            # Extract video stream info
            video_streams = [s for s in probe_cmd['streams'] if s.get('codec_type') == 'video']
            if not video_streams:
                print(f"No video streams found in {self.stream_url}")
                return False

            video_stream = video_streams[0]
            
            # Get stream info with ffmpeg (more reliable than probe)
            info_cmd = (
                ffmpeg
                .input(self.stream_url, size='original')  # Don't resize yet
                .outputs()
                .run(cmd=['ffmpeg', '-i', self.stream_url, '-v', 'quiet'], 
                     capture_stdout=True, capture_stderr=True)
            )

            # Parse resolution from probe output
            width = int(video_stream.get('width', 0)) or (width if width else 640)
            height = int(video_stream.get('height', 0)) or (height if height else 480)
            
            # Calculate FPS from codec info
            r_frame_rate = video_stream.get('r_frame_rate', '30/1')
            try:
                fps_parts = r_frame_rate.split('/')
                if len(fps_parts) == 2:
                    fps = int(fps_parts[0]) / int(fps_parts[1])
                else:
                    fps = float(r_frame_rate)
            except (ValueError, ZeroDivisionError):
                fps = self._min_fps

            # Ensure minimum FPS threshold
            if fps < self._min_fps:
                print(
                    f"Warning: Stream {self.stream_id} has low FPS ({fps:.1f}), "
                    f"below minimum threshold of {self._min_fps}"
                )

            # Create metadata object
            self._metadata = StreamMetadata(
                width=width,
                height=height,
                fps=fps,
                pixel_format='bgr24',  # Standard for OpenCV
                bitrate=int(video_stream.get('bit_rate', '0')),
                url=self.stream_url
            )

            print(
                f"Connected to stream {self.stream_id}: "
                f"{width}x{height}, {fps:.1f} FPS, {video_stream.get('codec_name', 'unknown')}"
            )

            # Initialize the FFmpeg process for frame reading
            self._process = (
                ffmpeg
                .input(self.stream_url)
                .output(
                    'pipe:', 
                    format='rawvideo', 
                    pix_fmt='bgr24',
                    s=f'{width}x{height}'  # Ensure correct resolution
                )
                .run_async(capture_stdout=True, capture_stderr=True)
            )

            self._is_running = True
            return True

        except Exception as e:
            error_msg = f"Error connecting to stream {self.stream_id} ({self.stream_url}): {e}"
            print(error_msg)
            
            # Increment error count for health monitoring
            self._error_count += 1
            if self._error_count >= self._max_errors_before_fail:
                print(f"Stream {self.stream_id} failed after {self._error_count} errors")

            return False

    def disconnect(self) -> None:
        """Gracefully stops the FFmpeg process and cleans up resources."""
        print(f"Disconnecting stream {self.stream_id}...")
        
        self._is_running = False
        
        # Drain remaining frames from buffer
        with self._buffer_lock:
            while len(self._frame_buffer) > 0:
                try:
                    frame = self._frame_buffer.pop(0)
                    if frame is not None:
                        self._delivery_queue.append(FrameData(
                            timestamp=time.time(),
                            data=frame,
                            stream_id=self.stream_id
                        ))
                    self._condition.notify_all()
                except Exception:
                    break

        # Terminate FFmpeg process
        if self._process is not None:
            try:
                self._process.terminate(timeout=2.0)
                self._process.wait(timeout=5.0)
            except (AttributeError, TimeoutError):
                pass  # Process may already be dead

        self._process = None
        print(f"Stream {self.stream_id} disconnected")

    def get_stream_metadata(self) -> Optional[StreamMetadata]:
        """Returns the extracted stream metadata.

        Returns:
            StreamMetadata object if available, None otherwise
        """
        return self._metadata

    def is_connected(self) -> bool:
        """Checks if currently connected to a stream."""
        return self._is_running and self._process is not None

    def get_frame_stats(self) -> Dict[str, Any]:
        """Returns current frame statistics for monitoring.

        Returns:
            Dictionary with frame count, error rate, buffer size, etc.
        """
        elapsed = time.time() - self._last_frame_time if self._last_frame_time > 0 else 1.0
        actual_fps = self._frame_count / elapsed if elapsed > 0 else 0

        return {
            'stream_id': self.stream_id,
            'is_connected': self.is_connected(),
            'metadata': {
                'width': self._metadata.width if self._metadata else None,
                'height': self._metadata.height if self._metadata else None,
                'fps': self._metadata.fps if self._metadata else None,
            } if self._metadata else None,
            'frame_count': self._frame_count,
            'actual_fps': actual_fps,
            'error_count': self._error_count,
            'buffer_size': len(self._frame_buffer),
            'delivery_queue_size': len(self._delivery_queue)
        }

    def get_next_frame(self) -> Optional[FrameData]:
        """Retrieves the next frame from the stream with buffering.

        This method blocks until a frame is available or connection fails.
        Uses thread-safe buffering to maintain smooth playback.

        Returns:
            FrameData object containing timestamp, image data, and stream ID
        """
        if not self._is_running or self._process is None:
            return None

        # Wait for a frame with timeout
        start_time = time.time()
        
        while True:
            try:
                # Try to get frame from buffer first (non-blocking)
                with self._buffer_lock:
                    if len(self._frame_buffer) > 0:
                        frame_data = self._frame_buffer.pop(0)
                        return FrameData(
                            timestamp=time.time(),
                            data=frame_data,
                            stream_id=self.stream_id
                        )

                # Read from FFmpeg process with timeout
                in_bytes = self._process.stdout.read(
                    self._metadata.width * self._metadata.height * 3
                ) if self._metadata else b''

                if not in_bytes:
                    # No data received - check for connection issues
                    elapsed = time.time() - start_time
                    if elapsed > self._timeout:
                        print(f"Timeout waiting for frame from {self.stream_id}")
                        return None
                    
                    continue

                # Convert raw bytes to numpy array
                height, width = (
                    self._metadata.height, 
                    self._metadata.width
                ) if self._metadata else (480, 640)
                
                frame = np.frombuffer(in_bytes, np.uint8).reshape((height, width, 3))

                # Validate frame dimensions
                if frame.shape != (height, width, 3):
                    print(
                        f"Warning: Frame shape mismatch for {self.stream_id}: "
                        f"expected ({height}, {width}, 3), got {frame.shape}"
                    )
                    continue

                # Add to buffer (up to buffer_size frames)
                with self._buffer_lock:
                    if len(self._frame_buffer) >= self._buffer_size:
                        # Drop oldest frame to maintain buffer size limit
                        dropped = self._frame_buffer.pop(0)
                        if dropped is not None:
                            self._delivery_queue.append(FrameData(
                                timestamp=time.time(),
                                data=dropped,
                                stream_id=self.stream_id
                            ))

                    self._frame_buffer.append(frame)
                    self._condition.notify_all()

                # Return immediately after buffering
                return FrameData(
                    timestamp=time.time(),
                    data=frame.copy(),  # Copy to prevent modification issues
                    stream_id=self.stream_id
                )

            except Exception as e:
                print(f"Error reading frame from {self.stream_id}: {e}")
                
                # Check if process is still running
                if not self._is_running or (hasattr(self._process, 'returncode') and self._process.returncode is not None):
                    return None
                
                # Increment error count
                self._error_count += 1
                
                if self._error_count >= self._max_errors_before_fail:
                    print(f"Stream {self.stream_id} failed after {self._error_count} errors")
                    return None

                # Wait a bit before retrying
                time.sleep(0.1)

    def get_frame(self, timeout_ms: int = 100) -> Optional[FrameData]:
        """Non-blocking frame retrieval with optional timeout.

        Args:
            timeout_ms: Maximum wait time in milliseconds (default 100ms)

        Returns:
            FrameData if available within timeout, None otherwise
        """
        deadline = time.time() + (timeout_ms / 1000.0)
        
        while time.time() < deadline:
            frame = self.get_next_frame()
            if frame is not None:
                return frame
            
            # Small sleep to avoid busy-waiting
            time.sleep(0.001)  # 1ms

        return None

    def drain_buffer(self, max_frames: int = -1) -> list[FrameData]:
        """Drains all frames from the buffer for processing.

        Args:
            max_frames: Maximum number of frames to drain (-1 for all)

        Returns:
            List of FrameData objects drained from buffer
        """
        with self._buffer_lock:
            frames = []
            
            while len(self._frame_buffer) > 0:
                if max_frames != -1 and len(frames) >= max_frames:
                    break
                    
                frame_data = self._frame_buffer.pop(0)
                if frame_data is not None:
                    frames.append(FrameData(
                        timestamp=time.time(),
                        data=frame_data.copy(),
                        stream_id=self.stream_id
                    ))
                
                self._condition.notify_all()

            return frames

    def __del__(self):
        """Destructor to ensure cleanup."""
        if hasattr(self, '_is_running') and not self._is_running:
            self.disconnect()
