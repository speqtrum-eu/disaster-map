"""
Orthomosaic stitching implementations
"""

import cv2
import numpy as np
from typing import Optional, List, Tuple, Dict, Any, Deque
from dataclasses import dataclass, field
from collections import deque
from enum import Enum

from ..core.models import Frame, OrthomosaicTile, ProcessingConfig, StreamConfig
from ..core.utils import get_logger, resize_with_aspect, blend_images, create_pyramid
from .feature_matcher import FeatureMatcher, create_matcher, MatchResult

logger = get_logger("processing.stitcher")


class StitchingMethod(Enum):
    """Stitching method types"""
    HOMOGRAPHY = "homography"
    BUNDLE_ADJUSTMENT = "bundle_adjustment"
    INCREMENTAL = "incremental"


@dataclass
class StitchingConfig:
    """Configuration for stitching"""
    method: StitchingMethod = StitchingMethod.INCREMENTAL
    confidence_threshold: float = 0.8
    reprojection_error: float = 5.0
    min_matches: int = 50
    blend_method: str = "alpha"  # alpha, feather, pyramid
    seam_find: bool = True  # Find optimal seam
    
    # For incremental stitching
    reference_update_interval: int = 10  # Update reference every N frames
    max_canvas_size: Tuple[int, int] = (8192, 8192)  # Maximum orthomosaic size
    
    # For tiling
    tile_size: int = 256
    overlap: int = 20  # percent
    
    @classmethod
    def from_processing_config(cls, config: ProcessingConfig) -> "StitchingConfig":
        """Create from ProcessingConfig"""
        return cls(
            method=StitchingMethod(config.stitch_method) if hasattr(config, 'stitch_method') else StitchingMethod.INCREMENTAL,
            confidence_threshold=config.confidence_threshold,
            reprojection_error=config.reprojection_error,
            min_matches=config.min_matches,
        )


class OrthoStitcher:
    """Base class for orthomosaic stitching"""
    
    def __init__(self, config: Optional[StitchingConfig] = None):
        self.config = config or StitchingConfig()
        self._matcher: Optional[FeatureMatcher] = None
        self._initialize_matcher()
    
    def _initialize_matcher(self) -> None:
        """Initialize feature matcher"""
        # Create a processing config for the matcher
        proc_config = ProcessingConfig(
            detector="SIFT",
            min_features=1000,
            matcher="FLANN",
            min_matches=self.config.min_matches,
            ratio_test=0.75,
            confidence_threshold=self.config.confidence_threshold,
            reprojection_error=self.config.reprojection_error,
        )
        self._matcher = create_matcher("sift", proc_config)
    
    def add_frame(self, frame: Frame) -> bool:
        """Add a frame to the stitcher"""
        raise NotImplementedError
    
    def get_orthomosaic(self) -> Optional[np.ndarray]:
        """Get the current orthomosaic"""
        raise NotImplementedError
    
    def get_tiles(self) -> List[OrthomosaicTile]:
        """Get orthomosaic tiles"""
        raise NotImplementedError
    
    def reset(self) -> None:
        """Reset the stitcher"""
        raise NotImplementedError


