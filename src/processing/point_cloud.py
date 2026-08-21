"""
Point cloud processing and visualization

This module provides functionality for:
- Generating point clouds from images
- Processing point clouds
- Visualizing point clouds
- Converting between formats
"""

import os
import time
import json
import struct
import numpy as np
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum

from ..core.models import Frame, GPSData, ProcessingConfig
from ..core.utils import get_logger, timestamp_now, ensure_directory

logger = get_logger("processing.point_cloud")


class PointCloudFormat(Enum):
    """Point cloud file formats"""
    LAS = "las"
    LAZ = "laz"
    PLY = "ply"
    XYZ = "xyz"
    CSV = "csv"
    NUMPY = "numpy"


class PointCloudColorMode(Enum):
    """Color modes for point clouds"""
    NONE = "none"
    RGB = "rgb"
    INTENSITY = "intensity"
    CLASSIFICATION = "classification"
    ELEVATION = "elevation"


@dataclass
class PointCloudConfig:
    """Configuration for point cloud generation"""
    # Generation
    method: str = "sfm"  # sfm, stereo, depth
    density: str = "medium"  # low, medium, high
    
    # Filtering
    min_distance: float = 0.1  # meters
    max_distance: float = 1000.0  # meters
    noise_filter: bool = True
    noise_threshold: float = 2.0  # standard deviations
    
    # Color
    color_mode: PointCloudColorMode = PointCloudColorMode.RGB
    
    # Output
    format: PointCloudFormat = PointCloudFormat.LAS
    
    # Directories
    temp_dir: str = "temp/point_cloud"
    output_dir: str = "data/point_cloud"
    
    @classmethod
    def from_processing_config(cls, config: ProcessingConfig) -> "PointCloudConfig":
        """Create from ProcessingConfig"""
        return cls()


@dataclass
class PointCloud:
    """Represents a 3D point cloud"""
    points: np.ndarray  # Nx3 or Nx6 array (xyz, rgb or xyz, intensity)
    colors: Optional[np.ndarray] = None  # Nx3 array (0-255)
    normals: Optional[np.ndarray] = None  # Nx3 array
    classification: Optional[np.ndarray] = None  # N array
    intensity: Optional[np.ndarray] = None  # N array
    gps_offset: Optional[Tuple[float, float, float]] = None  # (lat, lon, alt)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __len__(self) -> int:
        return len(self.points)
    
    def __getitem__(self, index: int) -> np.ndarray:
        return self.points[index]
    
    def get_xyz(self) -> np.ndarray:
        """Get XYZ coordinates"""
        return self.points[:, :3]
    
    def get_xy(self) -> np.ndarray:
        """Get XY coordinates"""
        return self.points[:, :2]
    
    def get_z(self) -> np.ndarray:
        """Get Z coordinates (elevation)"""
        return self.points[:, 2]
    
    def get_bounds(self) -> Tuple[np.ndarray, np.ndarray]:
        """Get bounding box (min, max)"""
        return np.min(self.points, axis=0), np.max(self.points, axis=0)
    
    def get_center(self) -> np.ndarray:
        """Get center point"""
        return np.mean(self.points, axis=0)
    
    def get_extent(self) -> Tuple[float, float, float]:
        """Get extent (width, height, depth)"""
        min_bounds, max_bounds = self.get_bounds()
        return (
            float(max_bounds[0] - min_bounds[0]),
            float(max_bounds[1] - min_bounds[1]),
            float(max_bounds[2] - min_bounds[2]),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "point_count": len(self),
            "has_colors": self.colors is not None,
            "has_normals": self.normals is not None,
            "has_classification": self.classification is not None,
            "extent": self.get_extent(),
            "metadata": self.metadata,
        }


