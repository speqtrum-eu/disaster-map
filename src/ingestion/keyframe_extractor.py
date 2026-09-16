"""Keyframe extraction utilities for video streams.

This module provides algorithms for extracting keyframes from video streams based on:
- Time intervals (fixed rate sampling)
- Motion detection (significant changes only)
- Hybrid approach (combines both methods)

Keyframes are critical for reducing data volume while maintaining map quality.
"""

import time
from typing import List, Optional, Callable, Tuple
from dataclasses import dataclass
from enum import Enum

import numpy as np
import cv2


@dataclass
class KeyframeConfig:
    """Configuration for keyframe extraction."""
    
    # Time-based settings
    interval_seconds: float = 1.0      # Extract every N seconds (default 1s)
    min_interval_ms: float = 50.0     # Minimum time between extractions
    
    # Motion detection settings
    motion_threshold: float = 30.0   # Pixel difference threshold for "significant" change
    min_motion_pixels: int = 1000    # Minimum pixels changed to trigger extraction
    use_gaussian_blur: bool = True   # Apply blur before differencing (reduces noise)
    blur_kernel_size: int = 5       # Gaussian blur kernel size
    
    # Quality scoring
    min_quality_score: float = 0.3   # Minimum score for a keyframe to be accepted
    quality_weight_motion: float = 0.4  # Weight for motion in quality calculation
    quality_weight_contrast: float = 0.3  # Weight for contrast
    quality_weight_edges: float = 0.3   # Weight for edge content
    
    # Deduplication
    max_similar_frames: int = 5     # Maximum similar frames to skip after a keyframe
    similarity_threshold: float = 0.85  # Similarity threshold (0-1)


@dataclass
class KeyframeResult:
    """Result of keyframe extraction."""
    
    frame_data: np.ndarray
    timestamp: float
    stream_id: str
    is_motion_triggered: bool
    quality_score: float
    confidence: float  # How certain we are this is a good keyframe


class ExtractionMode(Enum):
    """Keyframe extraction strategy modes."""
    TIME_BASED = "time"      # Extract at fixed intervals
    MOTION_BASED = "motion"  # Extract on significant motion only
    HYBRID = "hybrid"        # Extract on motion OR time threshold


