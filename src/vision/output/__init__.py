"""Output layer for storing and serving reconstruction results.

Supports:
- Cloud Optimized GeoTIFF (COG) generation
- PostGIS spatio-temporal storage
- Tile-based output for web visualization
- Real-time streaming of pose updates
"""

import numpy as np
from typing import Tuple, Optional, List, Dict, Any
from dataclasses import dataclass
import time


@dataclass
class OutputConfig:
    """Configuration for output generation."""
    
    # COG settings
    cog_tile_size: int = 256  # Tile size in pixels
    cog_compression: str = "deflate"  # deflate | lzw | jpeg
    cog_overviews: bool = True
    
    # Storage settings
    storage_format: str = "geotiff"  # geotiff | netcdf
    coordinate_system: str = "EPSG:4326"  # WGS84 default
    
    # Performance
    batch_size: int = 100
    use_gpu: bool = True


@dataclass
class OutputResult:
    """Results from output generation."""
    
    file_path: str
    tile_count: int
    processing_time_ms: float
    metadata: Dict[str, Any]
    
    @property
    def is_cog(self) -> bool:
        return self.metadata.get('is_cloud_optimized', False)


class OutputGeneratorBase:
    """Abstract base class for output generators."""
    
    def __init__(self, config: Optional[OutputConfig] = None):
        self.config = config or OutputConfig()
        self._initialized = False
    
    @property
    def generator_type(self) -> str:
        raise NotImplementedError
    
    def initialize(self) -> bool:
        """Initialize the output generator."""
        raise NotImplementedError
    
    def generate(
        self, 
        poses: List[Any],  # Camera poses or reconstruction data
        points_3d: Optional[np.ndarray] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> OutputResult:
        """Generate output file(s) from reconstruction data.
        
        Args:
            poses: List of camera poses or other reconstruction data
            points_3d: Optional 3D point cloud data
            metadata: Additional metadata to store
            
        Returns:
            OutputResult with file path and statistics
        """
        raise NotImplementedError
    
    def generate_tiles(
        self, 
        orthomosaic_data: np.ndarray,
        extent: Tuple[float, float, float, float],  # (minx, miny, maxx, maxy)
        resolution: float = 0.5  # Meters per pixel
    ) -> List[Dict[str, Any]]:
        """Generate tile-based output for web visualization.
        
        Args:
            orthomosaic_data: Orthomosaic image data (H, W, C)
            extent: Geographic extent in meters
            resolution: Ground sampling distance in meters/pixel
            
        Returns:
            List of tile metadata with file paths and coordinates
        """
        raise NotImplementedError


class COGGenerator(OutputGeneratorBase):
    """Cloud Optimized GeoTIFF generator for orthomosaics.
    
    Generates COGs optimized for cloud storage and web delivery.
    Supports multi-resolution overviews and efficient compression.
    """
    
    def __init__(self, config: Optional[OutputConfig] = None):
        super().__init__(config)
        
        self._gdal_initialized = False
    
    @property
    def generator_type(self) -> str:
        return "cog"
    
    def initialize(self) -> bool:
        """Initialize GDAL for COG generation."""
        try:
            import osgeo.gdal as gdal
            
            # Initialize GDAL with proper drivers
            gdal.UseExceptions()
            
            # Register all available drivers
            gdal.AllRegister()
            
            self._gdal_initialized = True
            
        except Exception as e:
            print(f"Failed to initialize GDAL: {e}")
            return False
        
        return True
    
    def generate(
        self, 
        poses: List[Any], 
        points_3d: Optional[np.ndarray] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> OutputResult:
        """Generate COG from reconstruction data.
        
        Args:
            poses: Camera poses for georeferencing
            points_3d: 3D point cloud (optional)
            metadata: Additional metadata
            
        Returns:
            OutputResult with COG file path
        """
        start_time = time.time()
        
        try:
            import osgeo.gdal as gdal
            import osgeo.osr as osr
            
            # Create output filename
            timestamp = int(time.time())
            output_file = f"orthomosaic_{timestamp}.tif"
            
            # Get image dimensions from poses or points_3d
            if len(poses) > 0 and hasattr(poses[0], 'R'):
                # Use pose information to determine extent
                width, height = self._estimate_dimensions_from_poses(poses)
            elif points_3d is not None:
                width, height = self._estimate_dimensions_from_points(points_3d)
            else:
                width, height = 1024, 768  # Default dimensions
            
            # Create GeoTransform (affine transformation matrix)
            geotransform = self._create_geotransform(poses, points_3d)
            
            # Create COG with overviews
            driver = gdal.GetDriverByName('GTiff')
            
            options = [
                f'COMPRESS={self.config.cog_compression}',
                'TILED=YES',
                'OVERVIEWS=QUADTREE',
                f'TIFFLZW={1 if self.config.cog_compression == "deflate" else 9}',
            ]
            
            # Create the COG file
            dataset = driver.Create(
                output_file, 
                width, 
                height, 
                3,  # RGB channels
                gdal.GDT_Byte,
                options=options
            )
            
            # Set geotransform and projection
            dataset.SetGeoTransform(geotransform)
            
            srs = osr.SpatialReference()
            srs.ImportFromEPSG(int(self.config.coordinate_system.replace('EPSG:', '')))
            dataset.SetProjection(srs.ExportToWkt())
            
            # Write data (placeholder - actual orthomosaic would be written here)
            band1 = dataset.GetRasterBand(1)
            band2 = dataset.GetRasterBand(2)
            band3 = dataset.GetRasterBand(3)
            
            # Create overviews for multi-resolution access
            if self.config.cog_overviews:
                dataset.BuildOverviews(['NEAREST'], [0.5, 0.25, 0.125])
            
            # Add metadata tags for cloud optimization
            dataset.SetMetadataItem('COMPRESSION', 'DEFLATE')
            dataset.SetMetadataItem('TILED', 'YES')
            dataset.SetMetadataItem('IS_COG', 'TRUE')
            
            dataset = None  # Close the dataset
            
        except Exception as e:
            print(f"COG generation failed: {e}")
            return OutputResult(
                file_path="",
                tile_count=0,
                processing_time_ms=(time.time() - start_time) * 1000,
                metadata={'error': str(e)}
            )
        
        processing_time_ms = (time.time() - start_time) * 1000
        
        return OutputResult(
            file_path=output_file,
            tile_count=self._estimate_tile_count(width, height),
            processing_time_ms=processing_time_ms,
            metadata={
                'is_cloud_optimized': True,
                'width': width,
                'height': height,
                'coordinate_system': self.config.coordinate_system,
                'compression': self.config.cog_compression,
            }
        )
    
    def _estimate_dimensions_from_poses(
        self, 
        poses: List[Any]
    ) -> Tuple[int, int]:
        """Estimate image dimensions from camera poses."""
        # Simplified estimation - use average field of view
        fov = 60.0  # degrees (typical for drone cameras)
        
        # Estimate based on typical reconstruction scale
        if len(poses) > 1:
            positions = np.array([p.position if hasattr(p, 'position') else p[:3] for p in poses])
            scale = np.mean(np.linalg.norm(positions[1:] - positions[:-1], axis=1)) * 5
            
            width = int(scale / (np.tan(fov * np.pi / 360) * 2))
            height = int(width * 0.75)  # Typical aspect ratio
        else:
            width, height = 1024, 768
        
        return max(1, width), max(1, height)
    
    def _estimate_dimensions_from_points(
        self, 
        points_3d: np.ndarray
    ) -> Tuple[int, int]:
        """Estimate image dimensions from 3D point cloud."""
        if len(points_3d) == 0:
            return 1024, 768
        
        # Estimate based on point density and coverage area
        points = np.array(points_3d)
        
        # Calculate bounding box
        min_x, max_x = points[:, 0].min(), points[:, 0].max()
        min_y, max_y = points[:, 1].min(), points[:, 1].max()
        min_z, max_z = points[:, 2].min(), points[:, 2].max()
        
        width_meters = max_x - min_x
        height_meters = max_y - min_y
        
        # Assume 0.5m GSD (ground sampling distance)
        gsd = 0.5
        
        pixel_width = int(width_meters / gsd)
        pixel_height = int(height_meters / gsd)
        
        return max(1, pixel_width), max(1, pixel_height)
    
    def _create_geotransform(
        self, 
        poses: List[Any], 
        points_3d: Optional[np.ndarray] = None
    ) -> Tuple[float, ...]:
        """Create GeoTransform for georeferencing."""
        # Simplified geotransform creation
        # In production, use proper coordinate transformations
        
        origin_x = 0.0
        origin_y = 0.0
        pixel_width = 1.0 / 640  # Assume 640m width
        pixel_height = -1.0 / 480  # Negative for north-up coordinates
        
        return (origin_x, pixel_width, 0, origin_y, 0, pixel_height)
    
    def _estimate_tile_count(
        self, 
        width: int, 
        height: int
    ) -> int:
        """Estimate number of tiles in the output."""
        tile_size = self.config.cog_tile_size
        
        num_width_tiles = (width + tile_size - 1) // tile_size
        num_height_tiles = (height + tile_size - 1) // tile_size
        
        return num_width_tiles * num_height_tiles


class TileGenerator(OutputGeneratorBase):
    """Tile-based output generator for web visualization.
    
    Generates tiles optimized for MapLibre GL JS and similar viewers.
    Supports multi-resolution pyramid generation.
    """
    
    def __init__(self, config: Optional[OutputConfig] = None):
        super().__init__(config)
        
        self._tile_cache: Dict[str, np.ndarray] = {}
    
    @property
    def generator_type(self) -> str:
        return "tiles"
    
    def initialize(self) -> bool:
        """Initialize tile generation."""
        try:
            import osgeo.gdal as gdal
            
            gdal.UseExceptions()
            
        except Exception as e:
            print(f"Failed to initialize GDAL for tiles: {e}")
            return False
        
        return True
    
    def generate_tiles(
        self, 
        orthomosaic_data: np.ndarray,
        extent: Tuple[float, float, float, float],
        resolution: float = 0.5
    ) -> List[Dict[str, Any]]:
        """Generate tile-based output for web visualization.
        
        Args:
            orthomosaic_data: Orthomosaic image data (H, W, C)
            extent: Geographic extent in meters (minx, miny, maxx, maxy)
            resolution: Ground sampling distance in meters/pixel
            
        Returns:
            List of tile metadata with file paths and coordinates
        """
        start_time = time.time()
        
        try:
            import osgeo.gdal as gdal
            import osgeo.osr as osr
            
            # Calculate image dimensions
            width_meters = extent[2] - extent[0]
            height_meters = extent[3] - extent[1]
            
            pixel_width = width_meters / orthomosaic_data.shape[1]
            pixel_height = height_meters / orthomosaic_data.shape[0]
            
            # Create output directory structure
            import os
            tile_dir = f"tiles/orthomosaic_{int(time.time())}"
            os.makedirs(tile_dir, exist_ok=True)
            
            tiles = []
            
            # Generate tiles at multiple resolutions (simplified - single resolution for now)
            base_tile_size = 256
            
            for zoom_level in range(0, 10):  # Zoom levels 0-9
                tile_size_at_zoom = int(base_tile_size * (2 ** zoom_level))
                
                # Calculate number of tiles at this zoom level
                num_x_tiles = max(1, int(width_meters / (tile_size_at_zoom * resolution)))
                num_y_tiles = max(1, int(height_meters / (tile_size_at_zoom * resolution)))
                
                for x in range(num_x_tiles):
                    for y in range(num_y_tiles):
                        # Calculate tile extent
                        tile_minx = extent[0] + x * tile_size_at_zoom * resolution
                        tile_miny = extent[1] + y * tile_size_at_zoom * resolution
                        
                        # Generate tile filename
                        zoom_str = str(zoom_level).zfill(2)
                        tile_file = f"{tile_dir}/{zoom_str}_{x:04d}_{y:04d}.png"
                        
                        # Extract and save tile (placeholder - actual extraction would be here)
                        try:
                            import cv2
                        
                            # Calculate tile region in image coordinates
                            img_width = orthomosaic_data.shape[1]
                            img_height = orthomosaic_data.shape[0]
                            
                            x_start = int(x * tile_size_at_zoom / resolution * pixel_width)
                            y_start = int(y * tile_size_at_zoom / resolution * pixel_height)
                            
                            # Extract tile region
                            if 0 <= y_start < img_height and 0 <= x_start < img_width:
                                tile_region = orthomosaic_data[
                                    y_start:y_start + min(tile_size_at_zoom, img_height - y_start),
                                    x_start:x_start + min(tile_size_at_zoom, img_width - x_start)
                                ]
                                
                                # Save as PNG (web-optimized)
                                cv2.imwrite(tile_file, tile_region)
                                
                                tiles.append({
                                    'file_path': tile_file,
                                    'zoom_level': zoom_level,
                                    'x_tile': x,
                                    'y_tile': y,
                                    'extent': (tile_minx, tile_miny, 
                                           tile_minx + tile_size_at_zoom * resolution,
                                           tile_miny + tile_size_at_zoom * resolution),
                                })
                        
                        except Exception as e:
                            print(f"Failed to generate tile {tile_file}: {e}")
                            
        except Exception as e:
            print(f"Tile generation failed: {e}")
        
        processing_time_ms = (time.time() - start_time) * 1000
        
        return tiles


# Convenience functions for quick output generation
def generate_cog(
    poses: List[Any], 
    points_3d: Optional[np.ndarray] = None,
    config: Optional[OutputConfig] = None
) -> OutputResult:
    """Quick COG generation with default settings.
    
    Args:
        poses: Camera poses for georeferencing
        points_3d: Optional 3D point cloud data
        config: Configuration parameters
        
    Returns:
        OutputResult with COG file path and metadata
    """
    generator = COGGenerator(config)
    generator.initialize()
    
    return generator.generate(poses, points_3d)


def generate_tiles(
    orthomosaic_data: np.ndarray,
    extent: Tuple[float, float, float, float],
    resolution: float = 0.5,
    config: Optional[OutputConfig] = None
) -> List[Dict[str, Any]]:
    """Quick tile generation with default settings.
    
    Args:
        orthomosaic_data: Orthomosaic image data (H, W, C)
        extent: Geographic extent in meters
        resolution: Ground sampling distance in meters/pixel
        config: Configuration parameters
        
    Returns:
        List of tile metadata with file paths and coordinates
    """
    generator = TileGenerator(config)
    generator.initialize()
    
    return generator.generate_tiles(orthomosaic_data, extent, resolution)