class PointCloudGenerator:
    """
    Generates point clouds from various sources
    """
    
    def __init__(self, config: Optional[PointCloudConfig] = None):
        self.config = config or PointCloudConfig()
        self._temp_dir = Path(self.config.temp_dir)
        ensure_directory(self._temp_dir)
    
    def generate_from_depth_map(
        self,
        depth_map: np.ndarray,
        color_image: Optional[np.ndarray] = None,
        camera_matrix: Optional[np.ndarray] = None,
        camera_pose: Optional[np.ndarray] = None,
    ) -> Optional[PointCloud]:
        """
        Generate point cloud from depth map
        
        Args:
            depth_map: Depth map (H, W)
            color_image: Optional color image (H, W, 3)
            camera_matrix: Camera intrinsic matrix (3, 3)
            camera_pose: Camera pose matrix (4, 4)
        
        Returns:
            PointCloud or None if failed
        """
        try:
            if camera_matrix is None:
                # Default camera matrix
                h, w = depth_map.shape
                camera_matrix = np.array([
                    [w / 2, 0, w / 2],
                    [0, h / 2, h / 2],
                    [0, 0, 1]
                ], dtype=np.float32)
            
            # Create point cloud from depth
            points = self._depth_to_point_cloud(depth_map, camera_matrix)
            
            # Add colors if available
            colors = None
            if color_image is not None:
                colors = self._extract_colors(depth_map, color_image)
            
            # Apply camera pose if available
            if camera_pose is not None:
                points = self._apply_pose(points, camera_pose)
            
            return PointCloud(
                points=points,
                colors=colors,
                metadata={
                    "method": "depth_map",
                    "source": "depth",
                },
            )
            
        except Exception as e:
            logger.error(f"Error generating point cloud from depth map: {e}")
            return None
    
    def _depth_to_point_cloud(
        self,
        depth_map: np.ndarray,
        camera_matrix: np.ndarray,
    ) -> np.ndarray:
        """Convert depth map to point cloud"""
        h, w = depth_map.shape
        
        # Create pixel coordinates
        u, v = np.meshgrid(np.arange(w), np.arange(h))
        u = u.astype(np.float32)
        v = v.astype(np.float32)
        
        # Flatten
        u_flat = u.flatten()
        v_flat = v.flatten()
        depth_flat = depth_map.flatten()
        
        # Filter out invalid depths
        valid_mask = depth_flat > 0
        u_flat = u_flat[valid_mask]
        v_flat = v_flat[valid_mask]
        depth_flat = depth_flat[valid_mask]
        
        # Calculate 3D points
        fx = camera_matrix[0, 0]
        fy = camera_matrix[1, 1]
        cx = camera_matrix[0, 2]
        cy = camera_matrix[1, 2]
        
        x = (u_flat - cx) * depth_flat / fx
        y = (v_flat - cy) * depth_flat / fy
        z = depth_flat
        
        points = np.column_stack([x, y, z])
        
        return points
    
    def _extract_colors(
        self,
        depth_map: np.ndarray,
        color_image: np.ndarray,
    ) -> np.ndarray:
        """Extract colors for point cloud from color image"""
        h, w = depth_map.shape
        
        # Create pixel coordinates
        u, v = np.meshgrid(np.arange(w), np.arange(h))
        u = u.astype(np.int32)
        v = v.astype(np.int32)
        
        # Flatten
        u_flat = u.flatten()
        v_flat = v.flatten()
        depth_flat = depth_map.flatten()
        
        # Filter out invalid depths
        valid_mask = depth_flat > 0
        u_flat = u_flat[valid_mask]
        v_flat = v_flat[valid_mask]
        
        # Extract colors
        colors = color_image[v_flat, u_flat]
        
        return colors
    
    def _apply_pose(self, points: np.ndarray, pose: np.ndarray) -> np.ndarray:
        """Apply camera pose to points"""
        # Add homogeneous coordinate
        points_hom = np.column_stack([points, np.ones(len(points))])
        
        # Apply pose
        points_transformed = (pose @ points_hom.T).T
        
        # Remove homogeneous coordinate
        return points_transformed[:, :3]
    
    def generate_from_stereo_pair(
        self,
        left_image: np.ndarray,
        right_image: np.ndarray,
        camera_matrix: Optional[np.ndarray] = None,
        baseline: float = 1.0,
        focal_length: float = 1000.0,
    ) -> Optional[PointCloud]:
        """
        Generate point cloud from stereo pair
        
        Args:
            left_image: Left image
            right_image: Right image
            camera_matrix: Camera intrinsic matrix
            baseline: Camera baseline
            focal_length: Camera focal length
        
        Returns:
            PointCloud or None if failed
        """
        try:
            from .dem_generator import StereoDEMGenerator, DEMConfig
            
            # Generate DEM first
            dem_gen = StereoDEMGenerator(DEMConfig())
            dem_result = dem_gen.generate_from_stereo_pair(
                left_image,
                right_image,
                baseline,
                focal_length,
            )
            
            if not dem_result or not dem_result.success:
                return None
            
            # Convert DEM to point cloud
            return self._dem_to_point_cloud(dem_result.dem, dem_result.resolution)
            
        except Exception as e:
            logger.error(f"Error generating point cloud from stereo: {e}")
            return None
    
    def _dem_to_point_cloud(self, dem: np.ndarray, resolution: float) -> PointCloud:
        """Convert DEM to point cloud"""
        h, w = dem.shape
        
        # Create coordinates
        x = np.arange(w) * resolution
        y = np.arange(h) * resolution
        
        xx, yy = np.meshgrid(x, y)
        
        # Flatten
        points = np.column_stack([
            xx.flatten(),
            yy.flatten(),
            dem.flatten(),
        ])
        
        # Filter out invalid points
        valid_mask = dem.flatten() > 0
        points = points[valid_mask]
        
        return PointCloud(
            points=points,
            metadata={
                "method": "dem_conversion",
                "resolution": resolution,
            },
        )
    
    def generate_from_frames(
        self,
        frames: List[Frame],
        method: str = "depth",
    ) -> Optional[PointCloud]:
        """
        Generate point cloud from multiple frames
        
        Args:
            frames: List of frames
            method: Generation method (depth, stereo, sfm)
        
        Returns:
            PointCloud or None if failed
        """
        if not frames:
            logger.error("No frames provided")
            return None
        
        if method == "depth":
            # Use first frame with depth
            if frames[0].data is not None:
                return self.generate_from_depth_map(frames[0].data)
        
        elif method == "stereo" and len(frames) >= 2:
            return self.generate_from_stereo_pair(
                frames[0].data,
                frames[1].data,
            )
        
        logger.error(f"Unknown method or insufficient frames: {method}")
        return None


