"""
DEM (Digital Elevation Model) and DTM (Digital Terrain Model) generation

This module provides functionality for generating elevation models from
stereo imagery and point clouds.
"""

import os
import time
import json
import tempfile
import threading
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum

import numpy as np
import cv2

from ..core.models import Frame, OrthomosaicTile, GPSData, ProcessingConfig
from ..core.utils import get_logger, timestamp_now, ensure_directory

logger = get_logger("processing.dem_generator")


class DEMMethod(Enum):
    """Methods for DEM generation"""
    STEREO_SGBM = "stereo_sgbm"  # Semi-Global Block Matching
    STEREO_BM = "stereo_bm"  # Block Matching
    POINT_CLOUD = "point_cloud"  # From point cloud
    PYODM = "pyodm"  # Using PyODM


class DEMOutputFormat(Enum):
    """Output formats for DEM"""
    GEOTIFF = "geotiff"
    ASCII = "ascii"
    NUMPY = "numpy"
    PNG = "png"


@dataclass
class DEMConfig:
    """Configuration for DEM generation"""
    # Method
    method: DEMMethod = DEMMethod.STEREO_SGBM
    
    # Stereo settings
    min_disparity: int = 0
    num_disparities: int = 64
    block_size: int = 5
    P1: int = 8 * 3 * 5**2  # SGBM parameter
    P2: int = 32 * 3 * 5**2  # SGBM parameter
    
    # Output
    output_format: DEMOutputFormat = DEMOutputFormat.GEOTIFF
    resolution: float = 1.0  # meters per pixel
    
    # Filtering
    median_filter_size: int = 5
    gaussian_filter_size: int = 5
    gaussian_sigma: float = 1.0
    
    # Geospatial
    coordinate_system: str = "EPSG:4326"
    
    # Directories
    temp_dir: str = "temp/dem"
    output_dir: str = "data/dem"
    
    @classmethod
    def from_processing_config(cls, config: ProcessingConfig) -> "DEMConfig":
        """Create from ProcessingConfig"""
        return cls(
            resolution=config.resolution if config.resolution else 0.1,
        )


@dataclass
class DEMResult:
    """Result from DEM generation"""
    dem: Optional[np.ndarray] = None
    dtm: Optional[np.ndarray] = None
    resolution: float = 0.0
    bounds: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    gps_bounds: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    processing_time: float = 0.0
    success: bool = False
    error_message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "resolution": self.resolution,
            "bounds": list(self.bounds),
            "gps_bounds": list(self.gps_bounds),
            "processing_time": self.processing_time,
            "success": self.success,
            "error_message": self.error_message,
            "metadata": self.metadata,
        }
    
    def get_elevation_at(self, x: int, y: int) -> Optional[float]:
        """Get elevation at a specific coordinate"""
        if self.dem is None:
            return None
        
        if 0 <= x < self.dem.shape[1] and 0 <= y < self.dem.shape[0]:
            return float(self.dem[y, x])
        return None
    
    def get_slope_at(self, x: int, y: int) -> Optional[float]:
        """Calculate slope at a specific coordinate (degrees)"""
        if self.dem is None:
            return None
        
        # Simple 3x3 Sobel filter for slope calculation
        if x < 1 or x >= self.dem.shape[1] - 1 or y < 1 or y >= self.dem.shape[0] - 1:
            return 0.0
        
        # Get 3x3 neighborhood
        kernel_x = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]])
        kernel_y = np.array([[-1, -2, -1], [0, 0, 0], [1, 2, 1]])
        
        neighborhood = self.dem[y-1:y+2, x-1:x+2]
        
        # Calculate gradients
        grad_x = np.sum(kernel_x * neighborhood)
        grad_y = np.sum(kernel_y * neighborhood)
        
        # Calculate slope in degrees
        slope_rad = np.arctan(np.sqrt(grad_x**2 + grad_y**2))
        slope_deg = np.degrees(slope_rad)
        
        return float(slope_deg)
    
    def get_aspect_at(self, x: int, y: int) -> Optional[float]:
        """Calculate aspect at a specific coordinate (degrees)"""
        if self.dem is None:
            return None
        
        if x < 1 or x >= self.dem.shape[1] - 1 or y < 1 or y >= self.dem.shape[0] - 1:
            return 0.0
        
        # Get 3x3 neighborhood
        kernel_x = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]])
        kernel_y = np.array([[-1, -2, -1], [0, 0, 0], [1, 2, 1]])
        
        neighborhood = self.dem[y-1:y+2, x-1:x+2]
        
        # Calculate gradients
        grad_x = np.sum(kernel_x * neighborhood)
        grad_y = np.sum(kernel_y * neighborhood)
        
        # Calculate aspect in degrees
        aspect_rad = np.arctan2(grad_y, grad_x)
        aspect_deg = np.degrees(aspect_rad)
        
        # Convert to 0-360 range
        if aspect_deg < 0:
            aspect_deg += 360
        
        return float(aspect_deg)


