"""
Video stream ingestors for various protocols
"""

import asyncio
import os
import time
import threading
import queue
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Callable, AsyncIterator
from pathlib import Path
import numpy as np
import cv2

from ..core.models import (
    Frame,
    VideoStream,
    StreamConfig,
    StreamStatus,
    StreamType,
    GPSData,
    GPSSource,
)
from ..core.utils import get_logger, timestamp_now

logger = get_logger("streaming.ingestors")


class StreamIngestor(ABC):
    """Abstract base class for stream ingestors"""
    
    def __init__(self, config: StreamConfig):
        self.config = config
        self.stream: Optional[VideoStream] = None
        self._frame_queue: queue.Queue = queue.Queue(maxsize=100)
        self._running: bool = False
        self._stop_event: threading.Event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._frame_callbacks: List[Callable[[Frame], None]] = []
        
    @abstractmethod
    def connect(self) -> bool:
        """Connect to the stream source"""
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from the stream source"""
        pass
    
    @abstractmethod
    def _read_frame(self) -> Optional[np.ndarray]:
        """Read a single frame from the stream"""
        pass
    
    def start(self) -> bool:
        """Start the ingestor thread"""
        if self._running:
            logger.warning(f"Ingestor for {self.config.id} already running")
            return False
        
        if not self.connect():
            logger.error(f"Failed to connect to {self.config.id}")
            return False
        
        self._running = True
        self._stop_event.clear()
        
        # Update stream status
        if self.stream:
            self.stream.status = StreamStatus.CONNECTED
        
        # Start thread
        self._thread = threading.Thread(
            target=self._ingest_loop,
            daemon=True,
            name=f"Ingestor-{self.config.id}"
        )
        self._thread.start()
        
        logger.info(f"Started ingestor for {self.config.id}")
        return True
    
    def stop(self) -> None:
        """Stop the ingestor thread"""
        if not self._running:
            return
        
        self._running = False
        self._stop_event.set()
        
        # Update stream status
        if self.stream:
            self.stream.status = StreamStatus.DISCONNECTED
        
        # Wait for thread to finish
        if self._thread:
            self._thread.join(timeout=5.0)
        
        self.disconnect()
        logger.info(f"Stopped ingestor for {self.config.id}")
    
    def _ingest_loop(self) -> None:
        """Main ingestion loop"""
        frame_count = 0
        last_time = timestamp_now()
        
        while self._running and not self._stop_event.is_set():
            try:
                # Read frame
                frame_data = self._read_frame()
                if frame_data is None:
                    time.sleep(0.01)
                    continue
                
                # Create Frame object
                frame = self._create_frame(frame_data, frame_count)
                if frame is None:
                    continue
                
                # Extract GPS if available
                if self.config.gps:
                    frame.gps = self._extract_gps(frame_data)
                
                # Add to queue
                try:
                    self._frame_queue.put_nowait(frame)
                    frame_count += 1
                    
                    # Update FPS
                    current_time = timestamp_now()
                    if current_time - last_time >= 1.0:
                        if self.stream:
                            self.stream.fps_actual = frame_count / (current_time - last_time)
                            self.stream.frame_count = frame_count
                            self.stream.last_frame_time = current_time
                        frame_count = 0
                        last_time = current_time
                    
                    # Notify callbacks
                    for callback in self._frame_callbacks:
                        try:
                            callback(frame)
                        except Exception as e:
                            logger.error(f"Error in frame callback: {e}")
                except queue.Full:
                    logger.warning(f"Frame queue full for {self.config.id}, dropping frame")
                    
            except Exception as e:
                logger.error(f"Error reading frame from {self.config.id}: {e}")
                time.sleep(0.1)
        
        logger.info(f"Ingest loop stopped for {self.config.id}")
    
    def _create_frame(self, frame_data: np.ndarray, frame_number: int) -> Optional[Frame]:
        """Create a Frame object from raw frame data"""
        try:
            frame = Frame(
                stream_id=self.config.id,
                data=frame_data.copy(),
                timestamp=timestamp_now(),
                frame_number=frame_number,
                resolution=(frame_data.shape[1], frame_data.shape[0]),
                calibration=self.config.calibration,
            )
            return frame
        except Exception as e:
            logger.error(f"Error creating frame: {e}")
            return None
    
    def _extract_gps(self, frame_data: np.ndarray) -> Optional[GPSData]:
        """Extract GPS data from frame (to be overridden by specific ingestors)"""
        return None
    
    def get_frame(self, timeout: Optional[float] = None) -> Optional[Frame]:
        """Get a frame from the queue"""
        try:
            return self._frame_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def add_frame_callback(self, callback: Callable[[Frame], None]) -> None:
        """Add a callback for new frames"""
        self._frame_callbacks.append(callback)
    
    def remove_frame_callback(self, callback: Callable[[Frame], None]) -> None:
        """Remove a frame callback"""
        if callback in self._frame_callbacks:
            self._frame_callbacks.remove(callback)
    
    async def async_frames(self) -> AsyncIterator[Frame]:
        """Async iterator for frames"""
        while self._running:
            frame = self.get_frame(timeout=0.1)
            if frame is not None:
                yield frame
            else:
                await asyncio.sleep(0.01)


class RTSPIngestor(StreamIngestor):
    """RTSP stream ingestor"""
    
    def __init__(self, config: StreamConfig):
        super().__init__(config)
        self._cap: Optional[cv2.VideoCapture] = None
    
    def connect(self) -> bool:
        """Connect to RTSP stream"""
        try:
            # RTSP buffer size (reduce latency)
            cv2.CAP_PROP_BUFFERSIZE = 1
            
            self._cap = cv2.VideoCapture(self.config.url)
            if not self._cap.isOpened():
                logger.error(f"Failed to open RTSP stream: {self.config.url}")
                return False
            
            # Set properties
            if self.config.resolution:
                self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.resolution[0])
                self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.resolution[1])
            if self.config.fps > 0:
                self._cap.set(cv2.CAP_PROP_FPS, self.config.fps)
            
            logger.info(f"Connected to RTSP stream: {self.config.url}")
            return True
            
        except Exception as e:
            logger.error(f"Error connecting to RTSP stream: {e}")
            return False
    
    def disconnect(self) -> None:
        """Disconnect from RTSP stream"""
        if self._cap:
            self._cap.release()
            self._cap = None
    
    def _read_frame(self) -> Optional[np.ndarray]:
        """Read a frame from RTSP stream"""
        if not self._cap or not self._cap.isOpened():
            return None
        
        ret, frame = self._cap.read()
        if not ret:
            return None
        
        return frame


class RTMPIngestor(StreamIngestor):
    """RTMP stream ingestor"""
    
    def __init__(self, config: StreamConfig):
        super().__init__(config)
        self._cap: Optional[cv2.VideoCapture] = None
    
    def connect(self) -> bool:
        """Connect to RTMP stream"""
        try:
            self._cap = cv2.VideoCapture(self.config.url)
            if not self._cap.isOpened():
                logger.error(f"Failed to open RTMP stream: {self.config.url}")
                return False
            
            logger.info(f"Connected to RTMP stream: {self.config.url}")
            return True
            
        except Exception as e:
            logger.error(f"Error connecting to RTMP stream: {e}")
            return False
    
    def disconnect(self) -> None:
        """Disconnect from RTMP stream"""
        if self._cap:
            self._cap.release()
            self._cap = None
    
    def _read_frame(self) -> Optional[np.ndarray]:
        """Read a frame from RTMP stream"""
        if not self._cap or not self._cap.isOpened():
            return None
        
        ret, frame = self._cap.read()
        if not ret:
            return None
        
        return frame


class HTTPIngestor(StreamIngestor):
    """HTTP/MJPEG stream ingestor"""
    
    def __init__(self, config: StreamConfig):
        super().__init__(config)
        self._cap: Optional[cv2.VideoCapture] = None
    
    def connect(self) -> bool:
        """Connect to HTTP stream"""
        try:
            self._cap = cv2.VideoCapture(self.config.url)
            if not self._cap.isOpened():
                logger.error(f"Failed to open HTTP stream: {self.config.url}")
                return False
            
            logger.info(f"Connected to HTTP stream: {self.config.url}")
            return True
            
        except Exception as e:
            logger.error(f"Error connecting to HTTP stream: {e}")
            return False
    
    def disconnect(self) -> None:
        """Disconnect from HTTP stream"""
        if self._cap:
            self._cap.release()
            self._cap = None
    
    def _read_frame(self) -> Optional[np.ndarray]:
        """Read a frame from HTTP stream"""
        if not self._cap or not self._cap.isOpened():
            return None
        
        ret, frame = self._cap.read()
        if not ret:
            return None
        
        return frame


class FileIngestor(StreamIngestor):
    """File-based video ingestor"""
    
    def __init__(self, config: StreamConfig):
        super().__init__(config)
        self._cap: Optional[cv2.VideoCapture] = None
        self._loop: bool = config.url.endswith(".mp4") or config.url.endswith(".avi")
    
    def connect(self) -> bool:
        """Open video file"""
        try:
            # Check if path exists
            if not os.path.exists(self.config.url):
                logger.error(f"Video file not found: {self.config.url}")
                return False
            
            self._cap = cv2.VideoCapture(self.config.url)
            if not self._cap.isOpened():
                logger.error(f"Failed to open video file: {self.config.url}")
                return False
            
            logger.info(f"Opened video file: {self.config.url}")
            return True
            
        except Exception as e:
            logger.error(f"Error opening video file: {e}")
            return False
    
    def disconnect(self) -> None:
        """Close video file"""
        if self._cap:
            self._cap.release()
            self._cap = None
    
    def _read_frame(self) -> Optional[np.ndarray]:
        """Read a frame from video file"""
        if not self._cap or not self._cap.isOpened():
            return None
        
        ret, frame = self._cap.read()
        if not ret:
            # End of file - rewind if looping
            if self._loop:
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self._cap.read()
                if not ret:
                    return None
            else:
                return None
        
        return frame


class WebRTCIngestor(StreamIngestor):
    """WebRTC stream ingestor (placeholder - requires aiortc)"""
    
    def __init__(self, config: StreamConfig):
        super().__init__(config)
        self._cap: Optional[Any] = None
        
        # Check if aiortc is available
        try:
            import aiortc
            self._aiortc_available = True
        except ImportError:
            self._aiortc_available = False
            logger.warning("aiortc not installed, WebRTC ingestor will not work")
    
    def connect(self) -> bool:
        """Connect to WebRTC stream"""
        if not self._aiortc_available:
            logger.error("aiortc not available for WebRTC streaming")
            return False
        
        try:
            # WebRTC connection would be established here
            # This is a placeholder - actual implementation requires aiortc
            logger.warning("WebRTC ingestor not fully implemented - requires aiortc")
            return False
            
        except Exception as e:
            logger.error(f"Error connecting to WebRTC stream: {e}")
            return False
    
    def disconnect(self) -> None:
        """Disconnect from WebRTC stream"""
        self._cap = None
    
    def _read_frame(self) -> Optional[np.ndarray]:
        """Read a frame from WebRTC stream"""
        # Placeholder
        return None


class MultiStreamManager:
    """Manages multiple video stream ingestors"""
    
    def __init__(self):
        self._ingestors: Dict[str, StreamIngestor] = {}
        self._streams: Dict[str, VideoStream] = {}
        self._frame_callbacks: List[Callable[[Frame], None]] = []
        self._running: bool = False
    
    def add_stream(self, config: StreamConfig) -> bool:
        """Add a new stream"""
        if config.id in self._ingestors:
            logger.warning(f"Stream {config.id} already exists")
            return False
        
        # Create ingestor based on type
        ingestor: Optional[StreamIngestor] = None
        if config.stream_type == StreamType.RTSP:
            ingestor = RTSPIngestor(config)
        elif config.stream_type == StreamType.RTMP:
            ingestor = RTMPIngestor(config)
        elif config.stream_type == StreamType.HTTP:
            ingestor = HTTPIngestor(config)
        elif config.stream_type == StreamType.FILE:
            ingestor = FileIngestor(config)
        elif config.stream_type == StreamType.WEBRTC:
            ingestor = WebRTCIngestor(config)
        else:
            logger.error(f"Unsupported stream type: {config.stream_type}")
            return False
        
        if ingestor is None:
            return False
        
        # Create VideoStream object
        stream = VideoStream(
            config=config,
            status=StreamStatus.DISCONNECTED,
        )
        
        ingestor.stream = stream
        self._ingestors[config.id] = ingestor
        self._streams[config.id] = stream
        
        # Add global frame callback
        ingestor.add_frame_callback(self._on_frame)
        
        logger.info(f"Added stream: {config.id} ({config.stream_type.value})")
        return True
    
    def remove_stream(self, stream_id: str) -> bool:
        """Remove a stream"""
        if stream_id not in self._ingestors:
            logger.warning(f"Stream {stream_id} not found")
            return False
        
        ingestor = self._ingestors[stream_id]
        ingestor.stop()
        
        del self._ingestors[stream_id]
        del self._streams[stream_id]
        
        logger.info(f"Removed stream: {stream_id}")
        return True
    
    def start_stream(self, stream_id: str) -> bool:
        """Start a specific stream"""
        if stream_id not in self._ingestors:
            logger.warning(f"Stream {stream_id} not found")
            return False
        
        ingestor = self._ingestors[stream_id]
        return ingestor.start()
    
    def stop_stream(self, stream_id: str) -> None:
        """Stop a specific stream"""
        if stream_id not in self._ingestors:
            logger.warning(f"Stream {stream_id} not found")
            return
        
        self._ingestors[stream_id].stop()
    
    def start_all(self) -> None:
        """Start all streams"""
        for stream_id, ingestor in self._ingestors.items():
            if ingestor.config.enabled:
                ingestor.start()
        self._running = True
    
    def stop_all(self) -> None:
        """Stop all streams"""
        for ingestor in self._ingestors.values():
            ingestor.stop()
        self._running = False
    
    def _on_frame(self, frame: Frame) -> None:
        """Handle incoming frames"""
        for callback in self._frame_callbacks:
            try:
                callback(frame)
            except Exception as e:
                logger.error(f"Error in global frame callback: {e}")
    
    def add_frame_callback(self, callback: Callable[[Frame], None]) -> None:
        """Add a global frame callback"""
        self._frame_callbacks.append(callback)
    
    def remove_frame_callback(self, callback: Callable[[Frame], None]) -> None:
        """Remove a global frame callback"""
        if callback in self._frame_callbacks:
            self._frame_callbacks.remove(callback)
    
    def get_stream(self, stream_id: str) -> Optional[VideoStream]:
        """Get stream info"""
        return self._streams.get(stream_id)
    
    def get_streams(self) -> Dict[str, VideoStream]:
        """Get all streams"""
        return self._streams.copy()
    
    def get_ingestor(self, stream_id: str) -> Optional[StreamIngestor]:
        """Get ingestor for a stream"""
        return self._ingestors.get(stream_id)
    
    def get_frames(self, stream_id: str, timeout: Optional[float] = None) -> Optional[Frame]:
        """Get a frame from a specific stream"""
        ingestor = self._ingestors.get(stream_id)
        if ingestor:
            return ingestor.get_frame(timeout)
        return None
    
    async def async_frames(self, stream_id: Optional[str] = None) -> AsyncIterator[Frame]:
        """Async iterator for frames from all streams or a specific stream"""
        if stream_id:
            ingestor = self._ingestors.get(stream_id)
            if ingestor:
                async for frame in ingestor.async_frames():
                    yield frame
        else:
            # Merge frames from all streams
            while self._running:
                for ingestor in self._ingestors.values():
                    frame = ingestor.get_frame(timeout=0.01)
                    if frame is not None:
                        yield frame
                await asyncio.sleep(0.01)
