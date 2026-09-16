"""Camera pose estimation and tracking with multi-stream fusion.

Vendor-agnostic implementation supporting:
- Relative pose from feature matches (Essential/Fundamental matrices)
- Absolute pose refinement with GPS/IMU sensor fusion
- Multi-stream consensus for robustness
- Sub-meter accuracy optimization

Optimized for real-time performance on central servers.
"""

import numpy as np
from typing import Tuple, Optional, List, Dict, Any
from dataclasses import dataclass
import time


@dataclass
class PoseEstimationResult:
    """Results from pose estimation."""
    
    pose: np.ndarray  # (6,) pose vector [x, y, z, roll, pitch, yaw] or (4,) quaternion + position
    confidence: float = 1.0
    is_absolute: bool = False  # True if absolute pose with GPS/IMU fusion
    processing_time_ms: float = 0.0
    
    @property
    def R(self) -> np.ndarray:
        """Rotation matrix from pose."""
        return _rotation_matrix_from_quaternion(
            self.pose[3] if len(self.pose) > 3 else self.pose[-1],
            self.pose[4] if len(self.pose) > 4 else self.pose[-2],
            self.pose[5] if len(self.pose) > 5 else self.pose[-3],
            self.pose[6] if len(self.pose) > 6 else 0.0,
        )
    
    @property
    def T(self) -> np.ndarray:
        """Translation vector (position)."""
        return self.pose[:3]


@dataclass
class SensorData:
    """Sensor data for pose fusion."""
    
    timestamp: float
    gps_position: Optional[np.ndarray] = None  # (3,) GPS position [lat, lon, alt] or ECEF
    gps_velocity: Optional[np.ndarray] = None  # (3,) velocity vector
    imu_quaternion: Optional[np.ndarray] = None  # (4,) quaternion [w, x, y, z]
    imu_acceleration: Optional[np.ndarray] = None  # (3,) acceleration
    imu_gyro: Optional[np.ndarray] = None  # (3,) angular velocity
    
    @property
    def has_gps(self) -> bool:
        return self.gps_position is not None and np.all(np.abs(self.gps_position) > 1e-8)
    
    @property
    def has_imu(self) -> bool:
        return (self.imu_quaternion is not None or 
                self.imu_acceleration is not None or 
                self.imu_gyro is not None)


@dataclass
class PoseTrackerConfig:
    """Configuration for pose estimation and tracking."""
    
    # Relative pose settings
    use_essential_matrix: bool = True  # Use essential matrix (known depth scale)
    ransac_reproj_threshold: float = 3.0  # RANSAC reprojection error threshold
    
    # Absolute pose fusion
    enable_gps_fusion: bool = True
    enable_imu_fusion: bool = False
    gps_weight: float = 0.5  # Weight for GPS in sensor fusion
    imu_weight: float = 0.3  # Weight for IMU in sensor fusion
    
    # Multi-stream fusion
    use_multi_stream_consensus: bool = True
    consensus_threshold: float = 0.7  # Minimum confidence for consensus
    
    # Accuracy requirements
    target_accuracy_meters: float = 0.5  # Sub-meter accuracy target
    pose_smoothing_enabled: bool = True
    smoothing_window: int = 10  # Moving average window
    
    # Performance
    max_pose_updates_per_second: int = 30  # Limit updates for stability