class StereoDEMGenerator:
    """
    Generates DEM from stereo imagery using OpenCV
    
    This generator:
    1. Takes stereo image pairs
    2. Computes disparity maps
    3. Converts to elevation
    4. Filters and smooths the result
    """
    
    def __init__(self, config: Optional[DEMConfig] = None):
        self.config = config or DEMConfig()
        self._temp_dir = Path(self.config.temp_dir)
        ensure_directory(self._temp_dir)
    
    def generate_from_stereo_pair(
        self,
        left_image: np.ndarray,
        right_image: np.ndarray,
        baseline: float = 1.0,
        focal_length: float = 1000.0,
    ) -> DEMResult:
        """
        Generate DEM from a stereo image pair
        
        Args:
            left_image: Left image (numpy array)
            right_image: Right image (numpy array)
            baseline: Camera baseline (meters)
            focal_length: Camera focal length (pixels)
        
        Returns:
            DEMResult with generated DEM
        """
        start_time = timestamp_now()
        
        try:
            # Convert to grayscale
            left_gray = cv2.cvtColor(left_image, cv2.COLOR_BGR2GRAY)
            right_gray = cv2.cvtColor(right_image, cv2.COLOR_BGR2GRAY)
            
            # Compute disparity
            if self.config.method == DEMMethod.STEREO_SGBM:
                disparity = self._compute_sgbm_disparity(left_gray, right_gray)
            else:
                disparity = self._compute_bm_disparity(left_gray, right_gray)
            
            if disparity is None:
                return DEMResult(
                    success=False,
                    error_message="Failed to compute disparity",
                    processing_time=timestamp_now() - start_time,
                )
            
            # Convert disparity to elevation
            dem = self._disparity_to_elevation(disparity, baseline, focal_length)
            
            # Filter the DEM
            dem = self._filter_dem(dem)
            
            # Calculate bounds
            bounds = (0, 0, dem.shape[1], dem.shape[0])
            
            return DEMResult(
                dem=dem,
                resolution=self.config.resolution,
                bounds=bounds,
                processing_time=timestamp_now() - start_time,
                success=True,
                metadata={
                    "method": self.config.method.value,
                    "baseline": baseline,
                    "focal_length": focal_length,
                },
            )
            
        except Exception as e:
            logger.error(f"Error generating DEM: {e}")
            return DEMResult(
                success=False,
                error_message=str(e),
                processing_time=timestamp_now() - start_time,
            )
    
    def _compute_sgbm_disparity(
        self,
        left: np.ndarray,
        right: np.ndarray,
    ) -> Optional[np.ndarray]:
        """Compute disparity using Semi-Global Block Matching"""
        try:
            # Create SGBM stereo matcher
            min_disparity = self.config.min_disparity
            num_disparities = self.config.num_disparities
            block_size = self.config.block_size
            
            stereo = cv2.StereoSGBM_create(
                minDisparity=min_disparity,
                numDisparities=num_disparities,
                blockSize=block_size,
                P1=self.config.P1,
                P2=self.config.P2,
                mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY,
            )
            
            # Compute disparity
            disparity = stereo.compute(left, right).astype(np.float32) / 16.0
            
            return disparity
            
        except Exception as e:
            logger.error(f"Error computing SGBM disparity: {e}")
            return None
    
    def _compute_bm_disparity(
        self,
        left: np.ndarray,
        right: np.ndarray,
    ) -> Optional[np.ndarray]:
        """Compute disparity using Block Matching"""
        try:
            # Create BM stereo matcher
            stereo = cv2.StereoBM_create(
                numDisparities=self.config.num_disparities,
                blockSize=self.config.block_size,
            )
            
            # Compute disparity
            disparity = stereo.compute(left, right).astype(np.float32)
            
            return disparity
            
        except Exception as e:
            logger.error(f"Error computing BM disparity: {e}")
            return None
    
    def _disparity_to_elevation(
        self,
        disparity: np.ndarray,
        baseline: float,
        focal_length: float,
    ) -> np.ndarray:
        """Convert disparity map to elevation"""
        # Remove invalid disparities (typically negative or zero)
        valid_mask = disparity > 0
        
        # Calculate elevation: elevation = (baseline * focal_length) / disparity
        elevation = np.zeros_like(disparity)
        elevation[valid_mask] = (baseline * focal_length) / disparity[valid_mask]
        
        # Fill invalid areas with interpolation
        elevation = self._fill_invalid_areas(elevation)
        
        return elevation
    
    def _fill_invalid_areas(self, dem: np.ndarray) -> np.ndarray:
        """Fill invalid areas in DEM using interpolation"""
        # Create mask of valid values
        valid_mask = dem > 0
        
        # Create indices for valid and invalid pixels
        xx, yy = np.meshgrid(np.arange(dem.shape[1]), np.arange(dem.shape[0]))
        
        # Interpolate invalid areas
        from scipy.interpolate import griddata
        
        valid_points = np.column_stack([xx[valid_mask], yy[valid_mask]])
        valid_values = dem[valid_mask]
        
        invalid_points = np.column_stack([xx[~valid_mask], yy[~valid_mask]])
        
        if len(valid_points) > 0 and len(invalid_points) > 0:
            interpolated = griddata(
                valid_points,
                valid_values,
                invalid_points,
                method='linear',
                fill_value=0,
            )
            
            # Update DEM with interpolated values
            dem[~valid_mask] = interpolated
        
        return dem
    
    def _filter_dem(self, dem: np.ndarray) -> np.ndarray:
        """Apply filters to DEM"""
        # Median filter
        if self.config.median_filter_size > 0:
            dem = cv2.medianBlur(dem, self.config.median_filter_size)
        
        # Gaussian filter
        if self.config.gaussian_filter_size > 0:
            dem = cv2.GaussianBlur(
                dem,
                (self.config.gaussian_filter_size, self.config.gaussian_filter_size),
                self.config.gaussian_sigma,
            )
        
        return dem
    
    def generate_from_frames(
        self,
        frames: List[Frame],
        baseline: float = 1.0,
        focal_length: float = 1000.0,
    ) -> Optional[DEMResult]:
        """
        Generate DEM from a list of frames (for multi-view stereo)
        
        Args:
            frames: List of frames (at least 2 for stereo)
            baseline: Camera baseline (meters)
            focal_length: Camera focal length (pixels)
        
        Returns:
            DEMResult or None if failed
        """
        if len(frames) < 2:
            logger.error("Need at least 2 frames for stereo DEM")
            return None
        
        # For now, just use first two frames
        left_frame = frames[0]
        right_frame = frames[1]
        
        if left_frame.data is None or right_frame.data is None:
            logger.error("Frames have no data")
            return None
        
        return self.generate_from_stereo_pair(
            left_frame.data,
            right_frame.data,
            baseline,
            focal_length,
        )


