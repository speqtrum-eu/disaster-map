"""Base SLAM Engine Abstract Interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
import numpy as np


@dataclass
class PoseEstimate:
    """3D Camera pose estimate with uncertainty metrics.
    
    Attributes:
        position: 3D position in meters [x, y, z]
        orientation: Quaternion [w, x, y, z] or Euler angles [roll, pitch, yaw]
        covariance: 6x6 covariance matrix for pose uncertainty
        timestamp: Frame capture timestamp in seconds
        confidence: Confidence score (0.0-1.0)
    """
    position: np.ndarray = field(default_factory=lambda: np.zeros(3))
    orientation: Optional[np.ndarray] = None
    covariance: Optional[np.ndarray] = None
    timestamp: float = 0.0
    confidence: float = 0.0
    
    def __post_init__(self):
        if self.position.shape != (3,):
            raise ValueError("Position must be a 3-element array")
        if self.orientation is not None and self.orientation.shape != (4,):
            raise ValueError("Orientation quaternion must be a 4-element array")


@dataclass
class MapState:
    """Current state of the SLAM map.
    
    Attributes:
        num_keyframes: Total number of keyframes in map
        num_features: Total tracked features
        num_points: Number of points in point cloud
        volume: Estimated mapped volume in cubic meters
        drift_error: Cumulative drift error estimate
        last_update: Timestamp of last map update
    """
    num_keyframes: int = 0
    num_features: int = 0
    num_points: int = 0
    volume: float = 0.0
    drift_error: float = 0.0
    last_update: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert map state to dictionary for serialization."""
        return {
            "num_keyframes": self.num_keyframes,
            "num_features": self.num_features,
            "num_points": self.num_points,
            "volume": round(self.volume, 2),
            "drift_error": round(self.drift_error, 4),
            "last_update": self.last_update,
        }


@dataclass
class SLAMConfig:
    """Configuration for SLAM engine initialization.
    
    Attributes:
        camera_width: Camera image width in pixels
        camera_height: Camera image height in pixels
        focal_length: Focal length in pixels (or None to auto-detect)
        principal_point: Principal point [cx, cy] or None for center
        frame_rate: Expected video frame rate
        max_keyframes: Maximum number of keyframes to store
        feature_density: Feature density per square meter
        optimization_interval: Number of frames between optimizations
    """
    camera_width: int = 640
    camera_height: int = 480
    focal_length: Optional[float] = None
    principal_point: Optional[np.ndarray] = None
    frame_rate: float = 30.0
    max_keyframes: int = 1000
    feature_density: float = 50.0
    optimization_interval: int = 10
    
    def __post_init__(self):
        if self.focal_length is None:
            # Auto-detect focal length from image dimensions
            aspect_ratio = self.camera_width / self.camera_height
            self.focal_length = max(self.camera_width, self.camera_height) * 0.5


class BaseSLAMEngine(ABC):
    """Abstract base class for SLAM engines.
    
    All SLAM implementations must provide:
    - initialize(): Setup engine with camera parameters
    - process_frame(): Process a new video frame
    - get_pose(): Retrieve current pose estimate
    - reset(): Clear all state and start fresh
    
    Subclasses should optimize for:
    - Real-time performance (30-60 FPS)
    - Low memory footprint (<1GB typical usage)
    - Robust tracking in challenging conditions
    """
    
    def __init__(self, config: Optional[SLAMConfig] = None):
        """Initialize SLAM engine with configuration.
        
        Args:
            config: SLAM configuration parameters (optional)
        """
        self.config = config or SLAMConfig()
        self._initialized = False
        self._running = False
        self._pose_history: List[PoseEstimate] = []
        self._keyframes: List[Dict[str, Any]] = []
        
    @abstractmethod
    def initialize(self) -> bool:
        """Initialize SLAM engine with camera parameters.
        
        Returns:
            True if initialization successful, False otherwise
        """
        pass
    
    @abstractmethod
    def process_frame(
        self, 
        frame: np.ndarray, 
        timestamp: float = 0.0
    ) -> PoseEstimate:
        """Process a new video frame and extract pose estimate.
        
        Args:
            frame: RGB/BGR image as numpy array (H, W, 3)
            timestamp: Frame capture time in seconds
            
        Returns:
            PoseEstimate with camera position and orientation
        """
        pass
    
    @abstractmethod
    def get_pose(self) -> Optional[PoseEstimate]:
        """Get current pose estimate.
        
        Returns:
            Current pose estimate or None if not available
        """
        pass
    
    @abstractmethod
    def reset(self):
        """Reset engine and clear all state."""
        pass
    
    def get_map_state(self) -> MapState:
        """Get current map state summary.
        
        Returns:
            MapState with statistics about the mapped area
        """
        return MapState(
            num_keyframes=len(self._keyframes),
            num_features=0,  # Override in subclasses
            num_points=0,   # Override in subclasses
            volume=0.0,     # Calculate from keyframe positions
            drift_error=0.0,  # Estimate from pose history
            last_update=self.config.frame_rate,
        )
    
    def get_pose_history(self, limit: int = 100) -> List[PoseEstimate]:
        """Get recent pose estimates for trajectory visualization.
        
        Args:
            limit: Maximum number of poses to return
            
        Returns:
            List of recent PoseEstimate objects
        """
        return self._pose_history[-limit:] if self._pose_history else []
    
    def is_tracking(self) -> bool:
        """Check if SLAM engine is actively tracking.
        
        Returns:
            True if tracking successfully, False otherwise
        """
        return hasattr(self, '_tracking') and self._tracking
    
    @property
    def running(self) -> bool:
        """Check if engine is currently running."""
        return self._running
    
    @property
    def initialized(self) -> bool:
        """Check if engine has been initialized."""
        return self._initialized