class PoseEstimatorBase:
    """Abstract base class for pose estimators."""
    
    def __init__(self, config: Optional[PoseTrackerConfig] = None):
        self.config = config or PoseTrackerConfig()
        self._initialized = False
    
    @property
    def estimator_type(self) -> str:
        raise NotImplementedError
    
    def initialize(self) -> bool:
        """Initialize the pose estimator."""
        raise NotImplementedError
    
    def estimate_relative_pose(
        self, 
        matches: np.ndarray,  # (M, 2) match pairs [src_idx, tgt_idx]
        keypoints1: np.ndarray,  # (N1, 2) keypoint coordinates in image 1
        keypoints2: np.ndarray,  # (N2, 2) keypoint coordinates in image 2
        intrinsic_matrix: Optional[np.ndarray] = None
    ) -> PoseEstimationResult:
        """Estimate relative pose from feature matches.
        
        Args:
            matches: Match pairs between two images
            keypoints1: Keypoints in first image
            keypoints2: Keypoints in second image
            intrinsic_matrix: Optional camera intrinsics [3x3]
            
        Returns:
            PoseEstimationResult with relative pose and confidence
        """
        raise NotImplementedError
    
    def estimate_absolute_pose(
        self, 
        relative_pose: np.ndarray,  # (6,) relative pose from previous step
        sensor_data: Optional[SensorData] = None,
        gps_position: Optional[np.ndarray] = None
    ) -> PoseEstimationResult:
        """Refine to absolute pose using sensor fusion.
        
        Args:
            relative_pose: Relative pose from feature matching
            sensor_data: Optional GPS/IMU sensor data
            gps_position: Optional direct GPS position
            
        Returns:
            PoseEstimationResult with absolute pose and confidence
        """
        raise NotImplementedError
    
    def track_pose(
        self, 
        matches: np.ndarray,
        keypoints1: np.ndarray,
        keypoints2: np.ndarray,
        sensor_data: Optional[SensorData] = None,
        previous_pose: Optional[np.ndarray] = None
    ) -> PoseEstimationResult:
        """Full pose estimation pipeline with tracking.
        
        Args:
            matches: Feature match pairs
            keypoints1: Keypoints in reference image
            keypoints2: Keypoints in current image
            sensor_data: Optional GPS/IMU data for fusion
            previous_pose: Previous pose for temporal consistency
            
        Returns:
            PoseEstimationResult with optimized pose
        """
        raise NotImplementedError
    
    def get_stats(self) -> Dict[str, Any]:
        """Get estimator statistics."""
        return {
            "estimator_type": self.estimator_type,
            "initialized": self._initialized,
            "config": vars(self.config),
        }


class PyTorchPoseEstimator(PoseEstimatorBase):
    """PyTorch-based pose estimation with vendor-agnostic GPU support.
    
    Uses learned pose regression for fast relative pose estimation.
    Combines with traditional methods for absolute pose refinement.
    Optimized for sub-meter accuracy in multi-stream fusion.
    """
    
    def __init__(self, config: Optional[PoseTrackerConfig] = None):
        super().__init__(config)
        
        self._model = None
        self._device = "cpu"
        self._previous_pose = None
    
    @property
    def estimator_type(self) -> str:
        return "pytorch_learned"
    
    def initialize(self) -> bool:
        """Initialize PyTorch pose estimation model."""
        try:
            import torch
            
            # Use vendor-agnostic GPU backend
            if self.config.pose_smoothing_enabled and FeaturePose._is_gpu_available():
                from src.vision.gpu import get_gpu_backend
                
                backend = get_gpu_backend()
                
                if hasattr(backend, 'name') and backend.name == "cuda":
                    self._device = f"cuda:{self.config.gpu_device}"
                else:
                    self._device = "cpu"
                
                torch.set_default_device(self._device)
            else:
                self._device = "cpu"
            
            # Load pose regression model (optional - can use traditional methods only)
            if hasattr(self, '_load_pose_model'):
                try:
                    self._model = _load_pose_regression_model()
                    if hasattr(self._model, 'eval'):
                        self._model.eval()
                except Exception as e:
                    print(f"Failed to load pose regression model (using traditional methods): {e}")
            
            self._initialized = True
            return True
            
        except Exception as e:
            print(f"Failed to initialize PyTorch pose estimator: {e}")
            return False
    
    def estimate_relative_pose(
        self, 
        matches: np.ndarray, 
        keypoints1: np.ndarray, 
        keypoints2: np.ndarray,
        intrinsic_matrix: Optional[np.ndarray] = None
    ) -> PoseEstimationResult:
        """Estimate relative pose using learned regression + RANSAC."""
        start_time = time.time()
        
        # Use traditional Essential matrix method as primary approach
        result = _estimate_essential_pose(
            matches, keypoints1, keypoints2, intrinsic_matrix,
            ransac_threshold=self.config.ransac_reproj_threshold
        )
        
        processing_time_ms = (time.time() - start_time) * 1000
        
        return PoseEstimationResult(
            pose=result['pose'],
            confidence=min(1.0, result['confidence'] / 2.0),  # Normalize to [0, 1]
            is_absolute=False,
            processing_time_ms=processing_time_ms
        )
    
    def estimate_absolute_pose(
        self, 
        relative_pose: np.ndarray,
        sensor_data: Optional[SensorData] = None,
        gps_position: Optional[np.ndarray] = None
    ) -> PoseEstimationResult:
        """Refine to absolute pose using sensor fusion."""
        start_time = time.time()
        
        # If GPS position is available, use it directly with smoothing
        if gps_position is not None and np.all(np.abs(gps_position) > 1e-8):
            return self._fuse_with_gps(relative_pose, gps_position)
        
        # Use sensor fusion if enabled
        if sensor_data is not None:
            result = _sensor_fusion_absolute_pose(
                relative_pose=relative_pose,
                sensor_data=sensor_data,
                config=self.config
            )
        else:
            # Default to previous pose with smoothing
            result = self._apply_smoothing(relative_pose)
        
        processing_time_ms = (time.time() - start_time) * 1000
        
        return PoseEstimationResult(
            pose=result['pose'],
            confidence=min(1.0, result.get('confidence', 0.5)),
            is_absolute=True if sensor_data else False,
            processing_time_ms=processing_time_ms
        )
    
    def track_pose(
        self, 
        matches: np.ndarray,
        keypoints1: np.ndarray,
        keypoints2: np.ndarray,
        sensor_data: Optional[SensorData] = None,
        previous_pose: Optional[np.ndarray] = None
    ) -> PoseEstimationResult:
        """Full pose estimation pipeline with tracking."""
        # Estimate relative pose from matches
        relative_result = self.estimate_relative_pose(
            matches=matches,
            keypoints1=keypoints1,
            keypoints2=keypoints2
        )
        
        # Refine to absolute pose with sensor fusion
        absolute_result = self.estimate_absolute_pose(
            relative_pose=relative_result.pose,
            sensor_data=sensor_data,
        )
        
        return absolute_result
    
    def _fuse_with_gps(
        self, 
        relative_pose: np.ndarray, 
        gps_position: np.ndarray
    ) -> PoseEstimationResult:
        """Fuse GPS position with visual pose."""
        # Convert GPS to ECEF (simplified - use proper geodetic transformation in production)
        import pyproj
        
        try:
            # Create transformer for WGS84 to ECEF
            transformer = pyproj.Transformer(
                crs="EPSG:4326",  # WGS84
                always_xy=True,
                ellps='WGS84'
            )
            
            ecef_position = np.array(transformer.transform(gps_position[0], gps_position[1], gps_position[2]))
            
        except Exception as e:
            print(f"GPS to ECEF conversion failed: {e}")
            # Fallback to using GPS position directly
            ecef_position = gps_position
        
        # Combine visual and GPS positions with weighted average
        visual_position = relative_pose[:3]
        
        # Weighted fusion (configurable weights)
        fused_position = (
            self.config.gps_weight * ecef_position + 
            (1 - self.config.gps_weight) * visual_position
        )
        
        return PoseEstimationResult(
            pose=np.concatenate([fused_position, relative_pose[3:]]),
            confidence=self.config.gps_weight,  # Confidence based on GPS weight
            is_absolute=True,
            processing_time_ms=5.0
        )
    
    def _apply_smoothing(self, pose: np.ndarray) -> PoseEstimationResult:
        """Apply temporal smoothing to pose estimate."""
        if not self.config.pose_smoothing_enabled or self._previous_pose is None:
            return PoseEstimationResult(
                pose=pose,
                confidence=0.8,  # Lower confidence without smoothing
                processing_time_ms=1.0
            )
        
        # Moving average smoothing
        smoothed_pose = (
            self.config.smoothing_window * pose + 
            (self.config.smoothing_window - 1) * self._previous_pose
        ) / self.config.smoothing_window
        
        self._previous_pose = pose.copy()
        
        return PoseEstimationResult(
            pose=smoothed_pose,
            confidence=0.95,  # Higher confidence with smoothing
            processing_time_ms=2.0
        )


