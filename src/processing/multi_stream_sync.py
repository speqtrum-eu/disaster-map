"""
Multi-stream synchronization for orthomosaic generation

This module provides advanced synchronization capabilities for:
- Temporal alignment of frames from multiple streams
- Geospatial alignment based on GPS data
- Feature-based alignment using image matching
- Hybrid synchronization combining multiple methods
"""

import time
import threading
import numpy as np
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque

from ..core.models import Frame, GPSData, ProcessingConfig, StreamConfig
from ..core.utils import get_logger, timestamp_now, ensure_directory
from .feature_matcher import FeatureMatcher, SIFTMatcher

logger = get_logger("processing.multi_stream_sync")


class SyncMethod(Enum):
    """Synchronization methods"""
    TIMESTAMP = "timestamp"  # Synchronize by timestamp
    GPS = "gps"  # Synchronize by GPS position
    FEATURE = "feature"  # Synchronize by feature matching
    HYBRID = "hybrid"  # Combine multiple methods


class SyncQuality(Enum):
    """Synchronization quality"""
    POOR = "poor"
    FAIR = "fair"
    GOOD = "good"
    EXCELLENT = "excellent"


@dataclass
class SyncConfig:
    """Configuration for multi-stream synchronization"""
    # Method
    method: SyncMethod = SyncMethod.HYBRID
    
    # Timestamp synchronization
    max_timestamp_diff: float = 0.5  # seconds
    timestamp_priority: List[str] = field(default_factory=lambda: ["primary", "secondary"])
    
    # GPS synchronization
    max_gps_distance: float = 10.0  # meters
    gps_accuracy_threshold: float = 5.0  # meters
    
    # Feature synchronization
    feature_matcher_type: str = "sift"
    min_feature_matches: int = 50
    feature_match_threshold: float = 0.7
    
    # Hybrid synchronization
    use_timestamp: bool = True
    use_gps: bool = True
    use_feature: bool = True
    
    # Buffer sizes
    frame_buffer_size: int = 100
    sync_window_size: int = 10  # Number of frames to consider for sync
    
    # Timeout
    sync_timeout: float = 5.0  # seconds
    
    @classmethod
    def from_processing_config(cls, config: ProcessingConfig) -> "SyncConfig":
        """Create from ProcessingConfig"""
        return cls()


@dataclass
class SyncResult:
    """Result of synchronization"""
    stream_id: str
    frame: Frame
    sync_time: float
    quality: SyncQuality = SyncQuality.FAIR
    confidence: float = 0.0
    matches: Optional[np.ndarray] = None
    offset: float = 0.0  # Time offset applied
    error: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "stream_id": self.stream_id,
            "sync_time": self.sync_time,
            "quality": self.quality.value,
            "confidence": self.confidence,
            "offset": self.offset,
            "error": self.error,
        }


@dataclass
class SyncGroup:
    """Group of synchronized frames from multiple streams"""
    group_id: str
    timestamp: float
    frames: Dict[str, Frame]  # stream_id -> Frame
    quality: SyncQuality = SyncQuality.FAIR
    confidence: float = 0.0
    gps_center: Optional[Tuple[float, float]] = None  # (lat, lon)
    bounds: Optional[Tuple[float, float, float, float]] = None  # (min_x, min_y, max_x, max_y)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "group_id": self.group_id,
            "timestamp": self.timestamp,
            "stream_count": len(self.frames),
            "quality": self.quality.value,
            "confidence": self.confidence,
            "gps_center": list(self.gps_center) if self.gps_center else None,
            "bounds": list(self.bounds) if self.bounds else None,
        }


