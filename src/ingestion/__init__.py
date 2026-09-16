"""Ingestion layer for video stream processing.

This module provides:
- FFmpeg-based video stream consumers
- Keyframe extraction with motion detection
- Redis message queue integration for frame delivery
"""

from .base import BaseStreamConsumer, FrameData
from .ffmpeg_consumer import FFmpegStreamConsumer
from .keyframe_extractor import (
    KeyframeExtractor, 
    KeyframeConfig, 
    KeyframeResult,
    ExtractionMode,
    extract_keyframes,
    frame_similarity
)
from .message_queue import (
    MessageQueue, 
    FrameMessage, 
    AckMessage,
    create_queue,
    publish_frame,
    send_ack
)

__all__ = [
    # Base classes
    "BaseStreamConsumer",
    "FrameData",
    
    # FFmpeg consumer
    "FFmpegStreamConsumer",
    
    # Keyframe extraction
    "KeyframeExtractor",
    "KeyframeConfig",
    "KeyframeResult",
    "ExtractionMode",
    "extract_keyframes",
    "frame_similarity",
    
    # Message queue
    "MessageQueue",
    "FrameMessage",
    "AckMessage",
    "create_queue",
    "publish_frame",
    "send_ack",
]
