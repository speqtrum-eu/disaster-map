"""
Core module containing data models and utilities
"""

from .models import (
    Frame,
    VideoStream,
    GPSData,
    CameraCalibration,
    OrthomosaicTile,
    ProcessingConfig,
    StreamConfig,
)
from .utils import (
    get_logger,
    load_config,
    save_config,
    validate_config,
    timestamp_now,
    calculate_iou,
    resize_with_aspect,
)

__all__ = [
    "Frame",
    "VideoStream",
    "GPSData",
    "CameraCalibration",
    "OrthomosaicTile",
    "ProcessingConfig",
    "StreamConfig",
    "get_logger",
    "load_config",
    "save_config",
    "validate_config",
    "timestamp_now",
    "calculate_iou",
    "resize_with_aspect",
]