class FrameBuffer:
    """
    Buffer for storing frames from multiple streams
    
    This buffer:
    1. Stores frames from each stream
    2. Allows retrieval by timestamp or index
    3. Manages frame lifetime
    """
    
    def __init__(self, max_size: int = 100, ttl: float = 30.0):
        self._max_size = max_size
        self._ttl = ttl  # Time-to-live in seconds
        self._buffers: Dict[str, deque] = defaultdict(deque)
        self._timestamps: Dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()
    
    def add_frame(self, stream_id: str, frame: Frame) -> bool:
        """Add a frame to the buffer"""
        with self._lock:
            # Remove old frames
            self._cleanup_buffer(stream_id)
            
            # Add new frame
            self._buffers[stream_id].append(frame)
            self._timestamps[stream_id].append(timestamp_now())
            
            # Check size limit
            while len(self._buffers[stream_id]) > self._max_size:
                self._buffers[stream_id].popleft()
                self._timestamps[stream_id].popleft()
            
            return True
    
    def get_frame(self, stream_id: str, index: int = -1) -> Optional[Frame]:
        """Get a frame from the buffer"""
        with self._lock:
            if stream_id not in self._buffers:
                return None
            
            buffer = self._buffers[stream_id]
            if index < 0:
                index = len(buffer) + index
            
            if 0 <= index < len(buffer):
                return buffer[index]
            return None
    
    def get_frames_in_range(
        self,
        stream_id: str,
        start_time: float,
        end_time: float,
    ) -> List[Frame]:
        """Get frames within a time range"""
        with self._lock:
            if stream_id not in self._buffers:
                return []
            
            frames = []
            buffer = self._buffers[stream_id]
            timestamps = self._timestamps[stream_id]
            
            for frame, ts in zip(buffer, timestamps):
                if start_time <= ts <= end_time:
                    frames.append(frame)
            
            return frames
    
    def get_latest_frame(self, stream_id: str) -> Optional[Frame]:
        """Get the latest frame from a stream"""
        return self.get_frame(stream_id, -1)
    
    def get_all_latest(self) -> Dict[str, Optional[Frame]]:
        """Get latest frames from all streams"""
        with self._lock:
            result = {}
            for stream_id in self._buffers:
                result[stream_id] = self.get_latest_frame(stream_id)
            return result
    
    def _cleanup_buffer(self, stream_id: str) -> None:
        """Remove old frames from buffer"""
        current_time = timestamp_now()
        
        while (self._timestamps[stream_id] and 
               current_time - self._timestamps[stream_id][0] > self._ttl):
            self._buffers[stream_id].popleft()
            self._timestamps[stream_id].popleft()
    
    def clear(self, stream_id: Optional[str] = None) -> None:
        """Clear the buffer"""
        with self._lock:
            if stream_id:
                self._buffers[stream_id].clear()
                self._timestamps[stream_id].clear()
            else:
                self._buffers.clear()
                self._timestamps.clear()
    
    def get_stream_ids(self) -> List[str]:
        """Get all stream IDs"""
        with self._lock:
            return list(self._buffers.keys())