class MultiStreamPoseFuser(PoseEstimatorBase):
    """Multi-stream pose fusion for robust sub-meter accuracy.
    
    Combines poses from multiple streams using consensus voting and geometric constraints.
    Optimized for real-time reconstruction on central servers.
    """
    
    def __init__(self, config: Optional[PoseTrackerConfig] = None):
        super().__init__(config)
        
        self._stream_poses: Dict[str, PoseEstimationResult] = {}
        self._consensus_count: Dict[Tuple[int, int], int] = {}
    
    @property
    def estimator_type(self) -> str:
        return "multi_stream_fusion"
    
    def initialize(self) -> bool:
        """Initialize multi-stream pose fuser."""
        try:
            import torch
            
            # Use GPU acceleration if available
            if FeaturePose._is_gpu_available():
                from src.vision.gpu import get_gpu_backend
                
                backend = get_gpu_backend()
                
                if hasattr(backend, 'name') and backend.name == "cuda":
                    self._device = f"cuda:{self.config.gpu_device}"
                else:
                    self._device = "cpu"
                
                torch.set_default_device(self._device)
            
            self._initialized = True
            return True
            
        except Exception as e:
            print(f"Failed to initialize MultiStreamPoseFuser: {e}")
            return False
    
    def add_stream_pose(
        self, 
        stream_id: str, 
        pose_result: PoseEstimationResult
    ) -> bool:
        """Add a pose estimate from a new stream."""
        self._stream_poses[stream_id] = pose_result
        
        # Initialize consensus tracking for this stream pair
        if len(self._stream_poses) > 1:
            for other_id in list(self._stream_poses.keys()):
                if other_id != stream_id:
                    key = (min(stream_id, other_id), max(stream_id, other_id))
                    self._consensus_count[key] = 0
        
        return True
    
    def fuse_streams(
        self, 
        reference_stream: str,
        target_streams: List[str],
        timestamps: Optional[List[float]] = None
    ) -> PoseEstimationResult:
        """Fuse poses from multiple streams using consensus."""
        start_time = time.time()
        
        if reference_stream not in self._stream_poses:
            raise ValueError(f"Reference stream '{reference_stream}' not found")
        
        ref_pose = self._stream_poses[reference_stream]
        
        # Collect all poses for fusion
        all_poses = [ref_pose]
        all_confidences = [ref_pose.confidence]
        
        for target_id in target_streams:
            if target_id in self._stream_poses:
                pose = self._stream_poses[target_id]
                all_poses.append(pose)
                all_confidences.append(pose.confidence)
        
        # Apply fusion method
        fused_pose, consensus_strength = self._apply_fusion_method(
            all_poses, all_confidences
        )
        
        processing_time_ms = (time.time() - start_time) * 1000
        
        return PoseEstimationResult(
            pose=fused_pose,
            confidence=min(1.0, consensus_strength),
            is_absolute=True,
            processing_time_ms=processing_time_ms
        )
    
    def _apply_fusion_method(
        self, 
        poses: List[PoseEstimationResult],
        confidences: List[float]
    ) -> Tuple[np.ndarray, float]:
        """Apply fusion method to combine poses from multiple streams."""
        if len(poses) == 1:
            return poses[0].pose, poses[0].confidence
        
        # Use weighted average with confidence weights
        total_weight = sum(confidences)
        
        if total_weight < 1e-8:
            return poses[0].pose, 0.0
        
        fused_position = np.zeros(3)
        fused_rotation = np.zeros(6)
        total_confidence = 0.0
        
        for pose_result, confidence in zip(poses, confidences):
            weight = confidence / total_weight
            
            # Fuse position (simple weighted average)
            fused_position += weight * pose_result.pose[:3]
            
            # Fuse rotation (quaternion averaging would be more accurate)
            if len(pose_result.pose) > 3:
                fused_rotation += weight * pose_result.pose[3:]
            
            total_confidence += confidence
        
        return np.concatenate([fused_position, fused_rotation]), total_confidence


