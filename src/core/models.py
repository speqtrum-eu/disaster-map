"""
Data models for the disaster map system
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum
import numpy as np
from datetime import datetime
import uuid


class StreamType(Enum):
    """Supported video stream types"""
    RTSP = "rtsp"
    RTMP = "rtmp"
    WEBRTC = "webrtc"
    HTTP = "http"
    FILE = "file"
    UDP = "udp"


class StreamStatus(Enum):
    """Stream connection status"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    PROCESSING = "processing"


class FrameProcessingStatus(Enum):
    """Frame processing status"""
    RAW = "raw"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class GPSSource(Enum):
    """GPS data source"""
    EMBEDDED = "embedded"  # From video metadata
    EXTERNAL = "external"  # From external GPS device
    MANUAL = "manual"  # Manually specified
    NONE = "none"  # No GPS data


@dataclass
class GPSData:
    """GPS coordinate data"""
    latitude: float = 0.0
    longitude: float = 0.0
    altitude: float = 0.0  # meters
    heading: float = 0.0  # degrees (0-360)
    tilt: float = 0.0  # degrees (0-90, 0=level, 90=straight down)
    roll: float = 0.0  # degrees
    accuracy: float = 0.0  # meters
    timestamp: float = 0.0  # Unix timestamp
    source: GPSSource = GPSSource.NONE
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "altitude": self.altitude,
            "heading": self.heading,
            "tilt": self.tilt,
            "roll": self.roll,
            "accuracy": self.accuracy,
            "timestamp": self.timestamp,
            "source": self.source.value,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GPSData":
        data["source"] = GPSSource(data.get("source", "none"))
        return cls(**data)


@dataclass
class CameraCalibration:
    """Camera intrinsic and distortion parameters"""
    fx: float = 1.0  # Focal length x
    fy: float = 1.0  # Focal length y
    cx: float = 0.0  # Principal point x
    cy: float = 0.0  # Principal point y
    width: int = 0  # Image width
    height: int = 0  # Image height
    distortion: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0, 0.0])  # k1, k2, p1, p2, k3
    
    def get_camera_matrix(self) -> np.ndarray:
        """Get OpenCV camera matrix"""
        return np.array([
            [self.fx, 0, self.cx],
            [0, self.fy, self.cy],
            [0, 0, 1]
        ], dtype=np.float64)
    
    def get_distortion_coeffs(self) -> np.ndarray:
        """Get OpenCV distortion coefficients"""
        return np.array(self.distortion, dtype=np.float64)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "fx": self.fx,
            "fy": self.fy,
            "cx": self.cx,
            "cy": self.cy,
            "width": self.width,
            "height": self.height,
            "distortion": self.distortion,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CameraCalibration":
        return cls(**data)