class TimestampSynchronizer:
    """
    Synchronizes frames based on timestamps
    """
    
    def __init__(self, config: Optional[SyncConfig] = None):
        self.config = config or SyncConfig()
        self._buffer = FrameBuffer(
            max_size=self.config.frame_buffer_size,
            ttl=self.config.sync_timeout * 2
        )
    
    def add_frame(self, stream_id: str, frame: Frame) -> bool:
        """Add a frame for synchronization"""
        return self._buffer.add_frame(stream_id, frame)
    
    def find_sync_groups(self) -> List[SyncGroup]:
        """Find groups of synchronized frames"""
        groups = []
        
        # Get all stream IDs
        stream_ids = self._buffer.get_stream_ids()
        if len(stream_ids) < 2:
            return groups
        
        # Find matching frames across streams
        for stream_id in stream_ids:
            latest_frame = self._buffer.get_latest_frame(stream_id)
            if latest_frame is None:
                continue
            
            # Find frames from other streams within timestamp range
            group_frames = {stream_id: latest_frame}
            group_time = latest_frame.timestamp
            
            for other_id in stream_ids:
                if other_id == stream_id:
                    continue
                
                # Get frames within range
                frames = self._buffer.get_frames_in_range(
                    other_id,
                    group_time - self.config.max_timestamp_diff,
                    group_time + self.config.max_timestamp_diff,
                )
                
                if frames:
                    # Use the closest frame
                    closest_frame = min(
                        frames,
                        key=lambda f: abs(f.timestamp - group_time)
                    )
                    group_frames[other_id] = closest_frame
            
            # Create group if we have frames from multiple streams
            if len(group_frames) > 1:
                group = SyncGroup(
                    group_id=f"sync_{timestamp_now()}_{len(groups)}",
                    timestamp=group_time,
                    frames=group_frames,
                    quality=self._calculate_quality(group_frames),
                    confidence=self._calculate_confidence(group_frames),
                )
                groups.append(group)
        
        return groups
    
    def _calculate_quality(self, frames: Dict[str, Frame]) -> SyncQuality:
        """Calculate synchronization quality"""
        timestamps = [f.timestamp for f in frames.values()]
        time_range = max(timestamps) - min(timestamps)
        
        if time_range < self.config.max_timestamp_diff / 4:
            return SyncQuality.EXCELLENT
        elif time_range < self.config.max_timestamp_diff / 2:
            return SyncQuality.GOOD
        elif time_range < self.config.max_timestamp_diff:
            return SyncQuality.FAIR
        else:
            return SyncQuality.POOR
    
    def _calculate_confidence(self, frames: Dict[str, Frame]) -> float:
        """Calculate synchronization confidence (0-1)"""
        timestamps = [f.timestamp for f in frames.values()]
        time_range = max(timestamps) - min(timestamps)
        
        # Normalize by max allowed difference
        normalized = time_range / self.config.max_timestamp_diff
        return max(0, 1 - normalized)