class KeyframeExtractor:
    """Extracts keyframes from video streams using configurable strategies.

    Features:
    - Time-based extraction with minimum interval enforcement
    - Motion detection using OpenCV frame differencing
    - Hybrid mode combining both approaches
    - Quality scoring for keyframe selection
    - Deduplication to avoid redundant frames
    """

    def __init__(self, config: Optional[KeyframeConfig] = None):
        """Initialize the keyframe extractor.

        Args:
            config: Keyframe extraction configuration (uses defaults if not provided)
        """
        self.config = config or KeyframeConfig()
        
        # State tracking
        self._last_extraction_time: float = 0.0
        self._last_keyframe_timestamp: float = 0.0
        self._motion_accumulator: np.ndarray = None
        self._previous_frame: Optional[np.ndarray] = None
        self._extraction_count = 0
        
    def extract(
        self, 
        frame_data: np.ndarray, 
        timestamp: float, 
        stream_id: str,
        mode: ExtractionMode = ExtractionMode.HYBRID
    ) -> List[KeyframeResult]:
        """Extracts keyframes from a single frame.

        Args:
            frame_data: Image data (H, W, C) in BGR format
            timestamp: Frame timestamp in seconds
            stream_id: Identifier for the source stream
            mode: Extraction strategy to use

        Returns:
            List of KeyframeResult objects (may contain multiple if motion is detected)
        """
        results = []
        
        # Handle edge case: empty or invalid frame
        if frame_data.size == 0 or len(frame_data.shape) != 3:
            return results
        
        height, width, channels = frame_data.shape
        
        # Time-based extraction check
        time_triggered = self._check_time_trigger(timestamp)
        
        # Motion detection (only for motion/hybrid modes)
        motion_triggered = False
        if mode in (ExtractionMode.MOTION_BASED, ExtractionMode.HYBRID):
            motion_triggered = self._detect_motion(frame_data)
        
        # Extract keyframe(s) based on triggers
        if time_triggered or motion_triggered:
            quality_score = self._calculate_quality_score(frame_data)
            
            if quality_score >= self.config.min_quality_score:
                result = KeyframeResult(
                    frame_data=frame_data.copy(),
                    timestamp=timestamp,
                    stream_id=stream_id,
                    is_motion_triggered=motion_triggered,
                    quality_score=quality_score,
                    confidence=min(1.0, (time_triggered + motion_triggered) / 2)
                )
                results.append(result)
                
                self._last_keyframe_timestamp = timestamp
                self._extraction_count += 1
        
        return results

    def extract_batch(
        self, 
        frames: List[Tuple[np.ndarray, float, str]],
        mode: ExtractionMode = ExtractionMode.HYBRID
    ) -> List[KeyframeResult]:
        """Extracts keyframes from a batch of frames.

        Args:
            frames: List of (frame_data, timestamp, stream_id) tuples
            mode: Extraction strategy to use

        Returns:
            List of all extracted KeyframeResult objects
        """
        all_results = []
        
        for frame_data, timestamp, stream_id in frames:
            results = self.extract(frame_data, timestamp, stream_id, mode)
            all_results.extend(results)
        
        return all_results

    def _check_time_trigger(self, current_timestamp: float) -> bool:
        """Checks if enough time has passed for extraction.

        Args:
            current_timestamp: Current frame timestamp

        Returns:
            True if time-based extraction should occur
        """
        elapsed = current_timestamp - self._last_extraction_time
        
        # Check minimum interval
        min_interval = max(
            self.config.interval_seconds, 
            self.config.min_interval_ms / 1000.0
        )
        
        if elapsed >= min_interval:
            return True
        
        return False

    def _detect_motion(self, frame_data: np.ndarray) -> bool:
        """Detects significant motion between consecutive frames.

        Uses OpenCV's difference-based motion detection with configurable thresholds.

        Args:
            frame_data: Current frame (H, W, C) in BGR format

        Returns:
            True if significant motion detected above threshold
        """
        # Handle first frame case - initialize previous frame for future comparisons
        if self._previous_frame is None or frame_data.size == 0:
            # For the very first frame, we can't detect motion yet
            # But we need to store it so subsequent frames have something to compare against
            height, width = frame_data.shape[:2]
            self._motion_accumulator = np.zeros((height, width), dtype=np.float32)
            self._previous_frame = cv2.cvtColor(frame_data, cv2.COLOR_BGR2GRAY).copy()
            return False
        
        height, width = self._previous_frame.shape
        
        # Convert to grayscale for faster processing
        current_gray = cv2.cvtColor(frame_data, cv2.COLOR_BGR2GRAY)
        
        if self._motion_accumulator is None:
            self._motion_accumulator = np.zeros((height, width), dtype=np.float32)
        
        # Calculate absolute difference (both are grayscale now)
        diff = np.abs(current_gray.astype(np.float32) - self._previous_frame.astype(np.float32))
        
        # Apply Gaussian blur to reduce noise (if enabled)
        if self.config.use_gaussian_blur:
            diff = cv2.GaussianBlur(diff, (self.config.blur_kernel_size, 
                                          self.config.blur_kernel_size), 0)
        
        # Accumulate motion over time for better detection of sustained movement
        self._motion_accumulator = (
            self._motion_accumulator * 0.7 + diff * 0.3
        )
        
        # Calculate total motion pixels above threshold
        motion_pixels = np.sum(self._motion_accumulator > self.config.motion_threshold)
        
        # Check if motion exceeds minimum threshold
        is_significant_motion = (
            motion_pixels >= self.config.min_motion_pixels and
            motion_pixels / (height * width) > 0.01  # At least 1% of frame changed
        )
        
        # Reset accumulator on significant motion detection to avoid false positives
        if is_significant_motion:
            self._motion_accumulator = np.zeros((height, width), dtype=np.float32)
        
        # Update previous frame for next comparison
        self._previous_frame = current_gray.copy()
        
        return is_significant_motion

    def _calculate_quality_score(
        self, 
        frame_data: np.ndarray
    ) -> float:
        """Calculates a quality score for the frame.

        Quality scoring considers multiple factors to ensure keyframes are useful:
        - Motion content (dynamic scenes)
        - Contrast (good lighting conditions)
        - Edge density (structural information)

        Args:
            frame_data: Image data (H, W, C) in BGR format

        Returns:
            Quality score between 0.0 and 1.0
        """
        height, width, channels = frame_data.shape
        
        # Normalize to [0, 1] range
        normalized = frame_data.astype(np.float32) / 255.0
        
        # Calculate contrast (standard deviation of pixel values)
        contrast = np.std(normalized)
        contrast_score = min(contrast / 0.5, 1.0)  # Normalize to [0, 1]
        
        # Calculate edge density using Sobel operator
        gray = cv2.cvtColor(frame_data, cv2.COLOR_BGR2GRAY)
        sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        edges = np.sqrt(sobel_x**2 + sobel_y**2)
        edge_density = np.mean(edges) / 255.0
        edge_score = min(edge_density * 5, 1.0)  # Scale to reasonable range
        
        # Calculate color diversity (good for texture-rich scenes)
        if channels == 3:
            color_variance = np.var(frame_data.astype(np.float32))
            color_score = min(color_variance / (255**2), 1.0)
        else:
            color_score = 0.5  # Default for grayscale
        
        # Combine scores with weights
        quality_score = (
            self.config.quality_weight_motion * contrast_score +
            self.config.quality_weight_contrast * edge_score +
            self.config.quality_weight_edges * color_score
        )
        
        return max(0.0, min(1.0, quality_score))

    def reset(self):
        """Resets the extractor state for a new video sequence."""
        # Initialize to negative infinity so first frame always passes time check if needed
        self._last_extraction_time = float('-inf')
        self._last_keyframe_timestamp = 0.0
        self._motion_accumulator = None
        self._previous_frame = None
        self._extraction_count = 0

    def get_stats(self) -> dict:
        """Returns current extractor statistics."""
        return {
            'extraction_count': self._extraction_count,
            'last_extraction_time': self._last_extraction_time,
            'last_keyframe_timestamp': self._last_keyframe_timestamp,
            'config': vars(self.config)
        }

    def set_config(self, config: KeyframeConfig):
        """Updates the extraction configuration.

        Args:
            config: New configuration to apply
        """
        self.config = config