class HomographyStitcher(OrthoStitcher):
    """
    Stitcher using homography-based alignment
    
    This stitcher:
    1. Uses feature matching to find homography between frames
    2. Warps new frames to the reference frame
    3. Blends them into a single orthomosaic
    """
    
    def __init__(self, config: Optional[StitchingConfig] = None):
        super().__init__(config)
        self._reference_frame: Optional[Frame] = None
        self._reference_kp: Optional[List[cv2.KeyPoint]] = None
        self._reference_desc: Optional[np.ndarray] = None
        self._orthomosaic: Optional[np.ndarray] = None
        self._canvas: Optional[np.ndarray] = None  # Canvas for accumulation
        self._canvas_mask: Optional[np.ndarray] = None  # Mask for valid regions
        self._frame_count: int = 0
        self._transformations: List[np.ndarray] = []  # List of homography matrices
    
    def add_frame(self, frame: Frame) -> bool:
        """Add a frame and update orthomosaic"""
        if frame.data is None:
            logger.warning("Cannot add frame with no data")
            return False
        
        try:
            # First frame - initialize
            if self._reference_frame is None:
                return self._initialize_with_frame(frame)
            
            # Subsequent frames - match and stitch
            return self._stitch_frame(frame)
            
        except Exception as e:
            logger.error(f"Error adding frame: {e}")
            return False
    
    def _initialize_with_frame(self, frame: Frame) -> bool:
        """Initialize with the first frame"""
        self._reference_frame = frame
        self._frame_count = 1
        
        # Extract features for reference
        gray = cv2.cvtColor(frame.data, cv2.COLOR_BGR2GRAY)
        self._reference_kp, self._reference_desc = self._matcher.detect_and_compute(gray)
        
        # Initialize orthomosaic with first frame
        self._orthomosaic = frame.data.copy()
        self._canvas = frame.data.copy()
        self._canvas_mask = np.ones(frame.data.shape[:2], dtype=np.uint8) * 255
        
        # Identity transformation
        self._transformations.append(np.eye(3))
        
        logger.info("Initialized stitcher with first frame")
        return True
    
    def _stitch_frame(self, frame: Frame) -> bool:
        """Stitch a new frame to the orthomosaic"""
        if self._reference_frame is None or self._matcher is None:
            return False
        
        # Match frames
        match_result = self._matcher.match_frames(self._reference_frame, frame)
        
        if match_result is None:
            logger.debug("Frame matching failed, skipping")
            return False
        
        if match_result.homography is None:
            logger.debug("Homography estimation failed, skipping")
            return False
        
        # Get transformation
        H = match_result.homography
        self._transformations.append(H)
        
        # Warp current frame to reference
        warped = cv2.warpPerspective(
            frame.data, 
            H, 
            (self._canvas.shape[1], self._canvas.shape[0]),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT
        )
        
        # Create mask for warped frame
        warped_mask = cv2.warpPerspective(
            np.ones(frame.data.shape[:2], dtype=np.uint8) * 255,
            H,
            (self._canvas.shape[1], self._canvas.shape[0]),
            flags=cv2.INTER_NEAREST,
            borderMode=cv2.BORDER_CONSTANT
        )
        
        # Blend with existing orthomosaic
        if self.config.blend_method == "alpha":
            # Simple alpha blending
            alpha = 0.5
            blended = cv2.addWeighted(
                self._orthomosaic, 1 - alpha, 
                warped, alpha, 
                0
            )
        elif self.config.blend_method == "feather":
            # Feather blending (smoother transitions)
            # Create feathered mask
            kernel_size = min(warped.shape[:2]) // 10
            if kernel_size > 0:
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
                feathered_mask = cv2.dilate(warped_mask, kernel)
                feathered_mask = cv2.GaussianBlur(feathered_mask, (kernel_size, kernel_size), 0)
                feathered_mask = feathered_mask.astype(np.float32) / 255.0
                
                # Blend using mask
                blended = self._orthomosaic.astype(np.float32) * (1 - feathered_mask[..., np.newaxis]) + \
                          warped.astype(np.float32) * feathered_mask[..., np.newaxis]
                blended = blended.astype(np.uint8)
            else:
                blended = warped
        else:
            # No blending - just use warped
            blended = warped
        
        # Update orthomosaic
        self._orthomosaic = blended
        
        # Update canvas and mask
        self._canvas = np.where(warped_mask[..., np.newaxis] > 0, warped, self._canvas)
        self._canvas_mask = cv2.bitwise_or(self._canvas_mask, warped_mask)
        
        self._frame_count += 1
        
        # Periodically update reference frame
        if self.config.reference_update_interval > 0 and \
           self._frame_count % self.config.reference_update_interval == 0:
            self._update_reference_frame(frame)
        
        return True
    
    def _update_reference_frame(self, frame: Frame) -> None:
        """Update the reference frame"""
        self._reference_frame = frame
        gray = cv2.cvtColor(frame.data, cv2.COLOR_BGR2GRAY)
        self._reference_kp, self._reference_desc = self._matcher.detect_and_compute(gray)
        logger.info(f"Updated reference frame (frame {self._frame_count})")
    
    def get_orthomosaic(self) -> Optional[np.ndarray]:
        """Get the current orthomosaic"""
        return self._orthomosaic
    
    def get_tiles(self) -> List[OrthomosaicTile]:
        """Generate tiles from orthomosaic"""
        if self._orthomosaic is None:
            return []
        
        tiles = []
        h, w = self._orthomosaic.shape[:2]
        
        # Simple tiling - single level
        tile_size = self.config.tile_size
        for y in range(0, h, tile_size):
            for x in range(0, w, tile_size):
                tile = self._orthomosaic[y:y+tile_size, x:x+tile_size]
                if tile.size > 0:
                    tile_obj = OrthomosaicTile(
                        x=x // tile_size,
                        y=y // tile_size,
                        z=0,
                        data=tile.copy(),
                        timestamp=self._reference_frame.timestamp if self._reference_frame else 0.0,
                    )
                    tiles.append(tile_obj)
        
        return tiles
    
    def reset(self) -> None:
        """Reset the stitcher"""
        self._reference_frame = None
        self._reference_kp = None
        self._reference_desc = None
        self._orthomosaic = None
        self._canvas = None
        self._canvas_mask = None
        self._frame_count = 0
        self._transformations = []
        logger.info("Stitcher reset")


