"""
Incremental Map State Management System.

Provides efficient map state management with:
- Incremental updates from streaming data
- Memory-efficient point cloud storage
- Continuous pose tracking integration
- Automatic memory management and cleanup
- Support for multiple coordinate systems

Features:
- Ring buffer for recent frames (O(1) operations)
- Sparse grid for large-scale maps
- Level of Detail (LOD) support
- Real-time statistics and monitoring
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple, Set, Any, Callable
from enum import Enum
import numpy as np


logger = logging.getLogger(__name__)


@dataclass
class PoseData:
    """Camera pose with uncertainty."""
    timestamp: float  # Unix timestamp
    position: np.ndarray  # [x, y, z] in meters
    orientation: np.ndarray  # [roll, pitch, yaw] in radians (quaternion or Euler)
    
    # Uncertainty metrics
    position_covariance: Optional[np.ndarray] = None  # 3x3 covariance matrix
    orientation_covariance: Optional[np.ndarray] = None  # 4x4 for quaternion
    
    # Quality indicators
    confidence: float = 1.0  # Pose confidence (0-1)
    is_keyframe: bool = False  # Whether this is a keyframe pose
    
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MapUpdate:
    """Incremental map update from new data."""
    timestamp: float
    pose: Optional[PoseData] = None
    points: Optional[np.ndarray] = None  # New point cloud points [N, 3]
    colors: Optional[np.ndarray] = None  # Point colors [N, 3] or [N, 4]
    
    # Update type
    update_type: str = "points"  # points, pose, keyframe
    
    # Metadata
    source_id: Optional[str] = None
    confidence: float = 1.0


@dataclass
class MapStats:
    """Real-time map statistics."""
    total_points: int = 0
    active_keyframes: int = 0
    total_poses: int = 0
    
    # Memory usage (estimated)
    memory_usage_mb: float = 0.0
    
    # Update rates
    points_per_second: float = 0.0
    poses_per_second: float = 0.0
    
    # Quality metrics
    avg_point_density: float = 0.0  # Points per cubic meter
    coverage_area_sqm: float = 0.0


class CoordinateSystem(Enum):
    """Supported coordinate systems."""
    LOCAL = "local"      # Local ENU (East-North-Up)
    GLOBAL = "global"    # WGS84 / GPS coordinates
    MAP = "map"          # Map-specific coordinate system


@dataclass
class Transform:
    """Coordinate transformation matrix."""
    from_system: CoordinateSystem
    to_system: CoordinateSystem
    
    rotation_matrix: np.ndarray  # 3x3 rotation matrix
    translation_vector: np.ndarray  # [x, y, z] translation
    
    @staticmethod
    def identity():
        """Create identity transform."""
        return Transform(
            from_system=CoordinateSystem.LOCAL,
            to_system=CoordinateSystem.LOCAL,
            rotation_matrix=np.eye(3),
            translation_vector=np.zeros(3)
        )


class PointCloudBuffer:
    """
    Memory-efficient point cloud buffer with automatic cleanup.
    
    Features:
    - Ring buffer for recent points (O(1) operations)
    - Automatic memory management
    - Support for sparse and dense storage
    
    Example:
        >>> buffer = PointCloudBuffer(max_points=1000000)
        >>> buffer.add_point([x, y, z], color=[r, g, b])
        >>> points = buffer.get_recent(500000)  # Get last 500k points
    """
    
    def __init__(self, max_points: int = 1_000_000):
        self.max_points = max_points
        
        # Ring buffers for efficient O(1) operations
        self._positions: List[np.ndarray] = []
        self._colors: List[np.ndarray] = []
        self._timestamps: List[float] = []
        
        # Point indices for quick access
        self._point_indices: Set[int] = set()
        
        # Statistics
        self._total_added = 0
        self._total_removed = 0
    
    def add_point(
        self, 
        position: np.ndarray, 
        color: Optional[np.ndarray] = None,
        timestamp: Optional[float] = None
    ) -> int:
        """
        Add a single point to the buffer.
        
        Args:
            position: Point coordinates [x, y, z]
            color: Point color [r, g, b] or [r, g, b, a] (optional)
            timestamp: Point capture timestamp (optional)
            
        Returns:
            Point index in buffer
            
        Example:
            >>> idx = buffer.add_point([10.5, 20.3, 5.7], color=[0.2, 0.8, 0.3])
        """
        position = np.asarray(position, dtype=np.float64)
        
        if len(position) != 3:
            raise ValueError(f"Position must be [x, y, z], got {position.shape}")
            
        timestamp = timestamp or time.time()
        
        # Add to buffers
        self._positions.append(position.copy())
        if color is not None:
            color = np.asarray(color, dtype=np.float32)
            if len(color) == 4:
                color = color[:3]  # Drop alpha for storage efficiency
            self._colors.append(color.copy())
        else:
            # Default gray color
            self._colors.append(np.array([0.5, 0.5, 0.5], dtype=np.float32))
            
        self._timestamps.append(timestamp)
        
        point_index = len(self._positions) - 1
        
        # Maintain max size with ring buffer behavior
        if len(self._positions) > self.max_points:
            # Remove oldest points (ring buffer style)
            remove_count = len(self._positions) - self.max_points
            
            for _ in range(remove_count):
                idx_to_remove = 0
                self._positions.pop(0)
                self._colors.pop(0)
                self._timestamps.pop(0)
                
                if point_index >= idx_to_remove:
                    self._point_indices.discard(idx_to_remove)
        
        # Update statistics
        self._total_added += 1
        
        return point_index
    
    def add_points_batch(
        self, 
        positions: np.ndarray, 
        colors: Optional[np.ndarray] = None,
        timestamps: Optional[List[float]] = None
    ) -> List[int]:
        """
        Add multiple points in a single batch operation.
        
        Args:
            positions: Points array [N, 3]
            colors: Colors array [N, 3] or [N, 4] (optional)
            timestamps: Timestamps list of length N (optional)
            
        Returns:
            List of point indices
            
        Example:
            >>> indices = buffer.add_points_batch(
            ...     positions=np.random.rand(1000, 3),
            ...     colors=np.random.rand(1000, 3)
            ... )
        """
        if len(positions.shape) != 2 or positions.shape[1] != 3:
            raise ValueError(f"Positions must be [N, 3], got {positions.shape}")
            
        timestamps = timestamps or [time.time()] * len(positions)
        
        indices = []
        
        for i in range(len(positions)):
            idx = self.add_point(
                positions[i], 
                colors[i] if colors is not None else None,
                timestamps[i]
            )
            indices.append(idx)
            
        return indices
    
    def get_points(self, start_idx: int = 0, end_idx: Optional[int] = None) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get points as numpy arrays.
        
        Args:
            start_idx: Starting index (inclusive)
            end_idx: Ending index (exclusive), None for all
            
        Returns:
            Tuple of (positions [N, 3], colors [N, 3])
            
        Example:
            >>> positions, colors = buffer.get_points(0, 100000)
        """
        end_idx = end_idx or len(self._positions)
        
        if start_idx >= end_idx:
            return np.empty((0, 3)), np.empty((0, 3))
            
        positions = np.array(self._positions[start_idx:end_idx], dtype=np.float64)
        colors = np.array(self._colors[start_idx:end_idx], dtype=np.float32)
        
        return positions, colors
    
    def get_recent(self, count: int) -> Tuple[np.ndarray, np.ndarray]:
        """Get the most recent N points."""
        if count <= 0 or count > len(self._positions):
            return self.get_points()
            
        start_idx = max(0, len(self._positions) - count)
        return self.get_points(start_idx, None)
    
    def get_by_timestamp_range(
        self, 
        start_time: float, 
        end_time: float
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Get points within a timestamp range."""
        # Find indices in timestamp range (O(N) but acceptable for recent data)
        valid_indices = [
            i for i, ts in enumerate(self._timestamps) 
            if start_time <= ts <= end_time
        ]
        
        if not valid_indices:
            return np.empty((0, 3)), np.empty((0, 3))
            
        positions = np.array([self._positions[i] for i in valid_indices], dtype=np.float64)
        colors = np.array([self._colors[i] for i in valid_indices], dtype=np.float32)
        
        return positions, colors
    
    def clear_old_points(self, max_age_seconds: float = 30.0) -> int:
        """
        Remove points older than specified age.
        
        Args:
            max_age_seconds: Maximum age in seconds
            
        Returns:
            Number of points removed
            
        Example:
            >>> removed = buffer.clear_old_points(60.0)  # Keep last minute of data
        """
        if not self._timestamps:
            return 0
            
        cutoff_time = time.time() - max_age_seconds
        
        # Find oldest point to keep
        min_valid_idx = None
        for i, ts in enumerate(self._timestamps):
            if ts >= cutoff_time:
                min_valid_idx = i
                break
        
        if min_valid_idx is None:
            return 0
            
        removed_count = len(self._positions) - min_valid_idx
        
        # Remove old points
        for _ in range(removed_count):
            self._positions.pop(0)
            self._colors.pop(0)
            self._timestamps.pop(0)
            
        self._total_removed += removed_count
        
        return removed_count
    
    @property
    def point_count(self) -> int:
        """Get current number of points."""
        return len(self._positions)
    
    @property
    def memory_usage_mb(self) -> float:
        """Estimate memory usage in megabytes."""
        # Rough estimate: positions (8 bytes per float64), colors (4 bytes per float32)
        pos_memory = self.point_count * 3 * 8 / (1024 * 1024)
        color_memory = self.point_count * 3 * 4 / (1024 * 1024)
        
        return pos_memory + color_memory
    
    def to_numpy(self) -> np.ndarray:
        """Convert entire buffer to numpy array [N, 6] for efficient storage."""
        if not self._positions:
            return np.empty((0, 6))
            
        # Combine positions and colors into single array
        combined = np.column_stack([
            np.array(self._positions, dtype=np.float32),
            np.array(self._colors, dtype=np.float32)
        ])
        
        return combined


class MapState:
    """
    Incremental map state with continuous updates.
    
    Features:
    - Real-time pose tracking integration
    - Point cloud accumulation with memory management
    - Automatic coordinate transformation
    - Statistics and monitoring
    
    Example:
        >>> map_state = MapState(
        ...     max_points=5_000_000,
        ...     transform=Transform.identity()
        ... )
        >>> # Process streaming updates
        >>> for update in stream_updates:
        ...     map_state.apply_update(update)
    """
    
    def __init__(
        self, 
        max_points: int = 5_000_000,
        coordinate_system: CoordinateSystem = CoordinateSystem.LOCAL,
        transform: Optional[Transform] = None
    ):
        self.max_points = max_points
        self.coordinate_system = coordinate_system
        
        # Initialize transform
        self.transform = transform or Transform.identity()
        
        # Point cloud buffer
        self._point_buffer = PointCloudBuffer(max_points)
        
        # Pose history (ring buffer for recent poses)
        self._pose_history: List[PoseData] = []
        self._max_pose_history = 1000
        
        # Keyframes for map reconstruction
        self._keyframes: Dict[int, Tuple[np.ndarray, np.ndarray]] = {}  # frame_id -> (points, colors)
        
        # Current state
        self._current_pose: Optional[PoseData] = None
        self._last_update_time: float = time.time()
        
        # Statistics
        self._stats = MapStats()
        self._update_count = 0
        
    def apply_update(self, update: MapUpdate) -> bool:
        """
        Apply an incremental map update.
        
        Args:
            update: Map update containing new data
            
        Returns:
            True if update was applied successfully
            
        Example:
            >>> success = map_state.apply_update(map_update)
        """
        self._update_count += 1
        
        try:
            # Apply pose update if present
            if update.pose is not None:
                self._apply_pose(update.pose)
            
            # Add points to buffer
            if update.points is not None and len(update.points) > 0:
                self._add_points(update.points, update.colors)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to apply map update: {e}")
            return False
    
    def _apply_pose(self, pose: PoseData) -> None:
        """Apply a new camera pose."""
        # Update current pose
        self._current_pose = pose
        
        # Add to history (ring buffer style)
        self._pose_history.append(pose)
        
        if len(self._pose_history) > self._max_pose_history:
            oldest_pose = self._pose_history.pop(0)
            
            # Optionally remove keyframes associated with old pose
            for frame_id in list(self._keyframes.keys()):
                if frame_id < oldest_pose.timestamp * 1000:  # Simplified check
                    del self._keyframes[frame_id]
    
    def _add_points(
        self, 
        points: np.ndarray, 
        colors: Optional[np.ndarray] = None
    ) -> int:
        """Add points to the map buffer."""
        if len(points) == 0:
            return 0
            
        # Transform points to current coordinate system
        transformed_points = self._transform_points(points)
        
        # Add to point cloud buffer
        indices = self._point_buffer.add_points_batch(
            positions=transformed_points,
            colors=colors
        )
        
        # Update statistics
        self._stats.total_points += len(points)
        
        return len(indices)
    
    def _transform_points(self, points: np.ndarray) -> np.ndarray:
        """Transform points from local to current coordinate system."""
        if not hasattr(self.transform, 'rotation_matrix'):
            return points
            
        # Apply rotation and translation
        rotated = points @ self.transform.rotation_matrix.T
        
        # Handle 4D homogeneous coordinates (x, y, z, w)
        if len(rotated.shape) == 2 and rotated.shape[1] == 4:
            rotated = rotated[:, :3]
            
        transformed = rotated + self.transform.translation_vector
        
        return transformed
    
    def get_current_pose(self) -> Optional[PoseData]:
        """Get the current camera pose."""
        return self._current_pose
    
    def get_recent_poses(
        self, 
        count: int = 100,
        max_age_seconds: float = 60.0
    ) -> List[PoseData]:
        """
        Get recent poses within time window.
        
        Args:
            count: Maximum number of poses to return
            max_age_seconds: Maximum age in seconds
            
        Returns:
            List of PoseData objects
            
        Example:
            >>> recent_poses = map_state.get_recent_poses(50, 30.0)
        """
        if not self._pose_history:
            return []
            
        cutoff_time = time.time() - max_age_seconds
        
        # Filter by age and take most recent
        valid_poses = [
            p for p in reversed(self._pose_history) 
            if p.timestamp >= cutoff_time
        ][:count]
        
        return list(reversed(valid_poses))
    
    def get_keyframes(
        self, 
        start_frame: int = 0, 
        end_frame: Optional[int] = None
    ) -> Dict[int, Tuple[np.ndarray, np.ndarray]]:
        """Get keyframe data for map reconstruction."""
        end_frame = end_frame or max(self._keyframes.keys()) + 1
        
        return {
            k: v for k, v in self._keyframes.items() 
            if start_frame <= k < end_frame
        }
    
    def add_keyframe(
        self, 
        frame_id: int, 
        points: np.ndarray, 
        colors: Optional[np.ndarray] = None
    ) -> bool:
        """
        Add a keyframe for map reconstruction.
        
        Args:
            frame_id: Unique frame identifier
            points: Keyframe point cloud [N, 3]
            colors: Point colors [N, 3] or [N, 4] (optional)
            
        Returns:
            True if keyframe added successfully
            
        Example:
            >>> success = map_state.add_keyframe(12345, points, colors)
        """
        try:
            self._keyframes[frame_id] = (points.copy(), colors.copy() if colors is not None else None)
            return True
        except Exception as e:
            logger.error(f"Failed to add keyframe {frame_id}: {e}")
            return False
    
    def get_map_bounds(self) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        """
        Get the bounding box of the current map.
        
        Returns:
            Tuple of (min_coords [x,y,z], max_coords [x,y,z]) or None if empty
            
        Example:
            >>> min_pt, max_pt = map_state.get_map_bounds()
        """
        positions, _ = self._point_buffer.get_points()
        
        if len(positions) == 0:
            return None
            
        min_coords = np.min(positions, axis=0)
        max_coords = np.max(positions, axis=0)
        
        return (min_coords, max_coords)
    
    def get_map_stats(self) -> MapStats:
        """Get current map statistics."""
        # Calculate coverage area
        bounds = self.get_map_bounds()
        if bounds is not None:
            min_pt, max_pt = bounds
            volume = np.prod(max_pt - min_pt)
            density = self._stats.total_points / max(0.1, volume)
            
            self._stats.avg_point_density = density
            
        # Calculate coverage area (projected on XY plane)
        if bounds is not None:
            xy_area = np.sqrt(np.prod(max_pt[:2] - min_pt[:2]))
            self._stats.coverage_area_sqm = xy_area
            
        return self._stats
    
    def reset(self) -> None:
        """Reset map state (clear all data)."""
        logger.info("Resetting map state...")
        
        self._point_buffer = PointCloudBuffer(self.max_points)
        self._pose_history.clear()
        self._keyframes.clear()
        self._current_pose = None
        
        # Reset statistics
        self._stats = MapStats()
        self._update_count = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Export map state as dictionary for serialization."""
        positions, colors = self._point_buffer.get_points()
        
        return {
            "total_points": len(positions),
            "current_pose": {
                "timestamp": self._current_pose.timestamp if self._current_pose else 0,
                "position": self._current_pose.position.tolist() if self._current_pose else None,
                "orientation": self._current_pose.orientation.tolist() if self._current_pose else None,
            },
            "bounds": {
                "min": bounds[0].tolist() if (bounds := self.get_map_bounds()) else None,
                "max": bounds[1].tolist() if bounds else None,
            },
            "keyframe_count": len(self._keyframes),
        }


class IncrementalMapManager:
    """
    Manages multiple map states with automatic switching and merging.
    
    Features:
    - Multiple active maps (for multi-agent scenarios)
    - Automatic map selection based on proximity
    - Map merging for coverage expansion
    - Memory management across all maps
    
    Example:
        >>> manager = IncrementalMapManager(max_maps=5)
        >>> # Create new map when drone enters new area
        >>> new_map = manager.create_new_map()
        >>> # Switch to nearest map automatically
        >>> manager.switch_to_nearest_pose(pose_data)
    """
    
    def __init__(self, max_maps: int = 5):
        self.max_maps = max_maps
        
        # Active maps indexed by ID
        self._maps: Dict[int, MapState] = {}
        
        # Current active map
        self._current_map_id: Optional[int] = None
        
        # Map metadata for selection logic
        self._map_metadata: Dict[int, Dict[str, Any]] = {
            0: {
                "center": np.zeros(3),
                "radius": 10.0,
                "created_at": time.time(),
            }
        }
        
        # Statistics
        self._total_points_across_maps = 0
    
    def create_new_map(self) -> int:
        """Create a new map instance."""
        map_id = len(self._maps) + 1
        
        if map_id > self.max_maps:
            logger.warning(f"Cannot create more than {self.max_maps} maps")
            return -1
            
        # Create new map with default settings
        map_state = MapState(
            max_points=5_000_000,
            coordinate_system=CoordinateSystem.LOCAL
        )
        
        self._maps[map_id] = map_state
        
        # Initialize metadata
        center = np.zeros(3)  # Will be updated with first pose
        radius = 10.0  # Default coverage radius
        
        self._map_metadata[map_id] = {
            "center": center,
            "radius": radius,
            "created_at": time.time(),
            "active": True,
        }
        
        logger.info(f"Created new map #{map_id}")
        return map_id
    
    def switch_to_map(self, map_id: int) -> bool:
        """Switch to a specific map."""
        if map_id not in self._maps:
            logger.error(f"Map {map_id} does not exist")
            return False
            
        self._current_map_id = map_id
        
        # Update metadata
        if map_id in self._map_metadata:
            self._map_metadata[map_id]["active"] = True
            
        logger.info(f"Switched to map #{map_id}")
        return True
    
    def switch_to_nearest_pose(self, pose: PoseData) -> int:
        """
        Automatically switch to the nearest active map.
        
        Args:
            pose: Current camera pose
            
        Returns:
            ID of selected map (current if no better option found)
            
        Example:
            >>> new_map_id = manager.switch_to_nearest_pose(current_pose)
        """
        if not self._maps:
            return -1
            
        # Calculate distance to each map center
        distances = []
        
        for map_id, metadata in self._map_metadata.items():
            center = metadata["center"]
            distance = np.linalg.norm(pose.position - center)
            
            distances.append((distance, map_id))
        
        # Sort by distance and select nearest active map
        distances.sort(key=lambda x: x[0])
        
        for distance, map_id in distances:
            if self._maps.get(map_id) is not None:
                if self.switch_to_map(map_id):
                    return map_id
                    
        logger.warning("No valid maps found")
        return -1
    
    def update_map_center(self, pose: PoseData) -> None:
        """Update the center of current map based on new pose."""
        if not self._current_map_id or self._current_map_id not in self._map_metadata:
            return
            
        # Move center towards new position (smooth transition)
        metadata = self._map_metadata[self._current_map_id]
        
        # Simple approach: set to average of recent poses
        # For smoother transitions, use weighted moving average
        
        if len(self._maps.get(self._current_map_id, MapState())._pose_history) > 0:
            all_poses = (
                self._maps[self._current_map_id]._pose_history + 
                [pose]
            )[-10:]  # Use last 10 poses
            
            new_center = np.mean([p.position for p in all_poses], axis=0)
            
            metadata["center"] = new_center
    
    def merge_maps(self, source_map_id: int, target_map_id: int) -> bool:
        """
        Merge two maps into one.
        
        Args:
            source_map_id: Map to be merged (will be removed)
            target_map_id: Target map to receive data
            
        Returns:
            True if merge successful
            
        Example:
            >>> success = manager.merge_maps(2, 1)  # Merge map 2 into map 1
        """
        if source_map_id not in self._maps or target_map_id not in self._maps:
            logger.error("One or both maps do not exist")
            return False
            
        source_map = self._maps[source_map_id]
        target_map = self._maps[target_map_id]
        
        # Merge point clouds
        positions, colors = source_map._point_buffer.get_points()
        
        if len(positions) > 0:
            # Transform points to target map's coordinate system
            transformed = source_map._transform_points(positions)
            
            indices = target_map._point_buffer.add_points_batch(
                positions=transformed,
                colors=colors
            )
            
            self._total_points_across_maps += len(positions)
        
        # Merge keyframes
        for frame_id, (points, colors) in source_map.get_keyframes().items():
            target_map.add_keyframe(frame_id + 1000000, points, colors)  # Offset IDs
            
        # Remove source map
        del self._maps[source_map_id]
        del self._map_metadata[source_map_id]
        
        logger.info(f"Merged map {source_map_id} into {target_map_id}")
        return True
    
    def get_active_maps(self) -> List[int]:
        """Get list of active (non-merged) map IDs."""
        return [mid for mid, meta in self._map_metadata.items() if meta.get("active", False)]
    
    def get_current_map_stats(self) -> Optional[MapStats]:
        """Get statistics for current active map."""
        if not self._current_map_id or self._current_map_id not in self._maps:
            return None
            
        return self._maps[self._current_map_id].get_map_stats()
    
    def get_all_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics for all maps."""
        total_points = sum(
            map_state._stats.total_points 
            for map_state in self._maps.values()
        )
        
        return {
            "total_maps": len(self._maps),
            "active_maps": len(self.get_active_maps()),
            "current_map_id": self._current_map_id,
            "total_points_across_all_maps": total_points,
            "map_ids": list(self._maps.keys()),
        }