class PointCloudDEMGenerator:
    """
    Generates DEM from point cloud data
    
    This generator:
    1. Takes point cloud data
    2. Rasterizes to DEM
    3. Filters and smooths the result
    """
    
    def __init__(self, config: Optional[DEMConfig] = None):
        self.config = config or DEMConfig()
        self._temp_dir = Path(self.config.temp_dir)
        ensure_directory(self._temp_dir)
    
    def generate_from_point_cloud(
        self,
        point_cloud: np.ndarray,
        resolution: Optional[float] = None,
    ) -> DEMResult:
        """
        Generate DEM from point cloud
        
        Args:
            point_cloud: Point cloud as numpy array (N, 3 or N, 4)
            resolution: Output resolution (meters per pixel)
        
        Returns:
            DEMResult with generated DEM
        """
        start_time = timestamp_now()
        use_resolution = resolution or self.config.resolution
        
        try:
            if point_cloud.shape[1] < 3:
                return DEMResult(
                    success=False,
                    error_message="Point cloud must have at least 3 columns (x, y, z)",
                    processing_time=timestamp_now() - start_time,
                )
            
            # Extract coordinates
            x_coords = point_cloud[:, 0]
            y_coords = point_cloud[:, 1]
            z_coords = point_cloud[:, 2]
            
            # Calculate bounds
            min_x, max_x = np.min(x_coords), np.max(x_coords)
            min_y, max_y = np.min(y_coords), np.max(y_coords)
            
            # Calculate grid dimensions
            width = int(np.ceil((max_x - min_x) / use_resolution))
            height = int(np.ceil((max_y - min_y) / use_resolution))
            
            # Create DEM grid
            dem = np.zeros((height, width), dtype=np.float32)
            count = np.zeros((height, width), dtype=np.int32)
            
            # Rasterize point cloud
            for i in range(len(point_cloud)):
                x, y, z = x_coords[i], y_coords[i], z_coords[i]
                
                # Convert to grid coordinates
                col = int((x - min_x) / use_resolution)
                row = int((y - min_y) / use_resolution)
                
                if 0 <= col < width and 0 <= row < height:
                    dem[row, col] += z
                    count[row, col] += 1
            
            # Average points in each cell
            valid_mask = count > 0
            dem[valid_mask] /= count[valid_mask]
            
            # Fill invalid areas
            dem = self._fill_invalid_areas(dem)
            
            # Filter the DEM
            dem = self._filter_dem(dem)
            
            bounds = (min_x, min_y, max_x, max_y)
            
            return DEMResult(
                dem=dem,
                resolution=use_resolution,
                bounds=bounds,
                processing_time=timestamp_now() - start_time,
                success=True,
                metadata={
                    "method": "point_cloud",
                    "point_count": len(point_cloud),
                },
            )
            
        except Exception as e:
            logger.error(f"Error generating DEM from point cloud: {e}")
            return DEMResult(
                success=False,
                error_message=str(e),
                processing_time=timestamp_now() - start_time,
            )
    
    def _fill_invalid_areas(self, dem: np.ndarray) -> np.ndarray:
        """Fill invalid areas in DEM"""
        # Use same method as stereo generator
        valid_mask = dem > 0
        
        from scipy.interpolate import griddata
        
        xx, yy = np.meshgrid(np.arange(dem.shape[1]), np.arange(dem.shape[0]))
        
        valid_points = np.column_stack([xx[valid_mask], yy[valid_mask]])
        valid_values = dem[valid_mask]
        
        invalid_points = np.column_stack([xx[~valid_mask], yy[~valid_mask]])
        
        if len(valid_points) > 0 and len(invalid_points) > 0:
            interpolated = griddata(
                valid_points,
                valid_values,
                invalid_points,
                method='linear',
                fill_value=0,
            )
            
            dem[~valid_mask] = interpolated
        
        return dem
    
    def _filter_dem(self, dem: np.ndarray) -> np.ndarray:
        """Apply filters to DEM"""
        # Median filter
        if self.config.median_filter_size > 0:
            dem = cv2.medianBlur(dem, self.config.median_filter_size)
        
        # Gaussian filter
        if self.config.gaussian_filter_size > 0:
            dem = cv2.GaussianBlur(
                dem,
                (self.config.gaussian_filter_size, self.config.gaussian_filter_size),
                self.config.gaussian_sigma,
            )
        
        return dem