# Traditional pose estimation methods (fallback when PyTorch not available)
def _estimate_essential_pose(
    matches: np.ndarray, 
    keypoints1: np.ndarray, 
    keypoints2: np.ndarray,
    intrinsic_matrix: Optional[np.ndarray] = None,
    ransac_threshold: float = 3.0
) -> Dict[str, Any]:
    """Estimate essential matrix and relative pose using RANSAC.
    
    Args:
        matches: Match pairs [src_idx, tgt_idx]
        keypoints1: Keypoints in first image (N1, 2)
        keypoints2: Keypoints in second image (N2, 2)
        intrinsic_matrix: Camera intrinsics [3x3]
        ransac_threshold: RANSAC reprojection error threshold
        
    Returns:
        Dictionary with pose and confidence
    """
    import cv2
    
    # Use OpenCV's essential matrix estimation
    if len(matches) < 8:
        return {'pose': np.zeros(6), 'confidence': 0.0}
    
    try:
        # Estimate essential matrix with RANSAC
        F, mask = cv2.findFundamentalMat(
            keypoints1.astype(np.float32),
            keypoints2.astype(np.float32),
            method=cv2.FM_RANSAC,
            prob=0.999,
            ransacReprojThreshold=ransac_threshold
        )
        
        if mask is None or len(mask) == 0:
            return {'pose': np.zeros(6), 'confidence': 0.0}
        
        # Convert essential matrix to rotation and translation
        R, t, _ = cv2.recoverPose(F, keypoints1.astype(np.float32), 
                                  keypoints2.astype(np.float32), mask)
        
        if R is None or t is None:
            return {'pose': np.zeros(6), 'confidence': 0.0}
        
        # Convert to pose vector [x, y, z, roll, pitch, yaw]
        rotation_matrix = R.astype(np.float32)
        translation = t.astype(np.float32)
        
        # Extract Euler angles from rotation matrix
        euler_angles = _rotation_to_euler(rotation_matrix)
        
        pose = np.concatenate([translation, euler_angles])
        
        confidence = len(mask) / len(keypoints1)  # Inlier ratio
        
        return {'pose': pose, 'confidence': confidence}
        
    except Exception as e:
        print(f"Essential matrix estimation failed: {e}")
        return {'pose': np.zeros(6), 'confidence': 0.0}


