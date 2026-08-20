"""
Frame extractors for keyframe selection and GPS extraction
"""

import time
import numpy as np
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from collections import deque

from ..core.models import Frame, GPSData, GPSSource
from ..core.utils import get_logger, calculate_iou

logger = get_logger("streaming.extractors")


@dataclass
class FrameExtractor:
    """Base class for frame extraction"""
    
    def extract(self, frame: Frame) -> Optional[Frame]:
        """Extract key information from frame"""
        return frame


@dataclass
class KeyframeExtractor:
    """
    Extracts keyframes based on various strategies:
    - Fixed interval (time-based)
    - Motion detection (content-based)
    - Feature change (feature-based)
    - Hybrid (combination of strategies)
    """
    
    strategy: str = "interval"  # interval, motion, feature, hybrid
    interval: float = 1.0  # Seconds between keyframes
    motion_threshold: float = 0.1  # IoU threshold for motion detection
    feature_threshold: float = 0.3  # Feature change threshold
    min_keyframes: int = 1  # Minimum keyframes per second
    
    # State for tracking
    _last_keyframe_time: float = 0.0
    _last_keyframe_features: Optional[np.ndarray] = None
    _frame_history: deque = field(default_factory=lambda: deque(maxlen=10))
    _last_keyframe: Optional[Frame] = None
    
    def extract(self, frame: Frame) -> Optional[Frame]:
        """
        Determine if this frame should be a keyframe
        
        Args:
            frame: Input frame
        
        Returns:
            Frame if it's a keyframe, None otherwise
        """
        if self.strategy == "interval":
            return self._extract_interval(frame)
        elif self.strategy == "motion":
            return self._extract_motion(frame)
        elif self.strategy == "feature":
            return self._extract_feature(frame)
        elif self.strategy == "hybrid":
            return self._extract_hybrid(frame)
        else:
            logger.warning(f"Unknown keyframe strategy: {self.strategy}")
            return frame
    
    def _extract_interval(self, frame: Frame) -> Optional[Frame]:
        """Extract keyframes at fixed time intervals"""
        current_time = frame.timestamp
        
        # Always take first frame
        if self._last_keyframe is None:
            self._last_keyframe = frame
            self._last_keyframe_time = current_time
            return frame
        
        # Check if enough time has passed
        if current_time - self._last_keyframe_time >= self.interval:
            self._last_keyframe = frame
            self._last_keyframe_time = current_time
            return frame
        
        return None
    
    def _extract_motion(self, frame: Frame) -> Optional[Frame]:
        """Extract keyframes based on motion detection"""
        if frame.data is None:
            return frame
        
        # Always take first frame
        if self._last_keyframe is None:
            self._last_keyframe = frame
            self._frame_history.append(frame)
            return frame
        
        # Convert to grayscale for motion detection
        gray = cv2.cvtColor(frame.data, cv2.COLOR_BGR2GRAY)
        last_gray = cv2.cvtColor(self._last_keyframe.data, cv2.COLOR_BGR2GRAY)
        
        # Compute absolute difference
        diff = cv2.absdiff(gray, last_gray)
        
        # Apply threshold
        _, thresh = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)
        
        # Calculate motion percentage
        motion_pixels = np.sum(thresh > 0)
        total_pixels = thresh.size
        motion_ratio = motion_pixels / total_pixels
        
        # Check if enough motion
        if motion_ratio > self.motion_threshold:
            self._last_keyframe = frame
            self._frame_history.append(frame)
            return frame
        
        return None
    
    def _extract_feature(self, frame: Frame) -> Optional[Frame]:
        """Extract keyframes based on feature change"""
        if frame.data is None:
            return frame
        
        # Always take first frame
        if self._last_keyframe is None:
            self._last_keyframe = frame
            self._last_keyframe_features = self._compute_features(frame.data)
            return frame
        
        # Compute current features
        current_features = self._compute_features(frame.data)
        
        if current_features is None or self._last_keyframe_features is None:
            return frame
        
        # Calculate feature difference
        diff = np.linalg.norm(current_features - self._last_keyframe_features)
        
        # Check if enough feature change
        if diff > self.feature_threshold:
            self._last_keyframe = frame
            self._last_keyframe_features = current_features
            return frame
        
        return None
    
    def _extract_hybrid(self, frame: Frame) -> Optional[Frame]:
        """Extract keyframes using hybrid approach"""
        # Check interval first
        interval_result = self._extract_interval(frame)
        if interval_result is not None:
            return interval_result
        
        # Check motion
        motion_result = self._extract_motion(frame)
        if motion_result is not None:
            return motion_result
        
        # Check feature
        feature_result = self._extract_feature(frame)
        if feature_result is not None:
            return feature_result
        
        return None
    
    def _compute_features(self, image: np.ndarray) -> Optional[np.ndarray]:
        """Compute feature vector for an image"""
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Resize to fixed size
            gray = cv2.resize(gray, (64, 64))
            
            # Flatten to feature vector
            return gray.flatten().astype(np.float32)
            
        except Exception as e:
            logger.error(f"Error computing features: {e}")
            return None
    
    def reset(self) -> None:
        """Reset the extractor state"""
        self._last_keyframe_time = 0.0
        self._last_keyframe_features = None
        self._frame_history.clear()
        self._last_keyframe = None