class MultiViewDEMGenerator:
    """
    Generates DEM from multiple images using Multi-View Stereo (MVS)
    
    This is a more advanced generator that:
    1. Takes multiple overlapping images
    2. Uses structure-from-motion to estimate camera poses
    3. Uses multi-view stereo to generate dense point cloud
    4. Rasterizes point cloud to DEM
    """
    
    def __init__(self, config: Optional[DEMConfig] = None):
        self.config = config or DEMConfig()
        self._temp_dir = Path(self.config.temp_dir)
        ensure_directory(self._temp_dir)
    
    def generate_from_frames(
        self,
        frames: List[Frame],
        config: Optional[DEMConfig] = None,
    ) -> Optional[DEMResult]:
        """
        Generate DEM from multiple frames using MVS
        
        Args:
            frames: List of frames (at least 5-10 for good results)
            config: DEM configuration
        
        Returns:
            DEMResult or None if failed
        """
        if len(frames) < 5:
            logger.warning("Need at least 5 frames for good MVS results")
            return None
        
        # For now, use COLMAP or OpenSfM for MVS
        # This would require additional implementation
        
        logger.warning("Multi-view stereo DEM generation not fully implemented")
        
        # Fallback to stereo pair
        stereo_gen = StereoDEMGenerator(config)
        return stereo_gen.generate_from_frames(frames[:2])