@dataclass
class Frame:
    """A single video frame with metadata"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    stream_id: str = ""
    data: Optional[np.ndarray] = None  # BGR image data
    timestamp: float = 0.0  # Unix timestamp (seconds)
    frame_number: int = 0
    gps: Optional[GPSData] = None
    calibration: Optional[CameraCalibration] = None
    resolution: Tuple[int, int] = (0, 0)
    status: FrameProcessingStatus = FrameProcessingStatus.RAW
    features: Optional[Dict[str, Any]] = None  # Extracted features
    descriptors: Optional[np.ndarray] = None  # Feature descriptors
    keypoints: Optional[List[Tuple[float, float]]] = None  # (x, y) coordinates
    
    def __post_init__(self):
        if self.data is not None and self.resolution == (0, 0):
            self.resolution = (self.data.shape[1], self.data.shape[0])
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "stream_id": self.stream_id,
            "timestamp": self.timestamp,
            "frame_number": self.frame_number,
            "gps": self.gps.to_dict() if self.gps else None,
            "calibration": self.calibration.to_dict() if self.calibration else None,
            "resolution": list(self.resolution),
            "status": self.status.value,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Frame":
        frame = cls(
            id=data.get("id", str(uuid.uuid4())),
            stream_id=data.get("stream_id", ""),
            timestamp=data.get("timestamp", 0.0),
            frame_number=data.get("frame_number", 0),
            resolution=tuple(data.get("resolution", [0, 0])),
            status=FrameProcessingStatus(data.get("status", "raw")),
        )
        if data.get("gps"):
            frame.gps = GPSData.from_dict(data["gps"])
        if data.get("calibration"):
            frame.calibration = CameraCalibration.from_dict(data["calibration"])
        return frame


@dataclass
class ProcessingConfig:
    """Configuration for orthomosaic processing"""
    # Feature detection
    detector: str = "SIFT"  # SIFT, SURF, ORB, AKAZE
    min_features: int = 1000
    
    # Feature matching
    matcher: str = "FLANN"  # FLANN, BFMatcher
    min_matches: int = 50
    ratio_test: float = 0.75
    
    # Stitching
    stitch_method: str = "homography"  # homography, bundle_adjustment
    confidence_threshold: float = 0.8
    reprojection_error: float = 5.0
    
    # Image processing
    frame_skip: int = 1  # Process every Nth frame
    keyframe_interval: float = 1.0  # Seconds between keyframes
    
    # Quality settings
    quality: str = "high"  # high, medium, low
    tile_size: int = 256  # Pixels
    overlap: int = 20  # Percent
    resolution: float = 0.1  # Meters per pixel
    
    # Geospatial
    coordinate_system: str = "EPSG:4326"  # WGS84
    target_system: str = "EPSG:3857"  # Web Mercator
    
    # Performance
    use_gpu: bool = False
    max_memory: int = 8  # GB
    num_workers: int = 4
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "detector": self.detector,
            "min_features": self.min_features,
            "matcher": self.matcher,
            "min_matches": self.min_matches,
            "ratio_test": self.ratio_test,
            "stitch_method": self.stitch_method,
            "confidence_threshold": self.confidence_threshold,
            "reprojection_error": self.reprojection_error,
            "frame_skip": self.frame_skip,
            "keyframe_interval": self.keyframe_interval,
            "quality": self.quality,
            "tile_size": self.tile_size,
            "overlap": self.overlap,
            "resolution": self.resolution,
            "coordinate_system": self.coordinate_system,
            "target_system": self.target_system,
            "use_gpu": self.use_gpu,
            "max_memory": self.max_memory,
            "num_workers": self.num_workers,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProcessingConfig":
        return cls(**data)


@dataclass
class StreamConfig:
    """Configuration for a single video stream"""
    id: str = ""
    name: str = ""
    enabled: bool = True
    stream_type: StreamType = StreamType.RTSP
    url: str = ""
    
    # Video properties
    resolution: Tuple[int, int] = (1920, 1080)
    fps: float = 30.0
    bitrate: int = 8000
    
    # GPS settings
    gps: bool = False
    gps_source: GPSSource = GPSSource.EMBEDDED
    external_gps: Optional[Dict[str, Any]] = None
    
    # Camera calibration
    calibration: Optional[CameraCalibration] = None
    
    # Geospatial settings
    altitude: float = 100.0  # meters (if GPS doesn't provide)
    heading: float = 0.0  # degrees
    tilt: float = 90.0  # degrees
    
    # Processing settings (overrides global)
    processing: Optional[ProcessingConfig] = None
    
    def to_dict(self) -> Dict[str, Any]:
        data = {
            "id": self.id,
            "name": self.name,
            "enabled": self.enabled,
            "stream_type": self.stream_type.value,
            "url": self.url,
            "resolution": list(self.resolution),
            "fps": self.fps,
            "bitrate": self.bitrate,
            "gps": self.gps,
            "gps_source": self.gps_source.value,
            "external_gps": self.external_gps,
            "altitude": self.altitude,
            "heading": self.heading,
            "tilt": self.tilt,
        }
        if self.calibration:
            data["calibration"] = self.calibration.to_dict()
        if self.processing:
            data["processing"] = self.processing.to_dict()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StreamConfig":
        config = cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            enabled=data.get("enabled", True),
            stream_type=StreamType(data.get("stream_type", "rtsp")),
            url=data.get("url", ""),
            resolution=tuple(data.get("resolution", [1920, 1080])),
            fps=data.get("fps", 30.0),
            bitrate=data.get("bitrate", 8000),
            gps=data.get("gps", False),
            gps_source=GPSSource(data.get("gps_source", "embedded")),
            external_gps=data.get("external_gps"),
            altitude=data.get("altitude", 100.0),
            heading=data.get("heading", 0.0),
            tilt=data.get("tilt", 90.0),
        )
        if data.get("calibration"):
            config.calibration = CameraCalibration.from_dict(data["calibration"])
        if data.get("processing"):
            config.processing = ProcessingConfig.from_dict(data["processing"])
        return config


@dataclass
class OrthomosaicTile:
    """A tile in the orthomosaic map"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    x: int = 0  # Tile coordinate
    y: int = 0
    z: int = 0  # Zoom level
    data: Optional[np.ndarray] = None  # Image data (RGB)
    timestamp: float = 0.0  # When this tile was generated
    bounds: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)  # (min_x, min_y, max_x, max_y) in world coords
    source_frames: List[str] = field(default_factory=list)  # IDs of source frames
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "timestamp": self.timestamp,
            "bounds": list(self.bounds),
            "source_frames": self.source_frames,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OrthomosaicTile":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            x=data.get("x", 0),
            y=data.get("y", 0),
            z=data.get("z", 0),
            timestamp=data.get("timestamp", 0.0),
            bounds=tuple(data.get("bounds", [0.0, 0.0, 0.0, 0.0])),
            source_frames=data.get("source_frames", []),
        )


@dataclass
class VideoStream:
    """Represents an active video stream"""
    config: StreamConfig
    status: StreamStatus = StreamStatus.DISCONNECTED
    connection: Any = None  # Stream connection object
    frame_count: int = 0
    last_frame_time: float = 0.0
    fps_actual: float = 0.0
    error_message: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "config": self.config.to_dict(),
            "status": self.status.value,
            "frame_count": self.frame_count,
            "last_frame_time": self.last_frame_time,
            "fps_actual": self.fps_actual,
            "error_message": self.error_message,
        }