@dataclass
class GPSExtractor:
    """
    Extracts GPS data from various sources:
    - Embedded metadata (EXIF)
    - External GPS device
    - Manual override
    """
    
    source: GPSSource = GPSSource.EMBEDDED
    external_gps_config: Optional[Dict[str, Any]] = None
    manual_override: Optional[GPSData] = None
    
    def extract(self, frame: Frame) -> Optional[GPSData]:
        """Extract GPS data for a frame"""
        if self.manual_override:
            return self.manual_override
        
        if self.source == GPSSource.EMBEDDED:
            return self._extract_embedded(frame)
        elif self.source == GPSSource.EXTERNAL:
            return self._extract_external(frame)
        elif self.source == GPSSource.MANUAL:
            return self.manual_override
        else:
            return None
    
    def _extract_embedded(self, frame: Frame) -> Optional[GPSData]:
        """Extract GPS from embedded metadata (EXIF)"""
        # This would parse EXIF data from the frame
        # For now, return None as this requires specific implementation
        return None
    
    def _extract_external(self, frame: Frame) -> Optional[GPSData]:
        """Extract GPS from external device"""
        # This would connect to an external GPS device
        # For now, return None as this requires specific implementation
        return None
    
    def set_manual_override(self, gps: GPSData) -> None:
        """Set manual GPS override"""
        self.manual_override = gps
    
    def clear_manual_override(self) -> None:
        """Clear manual GPS override"""
        self.manual_override = None


# Import cv2 for motion detection
try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False
    logger.warning("OpenCV not available, motion detection will not work")


@dataclass
class MotionDetector:
    """Detects motion between consecutive frames"""
    
    threshold: float = 0.05  # Motion threshold (0-1)
    min_contour_area: int = 100  # Minimum contour area for motion
    
    _prev_frame: Optional[np.ndarray] = None
    _motion_history: deque = field(default_factory=lambda: deque(maxlen=100))
    
    def detect(self, frame: Frame) -> Tuple[bool, float, Optional[np.ndarray]]:
        """
        Detect motion in a frame
        
        Args:
            frame: Input frame
        
        Returns:
            Tuple of (has_motion, motion_score, motion_mask)
        """
        if frame.data is None:
            return False, 0.0, None
        
        if not HAS_CV2:
            return False, 0.0, None
        
        gray = cv2.cvtColor(frame.data, cv2.COLOR_BGR2GRAY)
        
        if self._prev_frame is None:
            self._prev_frame = gray
            return False, 0.0, None
        
        # Compute absolute difference
        diff = cv2.absdiff(gray, self._prev_frame)
        
        # Apply threshold
        _, thresh = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)
        
        # Dilate to fill gaps
        kernel = np.ones((5, 5), np.uint8)
        dilated = cv2.dilate(thresh, kernel, iterations=2)
        
        # Find contours
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Calculate motion score
        motion_pixels = np.sum(dilated > 0)
        total_pixels = dilated.size
        motion_score = motion_pixels / total_pixels
        
        # Check for significant motion
        has_motion = motion_score > self.threshold
        
        # Update previous frame
        self._prev_frame = gray
        
        # Store motion history
        self._motion_history.append(motion_score)
        
        return has_motion, motion_score, dilated
    
    def get_motion_history(self) -> List[float]:
        """Get motion history"""
        return list(self._motion_history)
    
    def get_average_motion(self) -> float:
        """Get average motion score"""
        if not self._motion_history:
            return 0.0
        return float(np.mean(self._motion_history))
    
    def reset(self) -> None:
        """Reset motion detector"""
        self._prev_frame = None
        self._motion_history.clear()


class FrameBuffer:
    """Buffer for storing recent frames"""
    
    def __init__(self, max_size: int = 100):
        self._buffer: deque = deque(maxlen=max_size)
        self._index: Dict[str, Frame] = {}  # Frame ID to frame mapping
    
    def add_frame(self, frame: Frame) -> None:
        """Add a frame to the buffer"""
        self._buffer.append(frame)
        self._index[frame.id] = frame
        
        # Clean up old frames if buffer is full
        if len(self._buffer) > self._buffer.maxlen:
            old_frame = self._buffer.popleft()
            del self._index[old_frame.id]
    
    def get_frame(self, frame_id: str) -> Optional[Frame]:
        """Get a frame by ID"""
        return self._index.get(frame_id)
    
    def get_frames_in_time_range(self, start_time: float, end_time: float) -> List[Frame]:
        """Get frames within a time range"""
        return [f for f in self._buffer if start_time <= f.timestamp <= end_time]
    
    def get_latest_frame(self) -> Optional[Frame]:
        """Get the latest frame"""
        if self._buffer:
            return self._buffer[-1]
        return None
    
    def get_frames_since(self, timestamp: float) -> List[Frame]:
        """Get all frames since a timestamp"""
        return [f for f in self._buffer if f.timestamp >= timestamp]
    
    def clear(self) -> None:
        """Clear the buffer"""
        self._buffer.clear()
        self._index.clear()
    
    def __len__(self) -> int:
        return len(self._buffer)
    
    def __iter__(self):
        return iter(self._buffer)