class DEMEngine:
    """
    Main DEM generation engine
    
    This engine:
    1. Selects appropriate DEM generation method
    2. Generates DEM from available data
    3. Manages DEM storage and retrieval
    """
    
    def __init__(self, config: Optional[DEMConfig] = None):
        self.config = config or DEMConfig()
        
        # Create generators
        self._stereo_generator = StereoDEMGenerator(self.config)
        self._point_cloud_generator = PointCloudDEMGenerator(self.config)
        self._multi_view_generator = MultiViewDEMGenerator(self.config)
        
        # Storage
        self._dem_storage = DEMStorage(self.config)
    
    def generate(
        self,
        method: DEMMethod,
        **kwargs
    ) -> Optional[DEMResult]:
        """
        Generate DEM using specified method
        
        Args:
            method: DEM generation method
            **kwargs: Method-specific arguments
        
        Returns:
            DEMResult or None if failed
        """
        try:
            if method == DEMMethod.STEREO_SGBM or method == DEMMethod.STEREO_BM:
                self.config.method = method
                return self._stereo_generator.generate_from_frames(
                    kwargs.get('frames', []),
                    kwargs.get('baseline', 1.0),
                    kwargs.get('focal_length', 1000.0),
                )
            
            elif method == DEMMethod.POINT_CLOUD:
                return self._point_cloud_generator.generate_from_point_cloud(
                    kwargs.get('point_cloud'),
                    kwargs.get('resolution'),
                )
            
            elif method == DEMMethod.PYODM:
                # Use PyODM for DEM generation
                return self._generate_with_pyodm(kwargs)
            
            else:
                logger.error(f"Unknown DEM method: {method}")
                return None
                
        except Exception as e:
            logger.error(f"Error generating DEM: {e}")
            return None
    
    def _generate_with_pyodm(self, kwargs: Dict[str, Any]) -> Optional[DEMResult]:
        """Generate DEM using PyODM"""
        from .pyodm_integration import PyODMClient, ODMConfig, ODMOutputType
        
        try:
            # Create PyODM client
            pyodm_config = ODMConfig(
                output_types=[ODMOutputType.DSM, ODMOutputType.DTM],
                dsm=True,
                dtm=True,
            )
            client = PyODMClient(pyodm_config)
            
            if not client.is_available:
                logger.error("PyODM not available for DEM generation")
                return None
            
            # Get frames
            frames = kwargs.get('frames', [])
            if not frames:
                logger.error("No frames provided for PyODM DEM")
                return None
            
            # Save frames as images
            from .pyodm_integration import BatchOrthomosaicGenerator
            generator = BatchOrthomosaicGenerator(client)
            image_paths = generator._save_frames_as_images(frames)
            
            if not image_paths:
                return None
            
            # Create project
            project = client.create_project(
                name=f"dem_{timestamp_now()}",
                images=[str(p) for p in image_paths],
            )
            
            if not project:
                return None
            
            # Process with DSM/DTM output
            result = client.process_project(
                project,
                config=pyodm_config,
                wait=True,
            )
            
            if not result or not result.success:
                return None
            
            # Convert to DEMResult
            dem_result = DEMResult(
                dem=result.dsm,
                dtm=result.dtm,
                resolution=self.config.resolution,
                processing_time=result.processing_time,
                success=True,
                metadata={
                    "method": "pyodm",
                    "project_id": result.project_id,
                },
            )
            
            # Cleanup
            generator._cleanup_temp_images(image_paths)
            
            return dem_result
            
        except Exception as e:
            logger.error(f"Error generating DEM with PyODM: {e}")
            return None
    
    def save_dem(self, result: DEMResult, name: str = "dem") -> bool:
        """Save DEM result to storage"""
        return self._dem_storage.save(result, name)
    
    def load_dem(self, name: str) -> Optional[DEMResult]:
        """Load DEM from storage"""
        return self._dem_storage.load(name)
    
    def get_dem_list(self) -> List[str]:
        """Get list of saved DEMs"""
        return self._dem_storage.list_dems()
    
    def delete_dem(self, name: str) -> bool:
        """Delete a saved DEM"""
        return self._dem_storage.delete(name)


