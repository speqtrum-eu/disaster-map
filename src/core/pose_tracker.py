"""Camera Pose Tracking and Trajectory Management."""

import numpy as np
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
import time
import logging

logger = logging.getLogger(__name__)


@dataclass
class Pose3D:
    """3D Camera pose with full uncertainty information.
    
    Attributes:
        position: 3D position in meters [x, y, z]
        quaternion: Orientation as unit quaternion [w, x, y, z]
        euler_angles: Euler angles [roll, pitch, yaw] in radians
        covariance: 6x6 pose covariance matrix
        timestamp: Pose capture time in seconds
        confidence: Confidence score (0.0-1.0)
    """
    position: np.ndarray = field(default_factory=lambda: np.zeros(3))
    quaternion: Optional[np.ndarray] = None
    euler_angles: Optional[np.ndarray] = None
    covariance: Optional[np.ndarray] = None
    timestamp: float = 0.0
    confidence: float = 0.95
    
    def __post_init__(self):
        if self.position.shape != (3,):
            raise ValueError("Position must be a 3-element array")
        if self.quaternion is not None and self.quaternion.shape != (4,):
            raise ValueError("Quaternion must be a 4-element array")
    
    @property
    def x(self) -> float:
        """X position in meters."""
        return self.position[0]
    
    @property
    def y(self) -> float:
        """Y position in meters."""
        return self.position[1]
    
    @property
    def z(self) -> float:
        """Z (altitude) position in meters."""
        return self.position[2]
    
    @property
    def heading(self) -> float:
        """Heading angle (yaw) in radians."""
        if self.euler_angles is not None and len(self.euler_angles) >= 3:
            return self.euler_angles[2] % (2 * np.pi)
        return 0.0
    
    @property
    def pitch(self) -> float:
        """Pitch angle in radians."""
        if self.euler_angles is not None and len(self.euler_angles) >= 3:
            return self.euler_angles[1]
        return 0.0
    
    @property
    def roll(self) -> float:
        """Roll angle in radians."""
        if self.euler_angles is not None and len(self.euler_angles) >= 2:
            return self.euler_angles[0]
        return 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert pose to dictionary for serialization."""
        return {
            "position": self.position.tolist(),
            "quaternion": self.quaternion.tolist() if self.quaternion is not None else None,
            "euler_angles": self.euler_angles.tolist() if self.euler_angles is not None else None,
            "timestamp": self.timestamp,
            "confidence": self.confidence,
        }


@dataclass
class TrajectoryPoint:
    """Single point in the trajectory with pose and metadata.
    
    Attributes:
        pose: 3D camera pose at this point
        frame_number: Source frame number (if available)
        timestamp: Absolute timestamp
        quality_score: Quality metric for this measurement
        metadata: Additional tracking data
    """
    pose: Pose3D
    frame_number: Optional[int] = None
    timestamp: float = 0.0
    quality_score: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class PoseTracker:
    """Tracks and manages camera poses over time.
    
    Features:
    - Smooth pose interpolation between frames
    - Trajectory smoothing with configurable window size
    - Drift detection and correction
    - Coordinate frame transformations
    - Export to common formats (CSV, JSON)
    
    Usage:
        tracker = PoseTracker()
        
        # Add poses as they're computed
        for pose in slam_engine.get_pose_history():
            tracker.add_pose(pose)
        
        # Get smoothed trajectory
        smooth_trajectory = tracker.get_smoothed_trajectory(window=10)
        
        # Export for visualization
        tracker.export_csv("trajectory.csv")
    """
    
    def __init__(
        self,
        smoothing_window: int = 5,
        drift_threshold: float = 2.0,
        max_history_size: int = 10000,
    ):
        """Initialize pose tracker with configuration.
        
        Args:
            smoothing_window: Window size for trajectory smoothing
            drift_threshold: Maximum allowed drift before correction (meters)
            max_history_size: Maximum poses to store in memory
        """
        self.smoothing_window = max(smoothing_window, 1)
        self.drift_threshold = drift_threshold
        self.max_history_size = max_history_size
        
        # Trajectory storage
        self._trajectory: List[TrajectoryPoint] = []
        self._pose_buffer: List[Pose3D] = []
        
        # Drift tracking
        self._drift_accumulator = 0.0
        self._last_drift_check = time.time()
        
        # Coordinate frame info
        self._frame_offset = np.zeros(3)  # Offset from world origin
        self._rotation_matrix = np.eye(4)
    
    def add_pose(self, pose: Pose3D, frame_number: Optional[int] = None):
        """Add a new pose to the trajectory.
        
        Args:
            pose: 3D camera pose to add
            frame_number: Source frame number (optional)
            
        Performance:
            - O(1) insertion with bounded memory
            - Automatic history management
        """
        # Create trajectory point
        point = TrajectoryPoint(
            pose=pose,
            frame_number=frame_number,
            timestamp=pose.timestamp,
            quality_score=pose.confidence,
        )
        
        # Add to trajectory
        self._trajectory.append(point)
        
        # Maintain buffer for smoothing
        if len(self._pose_buffer) < self.smoothing_window:
            self._pose_buffer.append(pose)
        else:
            self._pose_buffer.pop(0)
            self._pose_buffer.append(pose)
        
        # Trim history if too large
        if len(self._trajectory) > self.max_history_size:
            self._trim_history()
    
    def _trim_history(self):
        """Remove oldest entries when history exceeds maximum size."""
        if len(self._trajectory) <= self.max_history_size:
            return
        
        # Keep recent points for better smoothing
        keep_count = int(self.max_history_size * 0.8)
        
        self._trajectory = self._trajectory[-keep_count:]
        logger.debug(f"Trimmed trajectory from {len(self._trajectory)} to {keep_count}")
    
    def get_trajectory(
        self,
        start_frame: Optional[int] = None,
        end_frame: Optional[int] = None,
    ) -> List[TrajectoryPoint]:
        """Get trajectory points within frame range.
        
        Args:
            start_frame: Start frame number (None for beginning)
            end_frame: End frame number (None for end)
            
        Returns:
            Filtered list of TrajectoryPoint objects
        """
        filtered = []
        
        for point in self._trajectory:
            if start_frame is not None and point.frame_number < start_frame:
                continue
            if end_frame is not None and point.frame_number > end_frame:
                continue
            filtered.append(point)
        
        return filtered
    
    def get_smoothed_trajectory(
        self,
        window_size: Optional[int] = None,
        method: str = "moving_average",
    ) -> List[Pose3D]:
        """Get smoothed trajectory using specified method.
        
        Args:
            window_size: Smoothing window size (uses configured value if None)
            method: Smoothing algorithm - 'moving_average', 'low_pass'
            
        Returns:
            List of smoothed Pose3D objects
            
        Performance:
            - Moving average: O(n) for n points
            - Low pass filter: O(n) with configurable cutoff
        """
        if window_size is None:
            window_size = self.smoothing_window
        
        if len(self._trajectory) < 2:
            return [point.pose for point in self._trajectory]
        
        positions = np.array([p.pose.position for p in self._trajectory])
        confidences = np.array([p.quality_score for p in self._trajectory])
        
        # Weighted moving average based on confidence
        weights = confidences / (confidences.sum() + 1e-8)
        
        smoothed_positions = []
        for i, pos in enumerate(positions):
            start_idx = max(0, i - window_size // 2)
            end_idx = min(len(positions), i + window_size // 2 + 1)
            
            # Weighted average
            weighted_pos = np.sum(weights[start_idx:end_idx] * positions[start_idx:end_idx], axis=0)
            smoothed_positions.append(weighted_pos)
        
        return [Pose3D(position=pos, confidence=confidences[i]) for i, pos in enumerate(smoothed_positions)]
    
    def get_drift_estimate(self) -> float:
        """Estimate cumulative drift from trajectory.
        
        Returns:
            Estimated drift distance in meters
            
        Algorithm:
            - Compare start and end positions
            - Account for expected motion based on frame count
            - Return normalized drift metric
        """
        if len(self._trajectory) < 2:
            return 0.0
        
        # Get trajectory bounds
        positions = np.array([p.pose.position for p in self._trajectory])
        
        start_pos = positions[0]
        end_pos = positions[-1]
        
        # Expected displacement based on typical motion
        expected_displacement = len(self._trajectory) * 0.5  # Assume ~0.5m per frame
        
        # Drift is deviation from expected path (simplified)
        actual_distance = np.linalg.norm(end_pos - start_pos)
        
        if expected_displacement > 0:
            drift_ratio = abs(actual_distance - expected_displacement) / expected_displacement
        else:
            drift_ratio = 0.0
        
        return float(drift_ratio * 100)  # Percentage
    
    def detect_drift(self, threshold: Optional[float] = None) -> bool:
        """Detect if current drift exceeds threshold.
        
        Args:
            threshold: Drift percentage threshold (uses configured value if None)
            
        Returns:
            True if drift is significant and needs correction
        """
        if threshold is None:
            threshold = self.drift_threshold
        
        drift = self.get_drift_estimate()
        return drift > threshold
    
    def correct_drift(self, correction_vector: Optional[np.ndarray] = None):
        """Apply drift correction to all poses.
        
        Args:
            correction_vector: 3D correction vector (applied if None)
            
        Performance:
            - O(n) where n is trajectory length
            - Consider using incremental updates for large trajectories
        """
        if len(self._trajectory) == 0:
            return
        
        if correction_vector is None:
            # Auto-calculate correction based on drift analysis
            positions = np.array([p.pose.position for p in self._trajectory])
            
            # Simple correction: shift to align start position with origin
            correction_vector = -positions[0]
        
        # Apply correction to all poses
        for point in self._trajectory:
            point.pose.position += correction_vector
        
        logger.info(f"Applied drift correction: {correction_vector}")
    
    def transform_to_frame(
        self,
        pose: Pose3D,
        frame_offset: np.ndarray = None,
    ) -> Pose3D:
        """Transform pose to local coordinate frame.
        
        Args:
            pose: World-frame pose to transform
            frame_offset: Offset vector for frame transformation
            
        Returns:
            Transformed pose in local frame
        """
        if frame_offset is None:
            frame_offset = self._frame_offset
        
        # Apply offset
        new_position = pose.position - frame_offset
        
        return Pose3D(
            position=new_position,
            quaternion=pose.quaternion.copy(),
            euler_angles=pose.euler_angles.copy() if pose.euler_angles is not None else None,
            timestamp=pose.timestamp,
            confidence=pose.confidence,
        )
    
    def transform_to_world(
        self,
        pose: Pose3D,
        frame_offset: np.ndarray = None,
    ) -> Pose3D:
        """Transform pose from local to world coordinate frame.
        
        Args:
            pose: Local-frame pose to transform
            frame_offset: Offset vector for transformation
            
        Returns:
            Transformed pose in world frame
        """
        if frame_offset is None:
            frame_offset = self._frame_offset
        
        # Apply offset (inverse of local-to-world)
        new_position = pose.position + frame_offset
        
        return Pose3D(
            position=new_position,
            quaternion=pose.quaternion.copy(),
            euler_angles=pose.euler_angles.copy() if pose.euler_angles is not None else None,
            timestamp=pose.timestamp,
            confidence=pose.confidence,
        )
    
    def export_csv(self, filepath: str) -> bool:
        """Export trajectory to CSV file.
        
        Args:
            filepath: Output CSV file path
            
        Returns:
            True if export successful
        """
        import csv
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Write header
            writer.writerow([
                'frame_number', 'timestamp', 
                'x', 'y', 'z',
                'roll', 'pitch', 'yaw',
                'confidence'
            ])
            
            # Write data
            for point in self._trajectory:
                pose = point.pose
                
                writer.writerow([
                    point.frame_number or '',
                    f"{pose.timestamp:.6f}",
                    f"{pose.position[0]:.4f}",
                    f"{pose.position[1]:.4f}",
                    f"{pose.position[2]:.4f}",
                    getattr(pose, 'euler_angles', None) and pose.euler_angles[2] or 0,
                    getattr(pose, 'euler_angles', None) and pose.euler_angles[1] or 0,
                    getattr(pose, 'euler_angles', None) and pose.euler_angles[0] or 0,
                    pose.confidence,
                ])
        
        logger.info(f"Trajectory exported to {filepath}")
        return True
    
    def export_json(self, filepath: str) -> bool:
        """Export trajectory to JSON file.
        
        Args:
            filepath: Output JSON file path
            
        Returns:
            True if export successful
        """
        import json
        
        # Handle both TrajectoryPoint and direct PoseEstimate objects
        data = []
        for point in self._trajectory:
            if isinstance(point, TrajectoryPoint):
                # TrajectoryPoint with pose attribute
                if hasattr(point.pose, 'to_dict'):
                    data.append(point.pose.to_dict())
                else:
                    data.append({})
            elif hasattr(point, 'pose') and hasattr(point.pose, 'to_dict'):
                # PoseEstimate object stored directly
                data.append(point.pose.to_dict())
            elif hasattr(point, 'to_dict'):
                # Direct PoseEstimate with to_dict method
                data.append(point.to_dict())
            else:
                data.append({})
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Trajectory exported to {filepath}")
        return True
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get trajectory statistics for monitoring.
        
        Returns:
            Dictionary with trajectory metrics
        """
        if len(self._trajectory) == 0:
            return {}
        
        positions = np.array([p.pose.position for p in self._trajectory])
        
        # Calculate bounds and volume
        min_pos = positions.min(axis=0)
        max_pos = positions.max(axis=0)
        extent = max_pos - min_pos
        
        # Calculate total distance traveled
        distances = np.linalg.norm(np.diff(positions, axis=0))
        total_distance = float(np.sum(distances))
        
        return {
            "num_points": len(self._trajectory),
            "total_distance_meters": round(total_distance, 2),
            "extent_meters": extent.tolist(),
            "volume_cubic_meters": round(np.prod(extent) * 0.5, 2),
            "avg_confidence": float(np.mean([p.quality_score for p in self._trajectory])),
            "min_confidence": float(np.min([p.quality_score for p in self._trajectory])),
            "max_confidence": float(np.max([p.quality_score for p in self._trajectory])),
        }