# Convenience function for quick extraction with defaults
def extract_keyframes(
    frame_data: np.ndarray, 
    timestamp: float, 
    stream_id: str
) -> List[KeyframeResult]:
    """Quick keyframe extraction using default settings.

    Args:
        frame_data: Image data (H, W, C) in BGR format
        timestamp: Frame timestamp in seconds
        stream_id: Identifier for the source stream

    Returns:
        List of KeyframeResult objects
    """
    extractor = KeyframeExtractor()
    return extractor.extract(frame_data, timestamp, stream_id)


# Utility function to compare two frames and get similarity score
def frame_similarity(
    frame1: np.ndarray, 
    frame2: np.ndarray,
    threshold: float = 0.85
) -> Tuple[float, bool]:
    """Calculates similarity between two frames.

    Args:
        frame1: First frame (H, W, C) in BGR format
        frame2: Second frame (H, W, C) in BGR format
        threshold: Similarity threshold for "similar" classification

    Returns:
        Tuple of (similarity_score, is_similar) where similarity_score is 0-1
    """
    if frame1.shape != frame2.shape or frame1.size == 0:
        return 0.0, False
    
    # Convert to grayscale and normalize
    gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
    gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
    
    # Calculate correlation coefficient
    correlation = np.corrcoef(gray1.flatten(), gray2.flatten())[0, 1]
    
    if np.isnan(correlation):
        return 0.0, False
    
    similarity = max(0.0, min(1.0, (correlation + 1) / 2))  # Map [-1, 1] to [0, 1]
    is_similar = similarity >= threshold
    
    return similarity, is_similar
