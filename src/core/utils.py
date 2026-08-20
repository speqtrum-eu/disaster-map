"""
Utility functions for the disaster map system
"""

import logging
import yaml
import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
from datetime import datetime
import numpy as np
import cv2


def get_logger(name: str = "disaster_map") -> logging.Logger:
    """Get a configured logger"""
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        # Configure only once
        logger.setLevel(logging.INFO)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        console_handler.setFormatter(console_formatter)
        
        # File handler
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / "disaster_map.log"
        file_handler = logging.FileHandler(log_file, mode="a")
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(file_formatter)
        
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
    
    return logger


# Global logger instance
logger = get_logger()


def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from YAML file"""
    path = Path(config_path)
    if not path.exists():
        logger.error(f"Config file not found: {config_path}")
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(path, "r") as f:
        config = yaml.safe_load(f)
    
    logger.info(f"Loaded configuration from {config_path}")
    return config


def save_config(config: Dict[str, Any], config_path: str) -> None:
    """Save configuration to YAML file"""
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    
    logger.info(f"Saved configuration to {config_path}")


def validate_config(config: Dict[str, Any]) -> bool:
    """Validate configuration structure"""
    required_sections = ["streams", "processing", "storage", "network"]
    
    for section in required_sections:
        if section not in config:
            logger.error(f"Missing required config section: {section}")
            return False
    
    # Validate streams
    if "streams" in config:
        for stream_id, stream_config in config["streams"].items():
            if "type" not in stream_config:
                logger.error(f"Stream {stream_id} missing 'type' field")
                return False
            if "url" not in stream_config:
                logger.error(f"Stream {stream_id} missing 'url' field")
                return False
    
    return True


def timestamp_now() -> float:
    """Get current Unix timestamp"""
    return time.time()


def datetime_now() -> datetime:
    """Get current datetime"""
    return datetime.now()


def calculate_iou(box1: Tuple[float, float, float, float], 
                 box2: Tuple[float, float, float, float]) -> float:
    """
    Calculate Intersection over Union (IoU) of two bounding boxes
    
    Args:
        box1: (x1, y1, x2, y2)
        box2: (x1, y1, x2, y2)
    
    Returns:
        IoU ratio (0.0 to 1.0)
    """
    # Determine the coordinates of the intersection rectangle
    x_left = max(box1[0], box2[0])
    y_top = max(box1[1], box2[1])
    x_right = min(box1[2], box2[2])
    y_bottom = min(box1[3], box2[3])
    
    if x_right < x_left or y_bottom < y_top:
        return 0.0
    
    # Calculate intersection area
    intersection_area = (x_right - x_left) * (y_bottom - y_top)
    
    # Calculate union area
    box1_area = (box1[2] - box1[0]) * (box1[3] - box1[1])
    box2_area = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union_area = box1_area + box2_area - intersection_area
    
    if union_area == 0:
        return 0.0
    
    return intersection_area / union_area


def resize_with_aspect(image: np.ndarray, 
                       max_size: int = 2048) -> np.ndarray:
    """
    Resize image while maintaining aspect ratio
    
    Args:
        image: Input image (H, W, C)
        max_size: Maximum dimension (width or height)
    
    Returns:
        Resized image
    """
    h, w = image.shape[:2]
    
    # Calculate scale factor
    scale = max_size / max(h, w)
    if scale >= 1.0:
        return image  # No need to resize
    
    new_w = int(w * scale)
    new_h = int(h * scale)
    
    return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)


def normalize_image(image: np.ndarray) -> np.ndarray:
    """
    Normalize image to 0-1 range
    
    Args:
        image: Input image (any dtype)
    
    Returns:
        Normalized image (float32, 0-1)
    """
    if image.dtype == np.uint8:
        return image.astype(np.float32) / 255.0
    elif image.dtype == np.uint16:
        return image.astype(np.float32) / 65535.0
    elif image.dtype == np.float32 or image.dtype == np.float64:
        # Assume already normalized or needs clamping
        return np.clip(image, 0.0, 1.0).astype(np.float32)
    else:
        # Generic normalization
        img_min = image.min()
        img_max = image.max()
        if img_max - img_min > 0:
            return ((image - img_min) / (img_max - img_min)).astype(np.float32)
        return np.zeros_like(image, dtype=np.float32)


def denormalize_image(image: np.ndarray) -> np.ndarray:
    """
    Convert normalized image back to uint8
    
    Args:
        image: Normalized image (float32, 0-1)
    
    Returns:
        uint8 image (0-255)
    """
    return (np.clip(image, 0.0, 1.0) * 255).astype(np.uint8)


def blend_images(img1: np.ndarray, img2: np.ndarray, 
                  mask: Optional[np.ndarray] = None) -> np.ndarray:
    """
    Blend two images using alpha blending or mask
    
    Args:
        img1: Background image
        img2: Foreground image (same size as img1)
        mask: Optional blend mask (0-255, same size as img1)
    
    Returns:
        Blended image
    """
    if img1.shape != img2.shape:
        raise ValueError(f"Image shapes don't match: {img1.shape} vs {img2.shape}")
    
    if mask is None:
        # Simple alpha blending
        alpha = 0.5
        return (img1 * (1 - alpha) + img2 * alpha).astype(np.uint8)
    else:
        # Mask-based blending
        if mask.shape != img1.shape[:2]:
            raise ValueError(f"Mask shape doesn't match images: {mask.shape} vs {img1.shape[:2]}")
        
        # Normalize mask to 0-1
        mask_norm = mask.astype(np.float32) / 255.0
        
        # Blend using mask
        result = img1.astype(np.float32) * (1 - mask_norm[..., np.newaxis]) + \
                 img2.astype(np.float32) * mask_norm[..., np.newaxis]
        
        return result.astype(np.uint8)


def create_pyramid(image: np.ndarray, levels: int = 4) -> List[np.ndarray]:
    """
    Create image pyramid for multi-scale processing
    
    Args:
        image: Input image
        levels: Number of pyramid levels
    
    Returns:
        List of images from largest to smallest
    """
    pyramid = [image]
    for _ in range(levels - 1):
        h, w = pyramid[-1].shape[:2]
        pyramid.append(cv2.resize(pyramid[-1], (w // 2, h // 2), interpolation=cv2.INTER_AREA))
    return pyramid


def get_data_dir() -> Path:
    """Get or create the data directory"""
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    return data_dir


def get_temp_dir() -> Path:
    """Get or create the temp directory"""
    temp_dir = Path("temp")
    temp_dir.mkdir(exist_ok=True)
    return temp_dir


def cleanup_temp_files(max_age_hours: int = 24) -> None:
    """Clean up old temporary files"""
    temp_dir = get_temp_dir()
    cutoff_time = time.time() - (max_age_hours * 3600)
    
    for file_path in temp_dir.glob("*"):
        if file_path.is_file():
            try:
                mtime = file_path.stat().st_mtime
                if mtime < cutoff_time:
                    file_path.unlink()
                    logger.info(f"Cleaned up temp file: {file_path}")
            except Exception as e:
                logger.error(f"Error cleaning up {file_path}: {e}")


def ensure_directory(path: str) -> Path:
    """Ensure a directory exists"""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path