class DEMStorage:
    """Storage for DEM data"""
    
    def __init__(self, config: Optional[DEMConfig] = None):
        self.config = config or DEMConfig()
        self._storage_dir = Path(self.config.output_dir)
        ensure_directory(self._storage_dir)
    
    def save(self, result: DEMResult, name: str) -> bool:
        """Save DEM result"""
        try:
            # Create output directory
            output_dir = self._storage_dir / name
            ensure_directory(output_dir)
            
            # Save DEM as numpy array
            if result.dem is not None:
                dem_path = output_dir / "dem.npy"
                np.save(dem_path, result.dem)
            
            # Save DTM if available
            if result.dtm is not None:
                dtm_path = output_dir / "dtm.npy"
                np.save(dtm_path, result.dtm)
            
            # Save metadata
            metadata_path = output_dir / "metadata.json"
            with open(metadata_path, 'w') as f:
                json.dump(result.to_dict(), f, indent=2)
            
            return True
            
        except Exception as e:
            logger.error(f"Error saving DEM: {e}")
            return False
    
    def load(self, name: str) -> Optional[DEMResult]:
        """Load DEM from storage"""
        try:
            output_dir = self._storage_dir / name
            
            if not output_dir.exists():
                return None
            
            # Load DEM
            dem_path = output_dir / "dem.npy"
            dem = np.load(dem_path) if dem_path.exists() else None
            
            # Load DTM
            dtm_path = output_dir / "dtm.npy"
            dtm = np.load(dtm_path) if dtm_path.exists() else None
            
            # Load metadata
            metadata_path = output_dir / "metadata.json"
            metadata = {}
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
            
            return DEMResult(
                dem=dem,
                dtm=dtm,
                resolution=metadata.get("resolution", 0.0),
                bounds=tuple(metadata.get("bounds", [0.0, 0.0, 0.0, 0.0])),
                gps_bounds=tuple(metadata.get("gps_bounds", [0.0, 0.0, 0.0, 0.0])),
                success=metadata.get("success", False),
                error_message=metadata.get("error_message", ""),
                metadata=metadata.get("metadata", {}),
            )
            
        except Exception as e:
            logger.error(f"Error loading DEM: {e}")
            return None
    
    def list_dems(self) -> List[str]:
        """List all saved DEMs"""
        try:
            dems = []
            for item in self._storage_dir.iterdir():
                if item.is_dir():
                    metadata_path = item / "metadata.json"
                    if metadata_path.exists():
                        dems.append(item.name)
            return dems
        except Exception as e:
            logger.error(f"Error listing DEMs: {e}")
            return []
    
    def delete(self, name: str) -> bool:
        """Delete a saved DEM"""
        try:
            output_dir = self._storage_dir / name
            if output_dir.exists():
                import shutil
                shutil.rmtree(output_dir)
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting DEM: {e}")
            return False


def create_dem_engine(config: Optional[DEMConfig] = None) -> DEMEngine:
    """Factory function to create DEM engine"""
    return DEMEngine(config)


def create_stereo_dem_generator(config: Optional[DEMConfig] = None) -> StereoDEMGenerator:
    """Factory function to create stereo DEM generator"""
    return StereoDEMGenerator(config)


def create_point_cloud_dem_generator(config: Optional[DEMConfig] = None) -> PointCloudDEMGenerator:
    """Factory function to create point cloud DEM generator"""
    return PointCloudDEMGenerator(config)
