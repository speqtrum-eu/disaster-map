"""Keyframe Selection and Management for Efficient SLAM."""

import numpy as np
from typing import Optional, List, Dict, Any, Tuple, Callable
from dataclasses import dataclass, field
import time
import logging
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class Keyframe:
    """Represents a keyframe in the SLAM map.
    
    Attributes:
        frame_id: Unique identifier for this keyframe
        timestamp: Capture timestamp in seconds
        pose: Camera pose at capture time
        image_hash: Hash of image content for change detection
        feature_count: Number of tracked features in this frame
        landmarks: Detected 3D landmarks (optional)
        metadata: Additional keyframe data
    """
    frame_id: int
    timestamp: float
    pose: Dict[str, Any]
    image_hash: str = ""
    feature_count: int = 0
    landmarks: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert keyframe to dictionary for serialization."""
        return {
            "frame_id": self.frame_id,
            "timestamp": self.timestamp,
            "pose": self.pose,
            "image_hash": self.image_hash,
            "feature_count": self.feature_count,
            "landmarks": self.landmarks[:10],  # Limit for serialization
            "metadata": self.metadata,
        }


@dataclass
class KeyframeSelectionConfig:
    """Configuration for keyframe selection algorithm.
    
    Attributes:
        max_keyframes: Maximum number of keyframes to store
        motion_threshold: Minimum motion required between keyframes (meters)
        feature_change_threshold: Minimum feature change percentage
        time_interval: Time interval between forced keyframes (seconds)
        landmark_density: Required landmark density for keyframe
        quality_score_min: Minimum pose confidence for keyframe
    """
    max_keyframes: int = 1000
    motion_threshold: float = 2.0  # meters
    feature_change_threshold: float = 0.3  # 30% change
    time_interval: float = 5.0  # seconds
    landmark_density: float = 10.0  # landmarks per square meter
    quality_score_min: float = 0.85


class KeyframeManager:
    """Manages keyframe selection and storage for efficient SLAM operation.
    
    Features:
    - Adaptive keyframe selection based on motion and feature change
    - Memory-efficient storage with configurable limits
    - Landmark association across keyframes
    - Loop closure detection support
    - Export/import for map persistence
    
    Keyframe Selection Strategy:
    ```
    ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
    │  Frame N-1  │───►│   Frame N   │───►│  Frame N+1  │
    │             │     │             │     │             │
    │  Pose: P₁   │     │  Pose: P₂   │     │  Pose: P₃   │
    │  Features: F₁│     │  Features: F₂│     │  Features: F₃│
    └──────┬──────┘     └──────┬──────┘     └──────┬──────┘
          │                   │                   │
          ▼                   ▼                   ▼
    Motion > threshold?   Feature change > thresh?  Time interval exceeded?
          │                   │                   │
          └─────────┬─────────┴─────────┬─────────┘
                    │                   │
                    ▼                   ▼
              Add Keyframe        Skip Frame
    ```
    
    Usage:
        manager = KeyframeManager(config)
        
        # Process frames and select keyframes
        for frame_data in video_stream:
            pose = slam_engine.process_frame(frame_data.image, frame_data.timestamp)
            
            if manager.should_add_keyframe(pose):
                keyframe = manager.create_keyframe(
                    frame_id=manager.frame_counter,
                    timestamp=pose.timestamp,
                    pose=pose.to_dict(),
                )
                manager.add_keyframe(keyframe)
    
    Performance:
    - Keyframe selection: <1ms per frame
    - Memory usage: O(max_keyframes * avg_frame_size)
    """
    
    def __init__(self, config: Optional[KeyframeSelectionConfig] = None):
        """Initialize keyframe manager with configuration.
        
        Args:
            config: Keyframe selection configuration (optional)
        """
        self.config = config or KeyframeSelectionConfig()
        
        # Keyframe storage
        self._keyframes: List[Keyframe] = []
        self._pose_history: List[Dict[str, Any]] = []
        self._feature_history: List[List[int]] = []  # Feature IDs per frame
        
        # Selection state
        self._last_keyframe_pose = None
        self._last_keyframe_features = None
        self._motion_accumulator = 0.0
        self._time_since_last_keyframe = 0.0
        
        # Statistics
        self._selection_count = 0
        self._skipped_count = 0
        self._total_frames_processed = 0
    
    def should_add_keyframe(
        self, 
        pose: Dict[str, Any],
        features: Optional[List[int]] = None,
    ) -> bool:
        """Determine if current frame should be added as keyframe.
        
        Args:
            pose: Current camera pose (dictionary)
            features: List of tracked feature IDs in this frame
            
        Returns:
            True if frame should be selected as keyframe
        """
        self._total_frames_processed += 1
        
        # Check time interval constraint
        current_time = pose.get('timestamp', time.time())
        self._time_since_last_keyframe = current_time - (
            self._keyframes[-1].timestamp if self._keyframes else 0
        )
        
        if self._time_since_last_keyframe >= self.config.time_interval:
            return True
        
        # Check motion threshold
        last_pose = self._pose_history[-1] if self._pose_history else None
        
        if last_pose is not None:
            current_pos = np.array(pose.get('position', [0, 0, 0]))
            last_pos = np.array(last_pose.get('position', [0, 0, 0]))
            
            motion_distance = np.linalg.norm(current_pos - last_pos)
            self._motion_accumulator += motion_distance
            
            if motion_distance >= self.config.motion_threshold:
                return True
        
        # Check feature change threshold
        if features is not None and self._last_keyframe_features is not None:
            current_feature_set = set(features)
            last_feature_set = set(self._last_keyframe_features)
            
            # Calculate feature change percentage
            union_size = len(current_feature_set | last_feature_set)
            intersection_size = len(current_feature_set & last_feature_set)
            
            if union_size > 0:
                feature_change = 1.0 - (intersection_size / union_size)
                
                if feature_change >= self.config.feature_change_threshold:
                    return True
        
        # Check landmark density requirement
        if features is not None and len(features) > 0:
            # Estimate area from motion
            if last_pose is not None:
                motion_area = max(
                    np.linalg.norm(current_pos - last_pos),
                    self.config.motion_threshold / 2,
                ) ** 2
                
                landmark_density = len(features) / motion_area
                
                if landmark_density >= self.config.landmark_density:
                    return True
        
        # Track pose history for future comparisons
        self._pose_history.append(pose)
        
        # Limit pose history size
        if len(self._pose_history) > 100:
            self._pose_history = self._pose_history[-50:]
        
        # Update feature history
        if features is not None:
            self._feature_history.append(features[:100])  # Limit for memory
        
        return False
    
    def create_keyframe(
        self,
        frame_id: int,
        timestamp: float,
        pose: Dict[str, Any],
        image_hash: str = "",
        feature_count: int = 0,
        landmarks: Optional[List[Dict[str, Any]]] = None,
    ) -> Keyframe:
        """Create a new keyframe object.
        
        Args:
            frame_id: Unique identifier for this keyframe
            timestamp: Capture timestamp
            pose: Camera pose at capture time
            image_hash: Hash of image content (for change detection)
            feature_count: Number of tracked features
            landmarks: Associated 3D landmarks
            
        Returns:
            New Keyframe object
        """
        return Keyframe(
            frame_id=frame_id,
            timestamp=timestamp,
            pose=pose.copy(),
            image_hash=image_hash,
            feature_count=feature_count,
            landmarks=landmarks or [],
        )
    
    def add_keyframe(self, keyframe: Keyframe):
        """Add a keyframe to the map.
        
        Args:
            keyframe: Keyframe to add
            
        Raises:
            ValueError: If max keyframes exceeded
        """
        if len(self._keyframes) >= self.config.max_keyframes:
            logger.warning(f"Max keyframes ({self.config.max_keyframes}) reached, removing oldest")
            self._remove_oldest_keyframe()
        
        self._keyframes.append(keyframe)
        self._selection_count += 1
        
        logger.debug(f"Added keyframe #{keyframe.frame_id} at {keyframe.timestamp:.2f}s")
    
    def _remove_oldest_keyframe(self):
        """Remove the oldest keyframe to make room for new ones."""
        if not self._keyframes:
            return
        
        removed = self._keyframes.pop(0)
        logger.debug(f"Removed oldest keyframe #{removed.frame_id}")
    
    def get_keyframe_by_id(self, frame_id: int) -> Optional[Keyframe]:
        """Get a specific keyframe by ID.
        
        Args:
            frame_id: Keyframe identifier
            
        Returns:
            Keyframe or None if not found
        """
        for kf in self._keyframes:
            if kf.frame_id == frame_id:
                return kf
        return None
    
    def get_keyframes_in_range(
        self,
        start_time: float = 0.0,
        end_time: Optional[float] = None,
    ) -> List[Keyframe]:
        """Get keyframes within a time range.
        
        Args:
            start_time: Start timestamp (inclusive)
            end_time: End timestamp (exclusive, None for all)
            
        Returns:
            Filtered list of Keyframe objects
        """
        filtered = []
        
        for kf in self._keyframes:
            if kf.timestamp < start_time:
                continue
            if end_time is not None and kf.timestamp >= end_time:
                break  # Assuming sorted by timestamp
            
            filtered.append(kf)
        
        return filtered
    
    def get_trajectory_keyframes(self, num_points: int = 100) -> List[Keyframe]:
        """Get evenly spaced keyframes for trajectory visualization.
        
        Args:
            num_points: Number of keyframes to return
            
        Returns:
            Evenly distributed subset of keyframes
        """
        if len(self._keyframes) <= num_points:
            return self._keyframes.copy()
        
        # Sample evenly across the timeline
        step = len(self._keyframes) / num_points
        
        sampled = []
        for i in range(num_points):
            index = int(i * step)
            if index < len(self._keyframes):
                sampled.append(self._keyframes[index])
        
        return sampled
    
    def detect_loop_closure(
        self, 
        current_pose: Dict[str, Any],
        tolerance: float = 5.0,
    ) -> Optional[Keyframe]:
        """Detect potential loop closure with existing keyframes.
        
        Args:
            current_pose: Current camera pose
            tolerance: Position matching tolerance in meters
            
        Returns:
            Matching keyframe or None if no match found
        """
        current_pos = np.array(current_pose.get('position', [0, 0, 0]))
        
        for kf in self._keyframes[-100:]:  # Check last 100 keyframes
            kf_pos = np.array(kf.pose.get('position', [0, 0, 0]))
            
            distance = np.linalg.norm(current_pos - kf_pos)
            
            if distance <= tolerance:
                return kf
        
        return None
    
    def get_map_statistics(self) -> Dict[str, Any]:
        """Get statistics about the keyframe map.
        
        Returns:
            Dictionary with map metrics
        """
        if not self._keyframes:
            return {}
        
        positions = np.array([kf.pose.get('position', [0, 0, 0]) for kf in self._keyframes])
        
        # Calculate mapped area
        min_pos = positions.min(axis=0)
        max_pos = positions.max(axis=0)
        extent = max_pos - min_pos
        
        return {
            "num_keyframes": len(self._keyframes),
            "total_frames_processed": self._total_frames_processed,
            "selection_rate": round(self._selection_count / max(1, self._total_frames_processed), 4),
            "skipped_frames": self._skipped_count,
            "mapped_extent_meters": extent.tolist(),
            "mapped_volume_cubic_meters": round(np.prod(extent) * 0.5, 2),
            "avg_keyframe_interval_seconds": round(
                (self._keyframes[-1].timestamp - self._keyframes[0].timestamp) 
                / len(self._keyframes), 3
            ) if len(self._keyframes) > 1 else 0.0,
        }
    
    def export_keyframes(self, filepath: str) -> bool:
        """Export all keyframes to file for persistence.
        
        Args:
            filepath: Output file path (JSON format)
            
        Returns:
            True if export successful
        """
        import json
        
        data = [kf.to_dict() for kf in self._keyframes]
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Exported {len(self._keyframes)} keyframes to {filepath}")
        return True
    
    def import_keyframes(self, filepath: str) -> int:
        """Import keyframes from file.
        
        Args:
            filepath: Input JSON file path
            
        Returns:
            Number of keyframes imported
        """
        import json
        
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        for item in data:
            kf = Keyframe(
                frame_id=item['frame_id'],
                timestamp=item['timestamp'],
                pose=item['pose'],
                image_hash=item.get('image_hash', ''),
                feature_count=item.get('feature_count', 0),
                landmarks=item.get('landmarks', []),
            )
            self._keyframes.append(kf)
        
        logger.info(f"Imported {len(data)} keyframes from {filepath}")
        return len(data)
    
    def reset(self):
        """Clear all keyframes and reset state."""
        self._keyframes.clear()
        self._pose_history.clear()
        self._feature_history.clear()
        
        self._last_keyframe_pose = None
        self._last_keyframe_features = None
        self._motion_accumulator = 0.0
        self._time_since_last_keyframe = 0.0
        
        logger.info("Keyframe manager reset complete")


class AdaptiveKeyframeManager(KeyframeManager):
    """Adaptive keyframe selection with dynamic threshold adjustment.
    
    This class automatically adjusts keyframe selection parameters based on:
    - Scene complexity (feature density)
    - Motion characteristics
    - Tracking confidence
    
    Usage:
        manager = AdaptiveKeyframeManager()
        
        # Process frames with adaptive selection
        for frame_data in video_stream:
            pose = slam_engine.process_frame(frame_data.image, frame_data.timestamp)
            
            if manager.should_add_keyframe(pose):
                manager.add_keyframe(...)
    """
    
    def __init__(self, config: Optional[KeyframeSelectionConfig] = None):
        super().__init__(config)
        
        # Adaptive parameters
        self._motion_threshold_base = self.config.motion_threshold
        self._feature_change_base = self.config.feature_change_threshold
        
        # Running statistics for adaptation
        self._avg_motion = 0.5  # meters per frame
        self._avg_feature_count = 100
        self._confidence_history: List[float] = []
        
        # Adaptation factors (0.0-2.0)
        self._motion_factor = 1.0
        self._feature_factor = 1.0
    
    def update_adaptation(self, pose: Dict[str, Any], features: Optional[List[int]] = None):
        """Update adaptation parameters based on current frame data.
        
        Args:
            pose: Current camera pose
            features: Tracked feature IDs (optional)
        """
        # Update motion statistics
        if len(self._pose_history) > 1:
            last_pos = np.array(self._pose_history[-2].get('position', [0, 0, 0]))
            current_pos = np.array(pose.get('position', [0, 0, 0]))
            
            motion = np.linalg.norm(current_pos - last_pos)
            self._avg_motion = (self._avg_motion * 0.9 + motion * 0.1)
        
        # Update feature statistics
        if features is not None:
            self._avg_feature_count = (
                self._avg_feature_count * 0.95 + len(features) * 0.05
            )
        
        # Update confidence history
        confidence = pose.get('confidence', 1.0)
        self._confidence_history.append(confidence)
        
        if len(self._confidence_history) > 20:
            self._confidence_history.pop(0)
    
    def get_adaptive_thresholds(self) -> Dict[str, float]:
        """Get current adaptive thresholds for keyframe selection.
        
        Returns:
            Dictionary with current threshold values
        """
        # Adjust motion threshold based on scene complexity
        if self._avg_feature_count > 200:
            # High feature density - reduce motion requirement
            self._motion_factor = max(0.5, min(1.5, 1.0 + (self._avg_feature_count - 200) / 1000))
        elif self._avg_feature_count < 50:
            # Low feature density - increase motion requirement
            self._motion_factor = max(0.5, min(2.0, 1.0 + (50 - self._avg_feature_count) / 100))
        
        return {
            "motion_threshold": self._motion_base * self._motion_factor,
            "feature_change_threshold": self._feature_change_base * self._feature_factor,
            "confidence_min": max(0.7, min(1.0, 0.85 + (1 - np.mean(self._confidence_history)) * 0.2),
        }
    
    @property
    def _motion_base(self) -> float:
        """Base motion threshold with adaptation."""
        return self.config.motion_threshold * self._motion_factor
    
    @property
    def _feature_change_base(self) -> float:
        """Base feature change threshold with adaptation."""
        return self.config.feature_change_threshold * self._feature_factor