class GPSSynchronizer:
    """
    Synchronizes frames based on GPS positions
    """
    
    def __init__(self, config: Optional[SyncConfig] = None):
        self.config = config or SyncConfig()
        self._buffer = FrameBuffer(
            max_size=self.config.frame_buffer_size,
            ttl=self.config.sync_timeout * 2
        )
    
    def add_frame(self, stream_id: str, frame: Frame) -> bool:
        """Add a frame for synchronization"""
        # Only add frames with GPS data
        if frame.gps is None:
            return False
        
        return self._buffer.add_frame(stream_id, frame)
    
    def find_sync_groups(self) -> List[SyncGroup]:
        """Find groups of synchronized frames based on GPS proximity"""
        groups = []
        
        # Get all stream IDs
        stream_ids = self._buffer.get_stream_ids()
        if len(stream_ids) < 2:
            return groups
        
        # Get all frames with GPS
        all_frames = []
        for stream_id in stream_ids:
            latest_frame = self._buffer.get_latest_frame(stream_id)
            if latest_frame and latest_frame.gps:
                all_frames.append((stream_id, latest_frame))
        
        # Cluster frames by GPS proximity
        clusters = self._cluster_by_gps(all_frames)
        
        # Create sync groups from clusters
        for cluster in clusters:
            if len(cluster) > 1:
                # Calculate center GPS
                lats = [f[1].gps.latitude for f in cluster]
                lons = [f[1].gps.longitude for f in cluster]
                center_lat = np.mean(lats)
                center_lon = np.mean(lons)
                
                # Use average timestamp
                timestamps = [f[1].timestamp for f in cluster]
                avg_timestamp = np.mean(timestamps)
                
                group_frames = {f[0]: f[1] for f in cluster}
                
                group = SyncGroup(
                    group_id=f"gps_sync_{timestamp_now()}_{len(groups)}",
                    timestamp=avg_timestamp,
                    frames=group_frames,
                    gps_center=(center_lat, center_lon),
                    quality=self._calculate_quality(cluster),
                    confidence=self._calculate_confidence(cluster),
                )
                groups.append(group)
        
        return groups
    
    def _cluster_by_gps(
        self,
        frames: List[Tuple[str, Frame]],
    ) -> List[List[Tuple[str, Frame]]]:
        """Cluster frames by GPS proximity"""
        clusters = []
        used = set()
        
        for i, (stream_id1, frame1) in enumerate(frames):
            if i in used:
                continue
            
            # Start new cluster
            cluster = [(stream_id1, frame1)]
            used.add(i)
            
            # Find nearby frames
            for j, (stream_id2, frame2) in enumerate(frames):
                if j in used or j == i:
                    continue
                
                # Calculate distance
                dist = self._gps_distance(frame1.gps, frame2.gps)
                
                if dist <= self.config.max_gps_distance:
                    cluster.append((stream_id2, frame2))
                    used.add(j)
            
            clusters.append(cluster)
        
        return clusters
    
    def _gps_distance(self, gps1: GPSData, gps2: GPSData) -> float:
        """Calculate distance between two GPS points in meters"""
        # Simple haversine formula
        lat1, lon1 = np.radians(gps1.latitude), np.radians(gps1.longitude)
        lat2, lon2 = np.radians(gps2.latitude), np.radians(gps2.longitude)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = np.sin(dlat / 2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2)**2
        c = 2 * np.arcsin(np.sqrt(a))
        
        # Earth radius in meters
        radius = 6371000
        distance = radius * c
        
        return float(distance)
    
    def _calculate_quality(self, cluster: List[Tuple[str, Frame]]) -> SyncQuality:
        """Calculate synchronization quality based on GPS clustering"""
        # Calculate average distance between frames
        distances = []
        for i in range(len(cluster)):
            for j in range(i + 1, len(cluster)):
                dist = self._gps_distance(cluster[i][1].gps, cluster[j][1].gps)
                distances.append(dist)
        
        if not distances:
            return SyncQuality.POOR
        
        avg_distance = np.mean(distances)
        
        if avg_distance < self.config.max_gps_distance / 4:
            return SyncQuality.EXCELLENT
        elif avg_distance < self.config.max_gps_distance / 2:
            return SyncQuality.GOOD
        elif avg_distance < self.config.max_gps_distance:
            return SyncQuality.FAIR
        else:
            return SyncQuality.POOR
    
    def _calculate_confidence(self, cluster: List[Tuple[str, Frame]]) -> float:
        """Calculate synchronization confidence (0-1)"""
        distances = []
        for i in range(len(cluster)):
            for j in range(i + 1, len(cluster)):
                dist = self._gps_distance(cluster[i][1].gps, cluster[j][1].gps)
                distances.append(dist)
        
        if not distances:
            return 0.0
        
        avg_distance = np.mean(distances)
        normalized = avg_distance / self.config.max_gps_distance
        return max(0, 1 - normalized)