class PointCloudIO:
    """
    Input/Output for point clouds
    """
    
    def __init__(self, config: Optional[PointCloudConfig] = None):
        self.config = config or PointCloudConfig()
        self._output_dir = Path(self.config.output_dir)
        ensure_directory(self._output_dir)
    
    def save(
        self,
        point_cloud: PointCloud,
        name: str = "point_cloud",
        format: Optional[PointCloudFormat] = None,
    ) -> bool:
        """Save point cloud to file"""
        save_format = format or self.config.format
        
        try:
            output_path = self._output_dir / f"{name}.{save_format.value}"
            
            if save_format == PointCloudFormat.NUMPY:
                return self._save_numpy(point_cloud, output_path)
            
            elif save_format == PointCloudFormat.XYZ:
                return self._save_xyz(point_cloud, output_path)
            
            elif save_format == PointCloudFormat.CSV:
                return self._save_csv(point_cloud, output_path)
            
            elif save_format == PointCloudFormat.PLY:
                return self._save_ply(point_cloud, output_path)
            
            elif save_format == PointCloudFormat.LAS or save_format == PointCloudFormat.LAZ:
                return self._save_las(point_cloud, output_path, save_format == PointCloudFormat.LAZ)
            
            else:
                logger.error(f"Unknown format: {save_format}")
                return False
                
        except Exception as e:
            logger.error(f"Error saving point cloud: {e}")
            return False
    
    def load(self, path: Union[str, Path]) -> Optional[PointCloud]:
        """Load point cloud from file"""
        path = Path(path)
        
        if not path.exists():
            logger.error(f"File not found: {path}")
            return None
        
        try:
            ext = path.suffix.lower()[1:]  # Remove dot
            
            if ext == "npy":
                return self._load_numpy(path)
            
            elif ext == "xyz":
                return self._load_xyz(path)
            
            elif ext == "csv":
                return self._load_csv(path)
            
            elif ext == "ply":
                return self._load_ply(path)
            
            elif ext in ["las", "laz"]:
                return self._load_las(path)
            
            else:
                logger.error(f"Unknown format: {ext}")
                return None
                
        except Exception as e:
            logger.error(f"Error loading point cloud: {e}")
            return None
    
    def _save_numpy(self, point_cloud: PointCloud, path: Path) -> bool:
        """Save as numpy array"""
        data = {
            "points": point_cloud.points,
            "colors": point_cloud.colors,
            "normals": point_cloud.normals,
            "classification": point_cloud.classification,
            "intensity": point_cloud.intensity,
            "metadata": point_cloud.metadata,
        }
        np.save(path, data)
        return True
    
    def _load_numpy(self, path: Path) -> Optional[PointCloud]:
        """Load from numpy array"""
        data = np.load(path, allow_pickle=True).item()
        
        return PointCloud(
            points=data["points"],
            colors=data["colors"],
            normals=data["normals"],
            classification=data["classification"],
            intensity=data["intensity"],
            metadata=data.get("metadata", {}),
        )
    
    def _save_xyz(self, point_cloud: PointCloud, path: Path) -> bool:
        """Save as XYZ file"""
        with open(path, 'w') as f:
            for i in range(len(point_cloud)):
                point = point_cloud.points[i]
                if point_cloud.colors is not None:
                    color = point_cloud.colors[i]
                    f.write(f"{point[0]} {point[1]} {point[2]} {color[0]} {color[1]} {color[2]}\n")
                else:
                    f.write(f"{point[0]} {point[1]} {point[2]}\n")
        return True
    
    def _load_xyz(self, path: Path) -> Optional[PointCloud]:
        """Load from XYZ file"""
        points = []
        colors = []
        
        with open(path, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 3:
                    point = [float(p) for p in parts[:3]]
                    points.append(point)
                    if len(parts) >= 6:
                        color = [int(p) for p in parts[3:6]]
                        colors.append(color)
        
        if not points:
            return None
        
        return PointCloud(
            points=np.array(points),
            colors=np.array(colors) if colors else None,
        )
    
    def _save_csv(self, point_cloud: PointCloud, path: Path) -> bool:
        """Save as CSV file"""
        import csv
        
        with open(path, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Write header
            header = ["x", "y", "z"]
            if point_cloud.colors is not None:
                header.extend(["r", "g", "b"])
            if point_cloud.intensity is not None:
                header.append("intensity")
            if point_cloud.classification is not None:
                header.append("classification")
            writer.writerow(header)
            
            # Write data
            for i in range(len(point_cloud)):
                row = list(point_cloud.points[i])
                if point_cloud.colors is not None:
                    row.extend(list(point_cloud.colors[i]))
                if point_cloud.intensity is not None:
                    row.append(point_cloud.intensity[i])
                if point_cloud.classification is not None:
                    row.append(point_cloud.classification[i])
                writer.writerow(row)
        
        return True
    
    def _load_csv(self, path: Path) -> Optional[PointCloud]:
        """Load from CSV file"""
        import csv
        
        points = []
        colors = []
        intensity = []
        classification = []
        
        with open(path, 'r') as f:
            reader = csv.reader(f)
            header = next(reader)
            
            for row in reader:
                if len(row) >= 3:
                    point = [float(r) for r in row[:3]]
                    points.append(point)
                    
                    if len(row) >= 6:
                        color = [int(r) for r in row[3:6]]
                        colors.append(color)
                    
                    if len(row) >= 7:
                        intensity.append(float(row[6]))
                    
                    if len(row) >= 8:
                        classification.append(int(row[7]))
        
        if not points:
            return None
        
        return PointCloud(
            points=np.array(points),
            colors=np.array(colors) if colors else None,
            intensity=np.array(intensity) if intensity else None,
            classification=np.array(classification) if classification else None,
        )
    
    def _save_ply(self, point_cloud: PointCloud, path: Path) -> bool:
        """Save as PLY file"""
        with open(path, 'w') as f:
            # Write header
            f.write("ply\n")
            f.write("format ascii 1.0\n")
            
            vertex_count = len(point_cloud)
            f.write(f"element vertex {vertex_count}\n")
            
            # Write properties
            f.write("property float x\n")
            f.write("property float y\n")
            f.write("property float z\n")
            
            if point_cloud.colors is not None:
                f.write("property uchar red\n")
                f.write("property uchar green\n")
                f.write("property uchar blue\n")
            
            if point_cloud.intensity is not None:
                f.write("property float intensity\n")
            
            if point_cloud.classification is not None:
                f.write("property uchar classification\n")
            
            f.write("end_header\n")
            
            # Write data
            for i in range(vertex_count):
                point = point_cloud.points[i]
                line = f"{point[0]} {point[1]} {point[2]}"
                
                if point_cloud.colors is not None:
                    color = point_cloud.colors[i]
                    line += f" {color[0]} {color[1]} {color[2]}"
                
                if point_cloud.intensity is not None:
                    line += f" {point_cloud.intensity[i]}"
                
                if point_cloud.classification is not None:
                    line += f" {point_cloud.classification[i]}"
                
                f.write(line + "\n")
        
        return True
    
    def _load_ply(self, path: Path) -> Optional[PointCloud]:
        """Load from PLY file"""
        points = []
        colors = []
        intensity = []
        classification = []
        
        with open(path, 'r') as f:
            # Skip header
            in_header = True
            for line in f:
                if in_header:
                    if line.strip() == "end_header":
                        in_header = False
                    continue
                
                parts = line.strip().split()
                if len(parts) >= 3:
                    point = [float(p) for p in parts[:3]]
                    points.append(point)
                    
                    if len(parts) >= 6:
                        color = [int(p) for p in parts[3:6]]
                        colors.append(color)
                    
                    if len(parts) >= 7:
                        intensity.append(float(parts[6]))
                    
                    if len(parts) >= 8:
                        classification.append(int(parts[7]))
        
        if not points:
            return None
        
        return PointCloud(
            points=np.array(points),
            colors=np.array(colors) if colors else None,
            intensity=np.array(intensity) if intensity else None,
            classification=np.array(classification) if classification else None,
        )
    
    def _save_las(self, point_cloud: PointCloud, path: Path, compressed: bool = False) -> bool:
        """Save as LAS/LAZ file"""
        try:
            import laspy
            
            # Create LAS header
            header = laspy.LasHeader(point_format=2)
            header.scales = [0.01, 0.01, 0.01]  # Scale factors
            header.offsets = [0, 0, 0]  # Offsets
            
            # Create LAS file
            las = laspy.LasData(header)
            
            # Set X, Y, Z
            las.x = point_cloud.points[:, 0].astype(np.int32)
            las.y = point_cloud.points[:, 1].astype(np.int32)
            las.z = point_cloud.points[:, 2].astype(np.int32)
            
            # Set intensity if available
            if point_cloud.intensity is not None:
                las.intensity = point_cloud.intensity.astype(np.uint16)
            
            # Set classification if available
            if point_cloud.classification is not None:
                las.classification = point_cloud.classification.astype(np.uint8)
            
            # Set RGB if available
            if point_cloud.colors is not None:
                las.red = point_cloud.colors[:, 0].astype(np.uint16)
                las.green = point_cloud.colors[:, 1].astype(np.uint16)
                las.blue = point_cloud.colors[:, 2].astype(np.uint16)
            
            # Write file
            las.write(path, compressed=compressed)
            
            return True
            
        except ImportError:
            logger.warning("laspy not available for LAS/LAZ export")
            return False
        except Exception as e:
            logger.error(f"Error saving LAS/LAZ: {e}")
            return False
    
    def _load_las(self, path: Path) -> Optional[PointCloud]:
        """Load from LAS/LAZ file"""
        try:
            import laspy
            
            las = laspy.read(path)
            
            # Get scales and offsets
            x_scale = las.header.scales[0]
            y_scale = las.header.scales[1]
            z_scale = las.header.scales[2]
            x_offset = las.header.offsets[0]
            y_offset = las.header.offsets[1]
            z_offset = las.header.offsets[2]
            
            # Create points
            points = np.column_stack([
                las.x * x_scale + x_offset,
                las.y * y_scale + y_offset,
                las.z * z_scale + z_offset,
            ])
            
            # Create colors if available
            colors = None
            if hasattr(las, 'red') and hasattr(las, 'green') and hasattr(las, 'blue'):
                colors = np.column_stack([las.red, las.green, las.blue])
            
            # Create intensity if available
            intensity = None
            if hasattr(las, 'intensity'):
                intensity = las.intensity
            
            # Create classification if available
            classification = None
            if hasattr(las, 'classification'):
                classification = las.classification
            
            return PointCloud(
                points=points,
                colors=colors,
                intensity=intensity,
                classification=classification,
            )
            
        except ImportError:
            logger.warning("laspy not available for LAS/LAZ import")
            return None
        except Exception as e:
            logger.error(f"Error loading LAS/LAZ: {e}")
            return None


class PointCloudVisualizer:
    """
    Visualizes point clouds using various methods
    """
    
    def __init__(self):
        self._temp_dir = Path("temp/visualization")
        ensure_directory(self._temp_dir)
    
    def create_2d_projection(
        self,
        point_cloud: PointCloud,
        resolution: float = 0.1,
    ) -> np.ndarray:
        """
        Create 2D projection (orthophoto) from point cloud
        
        Args:
            point_cloud: Input point cloud
            resolution: Output resolution (meters per pixel)
        
        Returns:
            2D orthophoto as numpy array
        """
        try:
            if len(point_cloud) == 0:
                return np.zeros((100, 100, 3), dtype=np.uint8)
            
            # Get bounds
            min_bounds, max_bounds = point_cloud.get_bounds()
            
            # Calculate grid dimensions
            width = int(np.ceil((max_bounds[0] - min_bounds[0]) / resolution))
            height = int(np.ceil((max_bounds[1] - min_bounds[1]) / resolution))
            
            # Create empty image
            if point_cloud.colors is not None:
                image = np.zeros((height, width, 3), dtype=np.uint8)
                count = np.zeros((height, width), dtype=np.int32)
            else:
                image = np.zeros((height, width), dtype=np.float32)
                count = np.zeros((height, width), dtype=np.int32)
            
            # Rasterize point cloud
            for i in range(len(point_cloud)):
                point = point_cloud.points[i]
                
                # Convert to image coordinates
                col = int((point[0] - min_bounds[0]) / resolution)
                row = int((point[1] - min_bounds[1]) / resolution)
                
                if 0 <= col < width and 0 <= row < height:
                    if point_cloud.colors is not None:
                        # Average colors
                        color = point_cloud.colors[i]
                        image[row, col] += color
                        count[row, col] += 1
                    else:
                        # Store elevation
                        image[row, col] += point[2]
                        count[row, col] += 1
            
            # Average values
            if point_cloud.colors is not None:
                valid_mask = count > 0
                image[valid_mask] = (image[valid_mask] / count[valid_mask][..., np.newaxis]).astype(np.uint8)
            else:
                valid_mask = count > 0
                image[valid_mask] /= count[valid_mask]
            
            return image
            
        except Exception as e:
            logger.error(f"Error creating 2D projection: {e}")
            return np.zeros((100, 100, 3), dtype=np.uint8)
    
    def create_height_map(
        self,
        point_cloud: PointCloud,
        resolution: float = 0.1,
    ) -> np.ndarray:
        """Create height map from point cloud"""
        # Similar to 2D projection but only elevation
        projection = self.create_2d_projection(point_cloud, resolution)
        
        if len(projection.shape) == 3:
            # Convert to grayscale
            return cv2.cvtColor(projection, cv2.COLOR_RGB2GRAY)
        return projection
    
    def create_slope_map(
        self,
        point_cloud: PointCloud,
        resolution: float = 0.1,
    ) -> np.ndarray:
        """Create slope map from point cloud"""
        # Create height map first
        height_map = self.create_height_map(point_cloud, resolution)
        
        # Calculate gradients
        grad_x = cv2.Sobel(height_map, cv2.CV_32F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(height_map, cv2.CV_32F, 0, 1, ksize=3)
        
        # Calculate slope
        slope = np.arctan(np.sqrt(grad_x**2 + grad_y**2))
        slope_deg = np.degrees(slope)
        
        # Normalize to 0-255
        slope_normalized = (slope_deg / 90.0 * 255).astype(np.uint8)
        
        return slope_normalized
    
    def create_aspect_map(
        self,
        point_cloud: PointCloud,
        resolution: float = 0.1,
    ) -> np.ndarray:
        """Create aspect map from point cloud"""
        # Create height map first
        height_map = self.create_height_map(point_cloud, resolution)
        
        # Calculate gradients
        grad_x = cv2.Sobel(height_map, cv2.CV_32F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(height_map, cv2.CV_32F, 0, 1, ksize=3)
        
        # Calculate aspect
        aspect = np.arctan2(grad_y, grad_x)
        aspect_deg = np.degrees(aspect)
        
        # Convert to 0-360 range
        aspect_deg = np.mod(aspect_deg, 360)
        
        # Normalize to 0-255
        aspect_normalized = (aspect_deg / 360.0 * 255).astype(np.uint8)
        
        return aspect_normalized
    
    def create_contour_lines(
        self,
        point_cloud: PointCloud,
        resolution: float = 0.1,
        interval: float = 1.0,
    ) -> List[np.ndarray]:
        """Create contour lines from point cloud"""
        # Create height map first
        height_map = self.create_height_map(point_cloud, resolution)
        
        # Normalize height map
        height_min = np.min(height_map)
        height_max = np.max(height_map)
        height_range = height_max - height_min
        
        if height_range == 0:
            return []
        
        # Create contours at regular intervals
        contours = []
        for elevation in np.arange(height_min, height_max, interval):
            # Create binary mask for this elevation
            mask = np.abs(height_map - elevation) < (interval / 2)
            contours.append(mask.astype(np.uint8) * 255)
        
        return contours


class PointCloudProcessor:
    """
    Processes point clouds (filtering, classification, etc.)
    """
    
    def __init__(self):
        pass
    
    def filter_outliers(
        self,
        point_cloud: PointCloud,
        threshold: float = 2.0,
    ) -> PointCloud:
        """
        Filter out outliers using statistical method
        
        Args:
            point_cloud: Input point cloud
            threshold: Standard deviation threshold
        
        Returns:
            Filtered point cloud
        """
        try:
            if len(point_cloud) == 0:
                return point_cloud
            
            # Calculate mean and std for each dimension
            mean = np.mean(point_cloud.points, axis=0)
            std = np.std(point_cloud.points, axis=0)
            
            # Calculate z-scores
            z_scores = np.abs((point_cloud.points - mean) / std)
            
            # Find outliers (any dimension above threshold)
            outliers = np.any(z_scores > threshold, axis=1)
            
            # Create filtered point cloud
            filtered_indices = ~outliers
            
            return PointCloud(
                points=point_cloud.points[filtered_indices],
                colors=point_cloud.colors[filtered_indices] if point_cloud.colors is not None else None,
                normals=point_cloud.normals[filtered_indices] if point_cloud.normals is not None else None,
                classification=point_cloud.classification[filtered_indices] if point_cloud.classification is not None else None,
                intensity=point_cloud.intensity[filtered_indices] if point_cloud.intensity is not None else None,
                metadata=point_cloud.metadata,
            )
            
        except Exception as e:
            logger.error(f"Error filtering outliers: {e}")
            return point_cloud
    
    def classify_ground(
        self,
        point_cloud: PointCloud,
        threshold: float = 0.1,
    ) -> PointCloud:
        """
        Classify ground points using simple height threshold
        
        Args:
            point_cloud: Input point cloud
            threshold: Height threshold for ground classification
        
        Returns:
            Point cloud with classification
        """
        try:
            if len(point_cloud) == 0:
                return point_cloud
            
            # Calculate statistics
            z_mean = np.mean(point_cloud.points[:, 2])
            z_std = np.std(point_cloud.points[:, 2])
            
            # Simple classification: points below mean - threshold are ground
            ground_threshold = z_mean - threshold * z_std
            
            classification = np.zeros(len(point_cloud), dtype=np.uint8)
            classification[point_cloud.points[:, 2] < ground_threshold] = 2  # Ground
            classification[point_cloud.points[:, 2] >= ground_threshold] = 1  # Non-ground
            
            return PointCloud(
                points=point_cloud.points,
                colors=point_cloud.colors,
                normals=point_cloud.normals,
                classification=classification,
                intensity=point_cloud.intensity,
                metadata=point_cloud.metadata,
            )
            
        except Exception as e:
            logger.error(f"Error classifying ground: {e}")
            return point_cloud
    
    def simplify(
        self,
        point_cloud: PointCloud,
        ratio: float = 0.5,
    ) -> PointCloud:
        """
        Simplify point cloud by sampling
        
        Args:
            point_cloud: Input point cloud
            ratio: Ratio of points to keep (0-1)
        
        Returns:
            Simplified point cloud
        """
        try:
            if len(point_cloud) == 0:
                return point_cloud
            
            # Random sampling
            num_points = int(len(point_cloud) * ratio)
            indices = np.random.choice(len(point_cloud), num_points, replace=False)
            
            return PointCloud(
                points=point_cloud.points[indices],
                colors=point_cloud.colors[indices] if point_cloud.colors is not None else None,
                normals=point_cloud.normals[indices] if point_cloud.normals is not None else None,
                classification=point_cloud.classification[indices] if point_cloud.classification is not None else None,
                intensity=point_cloud.intensity[indices] if point_cloud.intensity is not None else None,
                metadata=point_cloud.metadata,
            )
            
        except Exception as e:
            logger.error(f"Error simplifying point cloud: {e}")
            return point_cloud
    
    def normalize(
        self,
        point_cloud: PointCloud,
    ) -> PointCloud:
        """
        Normalize point cloud to 0-1 range
        
        Args:
            point_cloud: Input point cloud
        
        Returns:
            Normalized point cloud
        """
        try:
            if len(point_cloud) == 0:
                return point_cloud
            
            min_bounds = np.min(point_cloud.points, axis=0)
            max_bounds = np.max(point_cloud.points, axis=0)
            range_bounds = max_bounds - min_bounds
            
            # Avoid division by zero
            range_bounds[range_bounds == 0] = 1
            
            # Normalize
            normalized_points = (point_cloud.points - min_bounds) / range_bounds
            
            return PointCloud(
                points=normalized_points,
                colors=point_cloud.colors,
                normals=point_cloud.normals,
                classification=point_cloud.classification,
                intensity=point_cloud.intensity,
                metadata=point_cloud.metadata,
            )
            
        except Exception as e:
            logger.error(f"Error normalizing point cloud: {e}")
            return point_cloud


def create_point_cloud_generator(config: Optional[PointCloudConfig] = None) -> PointCloudGenerator:
    """Factory function to create point cloud generator"""
    return PointCloudGenerator(config)


def create_point_cloud_io(config: Optional[PointCloudConfig] = None) -> PointCloudIO:
    """Factory function to create point cloud IO"""
    return PointCloudIO(config)


def create_point_cloud_visualizer() -> PointCloudVisualizer:
    """Factory function to create point cloud visualizer"""
    return PointCloudVisualizer()


def create_point_cloud_processor() -> PointCloudProcessor:
    """Factory function to create point cloud processor"""
    return PointCloudProcessor()