def _rotation_to_euler(R: np.ndarray) -> np.ndarray:
    """Convert rotation matrix to Euler angles (roll, pitch, yaw)."""
    # Extract Euler angles from rotation matrix
    sy = np.sqrt(R[0, 0] * R[0, 0] + R[1, 0] * R[1, 0])
    
    singular = sy < 1e-6
    
    if not singular:
        x = np.atan2(R[2, 1], R[2, 2])
        y = np.atan2(-R[2, 0], sy)
        z = np.atan2(R[1, 0], R[0, 0])
    else:
        x = np.atan2(-R[1, 2], R[1, 1])
        y = np.atan2(-R[2, 0], sy)
        z = 0.0
    
    return np.array([x, y, z])


def _rotation_matrix_from_quaternion(
    w: float, x: float, y: float, z: float
) -> np.ndarray:
    """Convert quaternion to rotation matrix."""
    # Handle zero quaternion
    if abs(w) < 1e-8 and abs(x) < 1e-8 and abs(y) < 1e-8 and abs(z) < 1e-8:
        return np.eye(3)
    
    # Normalize quaternion
    norm = np.sqrt(w**2 + x**2 + y**2 + z**2)
    w, x, y, z = w / norm, x / norm, y / norm, z / norm
    
    R = np.array([
        [1 - 2 * (y**2 + z**2), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x**2 + z**2), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x**2 + y**2)]
    ])
    
    return R


def _sensor_fusion_absolute_pose(
    relative_pose: np.ndarray,
    sensor_data: SensorData,
    config: PoseTrackerConfig = None
) -> Dict[str, Any]:
    """Fuse GPS/IMU data with visual pose for absolute positioning.
    
    Args:
        relative_pose: Relative pose from feature matching
        sensor_data: GPS/IMU sensor data
        config: Configuration parameters
        
    Returns:
        Dictionary with fused pose and confidence
    """
    if config is None:
        config = PoseTrackerConfig()
    
    result = {'pose': relative_pose.copy(), 'confidence': 0.5}
    
    # Fuse GPS position if available
    if sensor_data.has_gps:
        gps_position = sensor_data.gps_position
        
        # Convert to ECEF (simplified - use proper geodetic transformation)
        try:
            import pyproj
            
            transformer = pyproj.Transformer(
                crs="EPSG:4326",
                always_xy=True,
                ellps='WGS84'
            )
            
            ecef_position = np.array(transformer.transform(gps_position[0], gps_position[1], gps_position[2]))
        except Exception as e:
            print(f"GPS conversion failed: {e}")
            ecef_position = gps_position
        
        # Weighted fusion with visual pose
        visual_position = relative_pose[:3]
        
        fused_position = (
            config.gps_weight * ecef_position + 
            (1 - config.gps_weight) * visual_position
        )
        
        result['pose'] = np.concatenate([fused_position, relative_pose[3:]])
        result['confidence'] = min(1.0, result['confidence'] + 0.2)
    
    # Fuse IMU data if available and enabled
    if sensor_data.has_imu and config.enable_imu_fusion:
        try:
            import quaternion
            
            if sensor_data.imu_quaternion is not None:
                imu_q = np.array(sensor_data.imu_quaternion)
                
                # Normalize quaternion
                norm = np.linalg.norm(imu_q)
                if norm > 1e-8:
                    imu_q = imu_q / norm
                    
                    # Convert to rotation matrix
                    R_imu = _rotation_matrix_from_quaternion(
                        imu_q[0], imu_q[1], imu_q[2], imu_q[3]
                    )
                    
                    # Extract Euler angles from IMU quaternion
                    euler_imu = _rotation_to_euler(R_imu)
                    
                    # Weighted fusion with visual rotation
                    visual_rotation = relative_pose[3:]
                    
                    fused_rotation = (
                        config.imu_weight * euler_imu + 
                        (1 - config.imu_weight) * visual_rotation
                    )
                    
                    result['pose'] = np.concatenate([result['pose'][:3], fused_rotation])
                    result['confidence'] = min(1.0, result['confidence'] + 0.1)
        except Exception as e:
            print(f"IMU fusion failed: {e}")
    
    return result


# Check for GPU availability (re-export from gpu module)
def _is_gpu_available():
    """Check if GPU is available."""
    try:
        from src.vision.gpu import is_gpu_available as gpu_is_available
        return gpu_is_available()
    except Exception:
        return False