class FeatureSynchronizer:
    """
    Synchronizes frames based on feature matching
    """
    
    def __init__(self, config: Optional[SyncConfig] = None):
        self.config = config or SyncConfig()
        self._buffer = FrameBuffer(
            max_size=self.config.frame_buffer_size,
            ttl=self.config.sync_timeout * 2
        )
        
        # Initialize feature matcher
        self._feature_matcher = self._create_feature_matcher()
    
    def _create_feature_matcher(self) -> FeatureMatcher:
        """Create feature matcher based on config"""
        if self.config.feature_matcher_type == "sift":
            return SIFTMatcher()
        else:
            return SIFTMatcher()  # Default to SIFT
    
    def add_frame(self, stream_id: str, frame: Frame) -> bool:
        """Add a frame for synchronization"""
        return self._buffer.add_frame(stream_id, frame)
    
    def find_sync_groups(self) -> List[SyncGroup]:
        """Find groups of synchronized frames based on feature matching"""
        groups = []
        
        # Get all stream IDs
        stream_ids = self._buffer.get_stream_ids()
        if len(stream_ids) < 2:
            return groups
        
        # Get latest frames from each stream
        latest_frames = self._buffer.get_all_latest()
        
        # Find matching frames
        for stream_id1, frame1 in latest_frames.items():
            if frame1 is None:
                continue
            
            group_frames = {stream_id1: frame1}
            
            for stream_id2, frame2 in latest_frames.items():
                if stream_id2 == stream_id1 or frame2 is None:
                    continue
                
                # Check if frames match
                match_result = self._feature_matcher.match(
                    frame1.data,
                    frame2.data,
                )
                
                if (match_result is not None and 
                    match_result.match_count >= self.config.min_feature_matches):
                    group_frames[stream_id2] = frame2
            
            # Create group if we have matches
            if len(group_frames) > 1:
                group = SyncGroup(
                    group_id=f"feature_sync_{timestamp_now()}_{len(groups)}",
                    timestamp=frame1.timestamp,
                    frames=group_frames,
                    quality=self._calculate_quality(group_frames),
                    confidence=self._calculate_confidence(group_frames),
                )
                groups.append(group)
        
        return groups
    
    def _calculate_quality(self, frames: Dict[str, Frame]) -> SyncQuality:
        """Calculate synchronization quality based on feature matching"""
        # Count total matches
        total_matches = 0
        pair_count = 0
        
        stream_ids = list(frames.keys())
        for i in range(len(stream_ids)):
            for j in range(i + 1, len(stream_ids)):
                frame1 = frames[stream_ids[i]]
                frame2 = frames[stream_ids[j]]
                
                match_result = self._feature_matcher.match(
                    frame1.data,
                    frame2.data,
                )
                
                if match_result:
                    total_matches += match_result.match_count
                    pair_count += 1
        
        if pair_count == 0:
            return SyncQuality.POOR
        
        avg_matches = total_matches / pair_count
        
        if avg_matches >= self.config.min_feature_matches * 2:
            return SyncQuality.EXCELLENT
        elif avg_matches >= self.config.min_feature_matches * 1.5:
            return SyncQuality.GOOD
        elif avg_matches >= self.config.min_feature_matches:
            return SyncQuality.FAIR
        else:
            return SyncQuality.POOR
    
    def _calculate_confidence(self, frames: Dict[str, Frame]) -> float:
        """Calculate synchronization confidence (0-1)"""
        total_matches = 0
        pair_count = 0
        
        stream_ids = list(frames.keys())
        for i in range(len(stream_ids)):
            for j in range(i + 1, len(stream_ids)):
                frame1 = frames[stream_ids[i]]
                frame2 = frames[stream_ids[j]]
                
                match_result = self._feature_matcher.match(
                    frame1.data,
                    frame2.data,
                )
                
                if match_result:
                    total_matches += match_result.match_count
                    pair_count += 1
        
        if pair_count == 0:
            return 0.0
        
        avg_matches = total_matches / pair_count
        normalized = avg_matches / self.config.min_feature_matches
        return min(1.0, normalized)


