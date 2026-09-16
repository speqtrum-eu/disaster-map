"""Vision engine configuration and constants."""

from dataclasses import dataclass
from typing import Optional, List
import numpy as np


@dataclass
class VisionConfig:
    """Configuration for the vision engine pipeline."""
    
    # Feature extraction settings
    feature_extractor: str = "superpoint"  # superpoint | superglue | lightglue
    feature_keypoints_threshold: float = 0.01  # Keypoint density threshold
    feature_descriptor_size: int = 64  # Descriptor dimension
    
    # Matching settings
    matcher: str = "superglue"  # superglue | lightglue
    match_confidence_threshold: float = 0.75  # Minimum confidence for matches
    max_matches_per_pair: int = 1000  # Maximum matches to keep
    
    # SfM solver settings
    sfm_solver: str = "ceres"  # ceres | colmap
    bundle_adjustment_iterations: int = 20
    pose_refinement_threshold: float = 1e-6  # Convergence threshold
    
    # Pose estimation settings
    relative_pose_method: str = "essential"  # essential | fundamental
    ransac_reproj_threshold: float = 3.0  # RANSAC reprojection error threshold
    min_triangles_for_absolute_pose: int = 5  # Minimum triangles for absolute pose
    
    # Multi-stream fusion settings
    enable_multi_stream_fusion: bool = True
    fusion_method: str = "kalman"  # kalman | weighted_average | consensus
    sensor_fusion_enabled: bool = True  # Fuse GPS/IMU data
    
    # Performance settings
    gpu_acceleration: bool = True
    batch_size: int = 32  # For batch processing
    max_concurrent_streams: int = 30
    
    # Accuracy requirements
    target_accuracy_meters: float = 0.5  # Sub-meter accuracy target
    pose_smoothing_window: int = 10  # Moving average window for smoothing


@dataclass
class StreamConfig:
    """Configuration for a specific video stream."""
    
    stream_id: str
    expected_fps: float = 30.0
    resolution_width: int = 640
    resolution_height: int = 480
    use_gps_fusion: bool = True
    use_imu_fusion: bool = False


@dataclass
class PipelineStats:
    """Statistics for pipeline performance monitoring."""
    
    frames_processed: int = 0
    feature_extraction_time_ms: float = 0.0
    matching_time_ms: float = 0.0
    pose_estimation_time_ms: float = 0.0
    total_latency_ms: float = 0.0
    
    @property
    def avg_latency_ms(self) -> float:
        """Average latency per frame."""
        if self.frames_processed == 0:
            return 0.0
        return self.total_latency_ms / self.frames_processed


# Default configuration constants
DEFAULT_FEATURE_RESOLUTION = (640, 480)
DEFAULT_DESCRIPTOR_SIZE = 64
DEFAULT_MATCH_CONFIDENCE = 0.75
DEFAULT_RANSAC_THRESHOLD = 3.0