class IncrementalStitcher(OrthoStitcher):
    """
    Incremental stitcher for real-time orthomosaic generation
    
    This stitcher:
    1. Maintains a growing canvas
    2. Adds frames incrementally using homography
    3. Expands canvas as needed
    4. Optimized for real-time performance
    """
    
    def __init__(self, config: Optional[StitchingConfig] = None):
        super().__init__(config)
        self._canvas: Optional[np.ndarray] = None  # Accumulated orthomosaic
        self._canvas_mask: Optional[np.ndarray] = None  # Valid regions mask
        self._reference_frame: Optional[Frame] = None
        self._frame_count: int = 0
        self._total_frames: int = 0
        
        # Canvas dimensions
        self._canvas_width: int = 0
        self._canvas_height: int = 0
        self._canvas_offset_x: int = 0
        self._canvas_offset_y: int = 0
    
    def add_frame(self, frame: Frame) -> bool:
        """Add a frame and update orthomosaic incrementally"""
        if frame.data is None:
            logger.warning("Cannot add frame with no data")
            return False
        
        self._total_frames += 1
        
        try:
            # First frame - initialize
            if self._canvas is None:
                return self._initialize_canvas(frame)
            
            # Subsequent frames - match and stitch
            return self._stitch_incremental(frame)
            
        except Exception as e:
            logger.error(f"Error adding frame: {e}")
            return False
    
    def _initialize_canvas(self, frame: Frame) -> bool:
        """Initialize canvas with first frame"""
        self._reference_frame = frame
        
        # Initialize canvas with frame
        self._canvas = frame.data.copy()
        self._canvas_mask = np.ones(frame.data.shape[:2], dtype=np.uint8) * 255
        
        # Set canvas dimensions
        self._canvas_width = frame.data.shape[1]
        self._canvas_height = frame.data.shape[0]
        self._canvas_offset_x = 0
        self._canvas_offset_y = 0
        
        self._frame_count = 1
        logger.info(f"Initialized canvas with frame: {frame.resolution}")
        return True
    
    def _stitch_incremental(self, frame: Frame) -> bool:
        """Stitch frame incrementally to canvas"""
        if self._canvas is None or self._matcher is None:
            return False
        
        # Match with reference frame
        match_result = self._matcher.match_frames(self._reference_frame, frame)
        
        if match_result is None or match_result.homography is None:
            logger.debug("Frame matching failed, skipping")
            return False
        
        # Estimate transformation from frame to canvas
        H = match_result.homography
        
        # Calculate new canvas bounds
        new_bounds = self._calculate_new_bounds(H, frame.data.shape)
        
        # Expand canvas if needed
        if new_bounds[2] > self._canvas_width or new_bounds[3] > self._canvas_height or \
           new_bounds[0] < 0 or new_bounds[1] < 0:
            self._expand_canvas(new_bounds)
        
        # Calculate placement in canvas
        H_canvas = self._calculate_canvas_homography(H, new_bounds)
        
        # Warp frame to canvas
        warped = cv2.warpPerspective(
            frame.data,
            H_canvas,
            (self._canvas_width, self._canvas_height),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT
        )
        
        # Create mask
        mask = cv2.warpPerspective(
            np.ones(frame.data.shape[:2], dtype=np.uint8) * 255,
            H_canvas,
            (self._canvas_width, self._canvas_height),
            flags=cv2.INTER_NEAREST,
            borderMode=cv2.BORDER_CONSTANT
        )
        
        # Blend with existing canvas
        self._canvas = self._blend_frames(self._canvas, warped, mask)
        self._canvas_mask = cv2.bitwise_or(self._canvas_mask, mask)
        
        self._frame_count += 1
        
        # Periodically update reference
        if self.config.reference_update_interval > 0 and \
           self._frame_count % self.config.reference_update_interval == 0:
            self._update_reference(frame)
        
        return True
    
    def _calculate_new_bounds(self, H: np.ndarray, frame_shape: Tuple[int, int, int]) -> Tuple[int, int, int, int]:
        """Calculate new canvas bounds after applying homography"""
        h, w = frame_shape[:2]
        
        # Get canvas corners in frame coordinates
        corners = np.array([
            [0, 0, 1],
            [w, 0, 1],
            [w, h, 1],
            [0, h, 1]
        ], dtype=np.float32).T
        
        # Transform to canvas coordinates
        transformed = np.dot(H, corners).T
        transformed = transformed[:, :2] / transformed[:, 2:]
        
        # Get bounding box
        min_x = int(np.min(transformed[:, 0]))
        min_y = int(np.min(transformed[:, 1]))
        max_x = int(np.max(transformed[:, 0]))
        max_y = int(np.max(transformed[:, 1]))
        
        return (min_x, min_y, max_x, max_y)
    
    def _expand_canvas(self, bounds: Tuple[int, int, int, int]) -> None:
        """Expand canvas to accommodate new bounds"""
        min_x, min_y, max_x, max_y = bounds
        
        # Calculate new dimensions
        new_width = max(self._canvas_width, max_x - self._canvas_offset_x)
        new_height = max(self._canvas_height, max_y - self._canvas_offset_y)
        
        # Calculate offset adjustment
        offset_x = min(0, min_x - self._canvas_offset_x)
        offset_y = min(0, min_y - self._canvas_offset_y)
        
        # Adjust offset
        self._canvas_offset_x += offset_x
        self._canvas_offset_y += offset_y
        
        # Create new canvas
        new_canvas = np.zeros((new_height, new_width, 3), dtype=np.uint8)
        new_mask = np.zeros((new_height, new_width), dtype=np.uint8)
        
        # Copy existing content
        if self._canvas is not None:
            old_x = -self._canvas_offset_x
            old_y = -self._canvas_offset_y
            new_canvas[old_y:old_y+self._canvas_height, old_x:old_x+self._canvas_width] = self._canvas
            new_mask[old_y:old_y+self._canvas_height, old_x:old_x+self._canvas_width] = self._canvas_mask
        
        # Update canvas
        self._canvas = new_canvas
        self._canvas_mask = new_mask
        self._canvas_width = new_width
        self._canvas_height = new_height
        
        logger.info(f"Expanded canvas to {new_width}x{new_height}, offset ({self._canvas_offset_x}, {self._canvas_offset_y})")
    
    def _calculate_canvas_homography(self, H: np.ndarray, bounds: Tuple[int, int, int, int]) -> np.ndarray:
        """Calculate homography from frame to canvas coordinates"""
        # Adjust homography for canvas offset
        offset_H = np.eye(3)
        offset_H[0, 2] = -bounds[0] - self._canvas_offset_x
        offset_H[1, 2] = -bounds[1] - self._canvas_offset_y
        
        return np.dot(offset_H, H)
    
    def _blend_frames(self, canvas: np.ndarray, warped: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """Blend warped frame with canvas"""
        if self.config.blend_method == "alpha":
            alpha = 0.5
            return cv2.addWeighted(canvas, 1 - alpha, warped, alpha, 0)
        elif self.config.blend_method == "feather":
            kernel_size = min(warped.shape[:2]) // 20
            if kernel_size > 0:
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
                feathered_mask = cv2.dilate(mask, kernel)
                feathered_mask = cv2.GaussianBlur(feathered_mask, (kernel_size * 2 + 1, kernel_size * 2 + 1), 0)
                feathered_mask = feathered_mask.astype(np.float32) / 255.0
                
                result = canvas.astype(np.float32) * (1 - feathered_mask[..., np.newaxis]) + \
                         warped.astype(np.float32) * feathered_mask[..., np.newaxis]
                return result.astype(np.uint8)
        
        # Default: use mask
        return np.where(mask[..., np.newaxis] > 0, warped, canvas)
    
    def _update_reference(self, frame: Frame) -> None:
        """Update reference frame"""
        self._reference_frame = frame
        logger.info(f"Updated reference frame (total frames: {self._total_frames})")
    
    def get_orthomosaic(self) -> Optional[np.ndarray]:
        """Get the current orthomosaic"""
        if self._canvas is None:
            return None
        
        # Crop to valid region
        if self._canvas_mask is not None:
            coords = np.argwhere(self._canvas_mask > 0)
            if len(coords) > 0:
                min_y, min_x = coords.min(axis=0)
                max_y, max_x = coords.max(axis=0)
                return self._canvas[min_y:max_y+1, min_x:max_x+1]
        
        return self._canvas
    
    def get_tiles(self, zoom_level: int = 0) -> List[OrthomosaicTile]:
        """Generate tiles from orthomosaic at specified zoom level"""
        ortho = self.get_orthomosaic()
        if ortho is None:
            return []
        
        tiles = []
        tile_size = self.config.tile_size
        
        # Calculate zoom level scaling
        scale = 1.0 / (2 ** zoom_level)
        scaled_tile_size = int(tile_size * scale)
        
        h, w = ortho.shape[:2]
        
        # Generate tiles
        for y in range(0, h, scaled_tile_size):
            for x in range(0, w, scaled_tile_size):
                tile_data = ortho[y:y+scaled_tile_size, x:x+scaled_tile_size]
                if tile_data.size > 0:
                    # Resize to standard tile size if needed
                    if scale != 1.0:
                        tile_data = cv2.resize(tile_data, (tile_size, tile_size), interpolation=cv2.INTER_AREA)
                    
                    tile_obj = OrthomosaicTile(
                        x=x // scaled_tile_size,
                        y=y // scaled_tile_size,
                        z=zoom_level,
                        data=tile_data.copy(),
                        timestamp=self._reference_frame.timestamp if self._reference_frame else 0.0,
                    )
                    tiles.append(tile_obj)
        
        return tiles
    
    def reset(self) -> None:
        """Reset the stitcher"""
        self._canvas = None
        self._canvas_mask = None
        self._reference_frame = None
        self._frame_count = 0
        self._total_frames = 0
        self._canvas_width = 0
        self._canvas_height = 0
        self._canvas_offset_x = 0
        self._canvas_offset_y = 0
        logger.info("Incremental stitcher reset")


class BundleAdjustmentStitcher(OrthoStitcher):
    """
    Stitcher using bundle adjustment for better accuracy
    
    This stitcher:
    1. Collects multiple frames
    2. Performs bundle adjustment to optimize camera poses
    3. Generates orthomosaic from optimized poses
    
    Note: More computationally expensive, better for batch processing
    """
    
    def __init__(self, config: Optional[StitchingConfig] = None):
        super().__init__(config)
        self._frames: List[Frame] = []
        self._camera_poses: List[np.ndarray] = []  # List of camera matrices
        self._point_cloud: Optional[np.ndarray] = None  # 3D point cloud
        
    def add_frame(self, frame: Frame) -> bool:
        """Add a frame for bundle adjustment"""
        self._frames.append(frame)
        logger.info(f"Added frame {len(self._frames)} for bundle adjustment")
        return True
    
    def process(self) -> bool:
        """Process all frames with bundle adjustment"""
        if len(self._frames) < 2:
            logger.warning("Need at least 2 frames for bundle adjustment")
            return False
        
        try:
            # This would implement bundle adjustment
            # For now, fallback to incremental stitching
            logger.warning("Bundle adjustment not implemented, using incremental stitching")
            
            stitcher = IncrementalStitcher(self.config)
            for frame in self._frames:
                stitcher.add_frame(frame)
            
            self._orthomosaic = stitcher.get_orthomosaic()
            return self._orthomosaic is not None
            
        except Exception as e:
            logger.error(f"Error in bundle adjustment: {e}")
            return False
    
    def get_orthomosaic(self) -> Optional[np.ndarray]:
        """Get the current orthomosaic"""
        return getattr(self, '_orthomosaic', None)
    
    def get_tiles(self) -> List[OrthomosaicTile]:
        """Get orthomosaic tiles"""
        return []
    
    def reset(self) -> None:
        """Reset the stitcher"""
        self._frames = []
        self._camera_poses = []
        self._point_cloud = None


def create_stitcher(method: str, config: Optional[StitchingConfig] = None) -> OrthoStitcher:
    """Factory function to create a stitcher"""
    method = method.lower()
    
    if method == "homography":
        return HomographyStitcher(config)
    elif method == "incremental":
        return IncrementalStitcher(config)
    elif method == "bundle_adjustment":
        return BundleAdjustmentStitcher(config)
    else:
        logger.warning(f"Unknown stitching method: {method}, using incremental")
        return IncrementalStitcher(config)