class HybridSynchronizer:
    """
    Hybrid synchronizer combining multiple methods
    """
    
    def __init__(self, config: Optional[SyncConfig] = None):
        self.config = config or SyncConfig()
        
        # Create individual synchronizers
        self._timestamp_sync = TimestampSynchronizer(self.config)
        self._gps_sync = GPSSynchronizer(self.config)
        self._feature_sync = FeatureSynchronizer(self.config)
        
        # Buffer for all methods
        self._buffer = FrameBuffer(
            max_size=self.config.frame_buffer_size,
            ttl=self.config.sync_timeout * 2
        )
    
    def add_frame(self, stream_id: str, frame: Frame) -> bool:
        """Add a frame for synchronization"""
        # Add to main buffer
        success = self._buffer.add_frame(stream_id, frame)
        
        # Add to individual synchronizers
        if self.config.use_timestamp:
            self._timestamp_sync.add_frame(stream_id, frame)
        if self.config.use_gps and frame.gps:
            self._gps_sync.add_frame(stream_id, frame)
        if self.config.use_feature:
            self._feature_sync.add_frame(stream_id, frame)
        
        return success
    
    def find_sync_groups(self) -> List[SyncGroup]:
        """Find groups of synchronized frames using hybrid approach"""
        # Get groups from each method
        timestamp_groups = self._timestamp_sync.find_sync_groups() if self.config.use_timestamp else []
        gps_groups = self._gps_sync.find_sync_groups() if self.config.use_gps else []
        feature_groups = self._feature_sync.find_sync_groups() if self.config.use_feature else []
        
        # Combine groups
        all_groups = timestamp_groups + gps_groups + feature_groups
        
        if not all_groups:
            return []
        
        # Merge overlapping groups
        merged_groups = self._merge_groups(all_groups)
        
        # Sort by quality and confidence
        merged_groups.sort(
            key=lambda g: (g.quality.value, g.confidence),
            reverse=True
        )
        
        return merged_groups
    
    def _merge_groups(self, groups: List[SyncGroup]) -> List[SyncGroup]:
        """Merge overlapping sync groups"""
        merged = []
        used = set()
        
        for i, group1 in enumerate(groups):
            if i in used:
                continue
            
            # Start with this group
            merged_group = group1
            used.add(i)
            
            # Find overlapping groups
            for j, group2 in enumerate(groups):
                if j in used:
                    continue
                
                # Check if groups overlap (share at least one frame)
                if self._groups_overlap(merged_group, group2):
                    # Merge groups
                    merged_group = self._merge_two_groups(merged_group, group2)
                    used.add(j)
            
            merged.append(merged_group)
        
        return merged
    
    def _groups_overlap(self, group1: SyncGroup, group2: SyncGroup) -> bool:
        """Check if two groups share any frames"""
        stream_ids1 = set(group1.frames.keys())
        stream_ids2 = set(group2.frames.keys())
        
        # Check if they share at least one stream
        return len(stream_ids1 & stream_ids2) > 0
    
    def _merge_two_groups(self, group1: SyncGroup, group2: SyncGroup) -> SyncGroup:
        """Merge two sync groups"""
        # Combine frames
        merged_frames = dict(group1.frames)
        merged_frames.update(group2.frames)
        
        # Use average timestamp
        all_timestamps = [f.timestamp for f in merged_frames.values()]
        avg_timestamp = np.mean(all_timestamps)
        
        # Calculate combined quality and confidence
        quality_values = [g.quality.value for g in [group1, group2]]
        avg_quality = SyncQuality(np.mean(quality_values))
        
        # Weighted confidence
        total_confidence = group1.confidence + group2.confidence
        avg_confidence = total_confidence / 2
        
        # Calculate bounds
        bounds = self._calculate_bounds(merged_frames)
        
        return SyncGroup(
            group_id=f"merged_{group1.group_id}_{group2.group_id}",
            timestamp=avg_timestamp,
            frames=merged_frames,
            quality=avg_quality,
            confidence=avg_confidence,
            bounds=bounds,
        )
    
    def _calculate_bounds(self, frames: Dict[str, Frame]) -> Optional[Tuple[float, float, float, float]]:
        """Calculate bounding box for a set of frames"""
        min_x, min_y = float('inf'), float('inf')
        max_x, max_y = float('-inf'), float('-inf')
        
        for frame in frames.values():
            if frame.gps:
                min_x = min(min_x, frame.gps.longitude)
                min_y = min(min_y, frame.gps.latitude)
                max_x = max(max_x, frame.gps.longitude)
                max_y = max(max_y, frame.gps.latitude)
        
        if min_x == float('inf'):
            return None
        
        return (min_x, min_y, max_x, max_y)


class StreamSynchronizer:
    """
    Main stream synchronizer class
    
    This class:
    1. Manages synchronization of multiple streams
    2. Provides callbacks for synchronized frames
    3. Handles stream registration and removal
    """
    
    def __init__(self, config: Optional[SyncConfig] = None):
        self.config = config or SyncConfig()
        self._synchronizer = HybridSynchronizer(self.config)
        
        # Callbacks
        self._sync_callbacks: List[Callable[[SyncGroup], None]] = []
        
        # Stream info
        self._stream_configs: Dict[str, StreamConfig] = {}
        self._active_streams: Dict[str, bool] = {}
        
        # Statistics
        self._sync_count: int = 0
        self._last_sync_time: float = 0.0
    
    def add_stream(self, stream_id: str, config: Optional[StreamConfig] = None) -> bool:
        """Add a stream for synchronization"""
        if stream_id in self._active_streams:
            logger.warning(f"Stream {stream_id} already added")
            return False
        
        self._active_streams[stream_id] = True
        if config:
            self._stream_configs[stream_id] = config
        
        logger.info(f"Added stream {stream_id} for synchronization")
        return True
    
    def remove_stream(self, stream_id: str) -> bool:
        """Remove a stream from synchronization"""
        if stream_id not in self._active_streams:
            logger.warning(f"Stream {stream_id} not found")
            return False
        
        del self._active_streams[stream_id]
        if stream_id in self._stream_configs:
            del self._stream_configs[stream_id]
        
        logger.info(f"Removed stream {stream_id} from synchronization")
        return True
    
    def add_frame(self, stream_id: str, frame: Frame) -> bool:
        """Add a frame from a stream for synchronization"""
        if stream_id not in self._active_streams:
            logger.warning(f"Stream {stream_id} not registered")
            return False
        
        success = self._synchronizer.add_frame(stream_id, frame)
        
        if success:
            # Check for sync groups
            groups = self._synchronizer.find_sync_groups()
            
            for group in groups:
                self._sync_count += 1
                self._last_sync_time = timestamp_now()
                
                # Notify callbacks
                for callback in self._sync_callbacks:
                    try:
                        callback(group)
                    except Exception as e:
                        logger.error(f"Error in sync callback: {e}")
        
        return success
    
    def find_sync_groups(self) -> List[SyncGroup]:
        """Find current sync groups"""
        return self._synchronizer.find_sync_groups()
    
    def add_sync_callback(self, callback: Callable[[SyncGroup], None]) -> None:
        """Add callback for sync groups"""
        self._sync_callbacks.append(callback)
    
    def remove_sync_callback(self, callback: Callable[[SyncGroup], None]) -> None:
        """Remove sync callback"""
        if callback in self._sync_callbacks:
            self._sync_callbacks.remove(callback)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get synchronization statistics"""
        return {
            "sync_count": self._sync_count,
            "last_sync_time": self._last_sync_time,
            "active_streams": len(self._active_streams),
            "stream_ids": list(self._active_streams.keys()),
        }
    
    def reset(self) -> None:
        """Reset the synchronizer"""
        self._sync_count = 0
        self._last_sync_time = 0.0
        self._active_streams.clear()
        self._stream_configs.clear()


def create_synchronizer(config: Optional[SyncConfig] = None) -> StreamSynchronizer:
    """Factory function to create stream synchronizer"""
    return StreamSynchronizer(config)


def create_timestamp_synchronizer(config: Optional[SyncConfig] = None) -> TimestampSynchronizer:
    """Factory function to create timestamp synchronizer"""
    return TimestampSynchronizer(config)


def create_gps_synchronizer(config: Optional[SyncConfig] = None) -> GPSSynchronizer:
    """Factory function to create GPS synchronizer"""
    return GPSSynchronizer(config)


def create_feature_synchronizer(config: Optional[SyncConfig] = None) -> FeatureSynchronizer:
    """Factory function to create feature synchronizer"""
    return FeatureSynchronizer(config)


def create_hybrid_synchronizer(config: Optional[SyncConfig] = None) -> HybridSynchronizer:
    """Factory function to create hybrid synchronizer"""
    return HybridSynchronizer(config)
