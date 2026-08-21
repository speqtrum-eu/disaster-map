"""
PyODM integration for orthomosaic generation

This module provides integration with PyODM (Python SDK for OpenDroneMap)
for high-quality orthomosaic generation from collected images.
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

try:
    from pyodm import Node, Project
    from pyodm.models import Project as ODMProject
    PYODM_AVAILABLE = True
except ImportError:
    PYODM_AVAILABLE = False
    Node = None
    Project = None
    ODMProject = None

from ..core.models import Frame, OrthomosaicTile, GPSData, ProcessingConfig
from ..core.utils import get_logger, timestamp_now, ensure_directory

logger = get_logger("processing.pyodm_integration")


class ODMProcessingMode(Enum):
    """PyODM processing modes"""
    FAST = "fast"
    STANDARD = "standard"
    HIGH_QUALITY = "high_quality"
    MAX_QUALITY = "max_quality"


class ODMOutputType(Enum):
    """PyODM output types"""
    ORTHOPHOTO = "orthophoto"
    DSM = "dsm"
    DTM = "dtm"
    POINT_CLOUD = "point_cloud"
    TEXTURED_MODEL = "textured_model"
    ALL = "all"


@dataclass
class ODMConfig:
    """Configuration for PyODM processing"""
    # Connection
    api_token: Optional[str] = None
    host: str = "localhost"
    port: int = 8000
    use_ssl: bool = False
    
    # Processing
    mode: ODMProcessingMode = ODMProcessingMode.STANDARD
    output_types: List[ODMOutputType] = field(default_factory=lambda: [
        ODMOutputType.ORTHOPHOTO,
        ODMOutputType.DSM,
    ])
    
    # Orthophoto settings
    orthophoto_resolution: float = 5.0  # cm/pixel
    orthophoto_crop: int = 0  # 0 = no crop, 1 = crop to extent
    orthophoto_cutline: bool = False
    
    # DSM/DTM settings
    dsm: bool = True
    dtm: bool = False
    
    # Point cloud settings
    point_cloud_classification: bool = False
    point_cloud_filter: str = ""  # "statistical", "radius", etc.
    
    # 3D model settings
    textured_model: bool = False
    mesh_size: int = 200000
    mesh_octree_depth: int = 9
    
    # Advanced settings
    skip_3dmodel: bool = False
    fast_orthophoto: bool = False
    auto_boundary: bool = True
    
    # Performance
    max_concurrency: int = 4
    gpu_mode: bool = False
    
    # Directories
    temp_dir: str = "/tmp/pyodm"
    output_dir: str = "data/pyodm_output"
    
    @classmethod
    def from_processing_config(cls, config: ProcessingConfig) -> "ODMConfig":
        """Create from ProcessingConfig"""
        return cls(
            mode=ODMProcessingMode.STANDARD,
            orthophoto_resolution=config.resolution * 100 if config.resolution else 5.0,
            gpu_mode=config.use_gpu,
        )


@dataclass
class ODMResult:
    """Result from PyODM processing"""
    project_id: str = ""
    project_name: str = ""
    status: str = ""
    orthophoto: Optional[np.ndarray] = None
    dsm: Optional[np.ndarray] = None
    dtm: Optional[np.ndarray] = None
    point_cloud: Optional[np.ndarray] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    processing_time: float = 0.0
    success: bool = False
    error_message: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "project_name": self.project_name,
            "status": self.status,
            "processing_time": self.processing_time,
            "success": self.success,
            "error_message": self.error_message,
            "metadata": self.metadata,
        }


class PyODMClient:
    """
    Client for interacting with PyODM/NodeODM
    
    This client:
    1. Connects to a NodeODM server
    2. Creates projects from image collections
    3. Processes projects with various options
    4. Retrieves results (orthophotos, DEMs, etc.)
    """
    
    def __init__(self, config: Optional[ODMConfig] = None):
        self.config = config or ODMConfig()
        self._node: Optional[Node] = None
        self._connected: bool = False
        self._lock = threading.Lock()
        
        # Initialize connection
        if PYODM_AVAILABLE:
            self._initialize()
    
    def _initialize(self) -> None:
        """Initialize PyODM client"""
        if not PYODM_AVAILABLE:
            logger.warning("PyODM not installed. Install with: pip install pyodm")
            return
        
        try:
            # Create Node instance
            self._node = Node(
                api_token=self.config.api_token,
                host=self.config.host,
                port=self.config.port,
            )
            
            # Test connection
            self._test_connection()
            
        except Exception as e:
            logger.error(f"Error initializing PyODM client: {e}")
            self._node = None
    
    def _test_connection(self) -> bool:
        """Test connection to NodeODM server"""
        if not self._node:
            return False
        
        try:
            # Try to get info
            info = self._node.info()
            logger.info(f"Connected to NodeODM: {info}")
            self._connected = True
            return True
        except Exception as e:
            logger.warning(f"Cannot connect to NodeODM: {e}")
            self._connected = False
            return False
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to NodeODM"""
        return self._connected and self._node is not None
    
    @property
    def is_available(self) -> bool:
        """Check if PyODM is available"""
        return PYODM_AVAILABLE and self.is_connected
    
    def create_project(
        self,
        name: str,
        images: List[Union[str, Path]],
        gps_accuracy: Optional[float] = None,
        **kwargs
    ) -> Optional[Project]:
        """
        Create a new PyODM project
        
        Args:
            name: Project name
            images: List of image paths
            gps_accuracy: GPS accuracy in meters (optional)
            **kwargs: Additional project options
        
        Returns:
            Project object or None if failed
        """
        if not self.is_available:
            logger.error("PyODM not available")
            return None
        
        try:
            # Ensure images exist
            image_paths = [Path(img) for img in images]
            for img_path in image_paths:
                if not img_path.exists():
                    logger.error(f"Image not found: {img_path}")
                    return None
            
            # Create project
            project = self._node.create_project(
                name=name,
                images=[str(p) for p in image_paths],
                **kwargs
            )
            
            logger.info(f"Created PyODM project: {name} ({project.id})")
            return project
            
        except Exception as e:
            logger.error(f"Error creating project: {e}")
            return None
    
    def process_project(
        self,
        project: Project,
        config: Optional[ODMConfig] = None,
        wait: bool = True,
        timeout: Optional[float] = None,
    ) -> Optional[ODMResult]:
        """
        Process a PyODM project
        
        Args:
            project: Project to process
            config: Processing configuration (overrides default)
            wait: Whether to wait for completion
            timeout: Timeout in seconds (None = no timeout)
        
        Returns:
            ODMResult with processing results
        """
        if not self.is_available:
            return ODMResult(
                project_id=project.id,
                project_name=project.name,
                success=False,
                error_message="PyODM not available"
            )
        
        proc_config = config or self.config
        start_time = timestamp_now()
        
        try:
            # Set up processing options
            options = self._get_processing_options(proc_config)
            
            # Start processing
            project.run(**options)
            
            if wait:
                # Wait for completion
                result = self._wait_for_completion(project, timeout)
                if not result.success:
                    return result
                
                # Download results
                result = self._download_results(project, proc_config)
            else:
                # Return immediately
                result = ODMResult(
                    project_id=project.id,
                    project_name=project.name,
                    status="processing",
                    processing_time=timestamp_now() - start_time,
                    success=True,
                )
            
            result.processing_time = timestamp_now() - start_time
            return result
            
        except Exception as e:
            logger.error(f"Error processing project: {e}")
            return ODMResult(
                project_id=project.id,
                project_name=project.name,
                success=False,
                error_message=str(e),
                processing_time=timestamp_now() - start_time,
            )
    
    def _get_processing_options(self, config: ODMConfig) -> Dict[str, Any]:
        """Get processing options from config"""
        options: Dict[str, Any] = {}
        
        # Processing mode
        if config.mode == ODMProcessingMode.FAST:
            options["fast"] = True
        elif config.mode == ODMProcessingMode.HIGH_QUALITY:
            options["high_quality"] = True
        elif config.mode == ODMProcessingMode.MAX_QUALITY:
            options["max_quality"] = True
        
        # Orthophoto settings
        if ODMOutputType.ORTHOPHOTO in config.output_types:
            options["orthophoto_resolution"] = config.orthophoto_resolution
            options["orthophoto_crop"] = config.orthophoto_crop
            options["orthophoto_cutline"] = config.orthophoto_cutline
        
        # DSM/DTM
        if ODMOutputType.DSM in config.output_types:
            options["dsm"] = True
        if ODMOutputType.DTM in config.output_types:
            options["dtm"] = True
        
        # Skip 3D model for faster processing
        if config.skip_3dmodel:
            options["skip_3dmodel"] = True
        
        # Fast orthophoto
        if config.fast_orthophoto:
            options["fast_orthophoto"] = True
        
        # Auto boundary
        if config.auto_boundary:
            options["auto_boundary"] = True
        
        # GPU mode
        if config.gpu_mode:
            options["gpu"] = True
        
        return options
    
    def _wait_for_completion(
        self,
        project: Project,
        timeout: Optional[float] = None
    ) -> ODMResult:
        """Wait for project processing to complete"""
        start_time = timestamp_now()
        
        while True:
            try:
                project.update()
                
                if project.status == "COMPLETED":
                    return ODMResult(
                        project_id=project.id,
                        project_name=project.name,
                        status="completed",
                        success=True,
                        processing_time=timestamp_now() - start_time,
                    )
                
                elif project.status == "FAILED":
                    return ODMResult(
                        project_id=project.id,
                        project_name=project.name,
                        status="failed",
                        success=False,
                        error_message=project.info.get("error", "Unknown error"),
                        processing_time=timestamp_now() - start_time,
                    )
                
                elif project.status == "CANCELLED":
                    return ODMResult(
                        project_id=project.id,
                        project_name=project.name,
                        status="cancelled",
                        success=False,
                        error_message="Processing cancelled",
                        processing_time=timestamp_now() - start_time,
                    )
                
                # Check timeout
                if timeout and (timestamp_now() - start_time) > timeout:
                    return ODMResult(
                        project_id=project.id,
                        project_name=project.name,
                        status="timeout",
                        success=False,
                        error_message="Processing timeout",
                        processing_time=timeout,
                    )
                
                # Wait before checking again
                time.sleep(5.0)
                
            except Exception as e:
                logger.error(f"Error checking project status: {e}")
                return ODMResult(
                    project_id=project.id,
                    project_name=project.name,
                    status="error",
                    success=False,
                    error_message=str(e),
                    processing_time=timestamp_now() - start_time,
                )
    
    def _download_results(
        self,
        project: Project,
        config: ODMConfig
    ) -> ODMResult:
        """Download results from a completed project"""
        result = ODMResult(
            project_id=project.id,
            project_name=project.name,
            status="completed",
            success=True,
        )
        
        try:
            # Get output directory
            output_dir = Path(config.output_dir) / project.id
            ensure_directory(output_dir)
            
            # Download orthophoto
            if ODMOutputType.ORTHOPHOTO in config.output_types:
                ortho_path = self._download_file(project, "orthophoto.tif")
                if ortho_path:
                    result.orthophoto = self._load_geotiff(ortho_path)
                    result.metadata["orthophoto_path"] = str(ortho_path)
            
            # Download DSM
            if ODMOutputType.DSM in config.output_types:
                dsm_path = self._download_file(project, "dsm.tif")
                if dsm_path:
                    result.dsm = self._load_geotiff(dsm_path)
                    result.metadata["dsm_path"] = str(dsm_path)
            
            # Download DTM
            if ODMOutputType.DTM in config.output_types:
                dtm_path = self._download_file(project, "dtm.tif")
                if dtm_path:
                    result.dtm = self._load_geotiff(dtm_path)
                    result.metadata["dtm_path"] = str(dtm_path)
            
            # Download point cloud
            if ODMOutputType.POINT_CLOUD in config.output_types:
                pcl_path = self._download_file(project, "point_cloud.laz")
                if pcl_path:
                    result.point_cloud = self._load_point_cloud(pcl_path)
                    result.metadata["point_cloud_path"] = str(pcl_path)
            
            # Store project info
            result.metadata["project_info"] = project.info
            
        except Exception as e:
            logger.error(f"Error downloading results: {e}")
            result.success = False
            result.error_message = str(e)
        
        return result
    
    def _download_file(self, project: Project, filename: str) -> Optional[Path]:
        """Download a file from the project"""
        if not self._node:
            return None
        
        try:
            output_dir = Path(self.config.output_dir) / project.id
            ensure_directory(output_dir)
            
            file_path = output_dir / filename
            
            # Download the file
            project.download_file(filename, str(file_path))
            
            if file_path.exists():
                logger.info(f"Downloaded {filename} to {file_path}")
                return file_path
            else:
                logger.warning(f"Failed to download {filename}")
                return None
                
        except Exception as e:
            logger.error(f"Error downloading {filename}: {e}")
            return None
    
    def _load_geotiff(self, path: Path) -> Optional[np.ndarray]:
        """Load a GeoTIFF file as numpy array"""
        try:
            # Try to use rasterio
            try:
                import rasterio
                with rasterio.open(path) as src:
                    return src.read(1)  # Read first band
            except ImportError:
                # Fallback to GDAL
                try:
                    from osgeo import gdal
                    ds = gdal.Open(str(path))
                    if ds:
                        band = ds.GetRasterBand(1)
                        return band.ReadAsArray()
                except ImportError:
                    logger.warning("Neither rasterio nor GDAL available for GeoTIFF")
                    return None
        except Exception as e:
            logger.error(f"Error loading GeoTIFF: {e}")
            return None
    
    def _load_point_cloud(self, path: Path) -> Optional[np.ndarray]:
        """Load a point cloud file (LAS/LAZ) as numpy array"""
        try:
            # Try to use laspy
            try:
                import laspy
                with laspy.open(path) as file:
                    # Convert to numpy array
                    points = np.vstack([
                        file.x,
                        file.y,
                        file.z,
                        file.intensity,
                        file.classification,
                    ]).T
                    return points
            except ImportError:
                logger.warning("laspy not available for point cloud loading")
                return None
        except Exception as e:
            logger.error(f"Error loading point cloud: {e}")
            return None
    
    def get_project(self, project_id: str) -> Optional[Project]:
        """Get a project by ID"""
        if not self.is_available:
            return None
        
        try:
            return self._node.get_project(project_id)
        except Exception as e:
            logger.error(f"Error getting project: {e}")
            return None
    
    def list_projects(self) -> List[Project]:
        """List all projects"""
        if not self.is_available:
            return []
        
        try:
            return list(self._node.list_projects())
        except Exception as e:
            logger.error(f"Error listing projects: {e}")
            return []
    
    def delete_project(self, project_id: str) -> bool:
        """Delete a project"""
        if not self.is_available:
            return False
        
        try:
            self._node.delete_project(project_id)
            return True
        except Exception as e:
            logger.error(f"Error deleting project: {e}")
            return False
    
    def get_project_status(self, project_id: str) -> Optional[str]:
        """Get project status"""
        project = self.get_project(project_id)
        if project:
            return project.status
        return None
    
    def cancel_project(self, project_id: str) -> bool:
        """Cancel a running project"""
        if not self.is_available:
            return False
        
        try:
            project = self.get_project(project_id)
            if project:
                project.cancel()
                return True
            return False
        except Exception as e:
            logger.error(f"Error cancelling project: {e}")
            return False


class BatchOrthomosaicGenerator:
    """
    Generates orthomosaics from collected frames using PyODM
    
    This generator:
    1. Collects frames from video streams
    2. Saves them as images
    3. Processes them with PyODM
    4. Returns the orthomosaic
    """
    
    def __init__(self, pyodm_client: Optional[PyODMClient] = None):
        self.pyodm_client = pyodm_client or PyODMClient()
        self._temp_dir = Path("temp/batch_ortho")
        ensure_directory(self._temp_dir)
    
    def generate_from_frames(
        self,
        frames: List[Frame],
        project_name: str = "batch_ortho",
        config: Optional[ODMConfig] = None,
        wait: bool = True,
        cleanup: bool = True,
    ) -> Optional[ODMResult]:
        """
        Generate orthomosaic from a list of frames
        
        Args:
            frames: List of frames to process
            project_name: Name for the PyODM project
            config: PyODM configuration
            wait: Whether to wait for completion
            cleanup: Whether to cleanup temp files
        
        Returns:
            ODMResult with orthomosaic and other outputs
        """
        if not self.pyodm_client.is_available:
            logger.error("PyODM not available")
            return None
        
        if not frames:
            logger.error("No frames provided")
            return None
        
        # Save frames as images
        image_paths = self._save_frames_as_images(frames)
        if not image_paths:
            logger.error("Failed to save frames as images")
            return None
        
        try:
            # Create project
            project = self.pyodm_client.create_project(
                name=project_name,
                images=image_paths,
            )
            
            if not project:
                return None
            
            # Process project
            result = self.pyodm_client.process_project(
                project,
                config=config,
                wait=wait,
            )
            
            # Cleanup temp images if requested
            if cleanup:
                self._cleanup_temp_images(image_paths)
            
            return result
            
        except Exception as e:
            logger.error(f"Error generating orthomosaic: {e}")
            self._cleanup_temp_images(image_paths)
            return None
    
    def _save_frames_as_images(self, frames: List[Frame]) -> List[Path]:
        """Save frames as image files"""
        import cv2
        
        image_paths = []
        
        for i, frame in enumerate(frames):
            if frame.data is None:
                continue
            
            try:
                # Create output path
                output_path = self._temp_dir / f"frame_{i:06d}.jpg"
                
                # Save as JPEG
                success = cv2.imwrite(str(output_path), frame.data, [
                    cv2.IMWRITE_JPEG_QUALITY, 95
                ])
                
                if success and output_path.exists():
                    image_paths.append(output_path)
                    
                    # Save GPS metadata if available
                    if frame.gps:
                        self._save_gps_metadata(output_path, frame.gps)
                else:
                    logger.warning(f"Failed to save frame {i}")
                    
            except Exception as e:
                logger.error(f"Error saving frame {i}: {e}")
        
        return image_paths
    
    def _save_gps_metadata(self, image_path: Path, gps: GPSData) -> None:
        """Save GPS metadata to image file"""
        try:
            from PIL import Image, ImageOps
            import piexif
            
            # Open image
            img = Image.open(image_path)
            
            # Create EXIF data
            exif_dict = {
                "GPS": {
                    piexif.GPSIFD.GPSVersionID: (2, 2, 0, 0),
                    piexif.GPSIFD.GPSLatitudeRef: "N" if gps.latitude >= 0 else "S",
                    piexif.GPSIFD.GPSLatitude: self._deg_to_dms(abs(gps.latitude)),
                    piexif.GPSIFD.GPSLongitudeRef: "E" if gps.longitude >= 0 else "W",
                    piexif.GPSIFD.GPSLongitude: self._deg_to_dms(abs(gps.longitude)),
                    piexif.GPSIFD.GPSAltitudeRef: 0 if gps.altitude >= 0 else 1,
                    piexif.GPSIFD.GPSAltitude: (abs(int(gps.altitude * 100)), 100),
                }
            }
            
            # Convert to bytes
            exif_bytes = piexif.dump(exif_dict)
            
            # Save with EXIF
            img.save(image_path, exif=exif_bytes)
            
        except ImportError:
            logger.warning("PIL or piexif not available for GPS metadata")
        except Exception as e:
            logger.error(f"Error saving GPS metadata: {e}")
    
    def _deg_to_dms(self, degrees: float) -> Tuple[int, int, int]:
        """Convert decimal degrees to DMS (degrees, minutes, seconds)"""
        degrees_int = int(degrees)
        minutes_float = (degrees - degrees_int) * 60
        minutes_int = int(minutes_float)
        seconds = int((minutes_float - minutes_int) * 60 * 100)
        
        return (degrees_int, minutes_int, seconds)
    
    def _cleanup_temp_images(self, image_paths: List[Path]) -> None:
        """Clean up temporary image files"""
        for path in image_paths:
            try:
                if path.exists():
                    path.unlink()
            except Exception as e:
                logger.error(f"Error cleaning up {path}: {e}")


class HybridOrthomosaicEngine:
    """
    Hybrid orthomosaic engine combining real-time and batch processing
    
    This engine:
    1. Uses custom stitcher for real-time updates
    2. Periodically runs PyODM for high-quality orthomosaics
    3. Combines results for best of both worlds
    """
    
    def __init__(
        self,
        realtime_engine: Any,
        pyodm_client: Optional[PyODMClient] = None,
    ):
        self.realtime_engine = realtime_engine
        self.pyodm_client = pyodm_client or PyODMClient()
        self._batch_generator = BatchOrthomosaicGenerator(self.pyodm_client)
        
        # Hybrid settings
        self._batch_interval = 300.0  # 5 minutes
        self._last_batch_time = 0.0
        self._batch_lock = threading.Lock()
        self._running = False
    
    def start(self) -> bool:
        """Start the hybrid engine"""
        if self._running:
            return False
        
        self._running = True
        self._last_batch_time = timestamp_now()
        
        # Start background thread for batch processing
        self._thread = threading.Thread(
            target=self._batch_loop,
            daemon=True,
            name="HybridOrtho-Batch"
        )
        self._thread.start()
        
        return True
    
    def stop(self) -> None:
        """Stop the hybrid engine"""
        self._running = False
        if hasattr(self, '_thread'):
            self._thread.join(timeout=5.0)
    
    def _batch_loop(self) -> None:
        """Background loop for batch processing"""
        while self._running:
            try:
                # Check if it's time for batch processing
                current_time = timestamp_now()
                if (current_time - self._last_batch_time) >= self._batch_interval:
                    self._run_batch_processing()
                    self._last_batch_time = current_time
                
                # Sleep for a while
                time.sleep(60.0)
                
            except Exception as e:
                logger.error(f"Error in batch loop: {e}")
                time.sleep(60.0)
    
    def _run_batch_processing(self) -> None:
        """Run batch processing with PyODM"""
        if not self.pyodm_client.is_available:
            logger.info("PyODM not available, skipping batch processing")
            return
        
        with self._batch_lock:
            try:
                # Get recent frames from realtime engine
                if hasattr(self.realtime_engine, '_frame_buffer'):
                    frames = list(self.realtime_engine._frame_buffer)
                else:
                    frames = []
                
                if not frames:
                    logger.info("No frames for batch processing")
                    return
                
                logger.info(f"Running batch processing with {len(frames)} frames")
                
                # Generate orthomosaic
                result = self._batch_generator.generate_from_frames(
                    frames,
                    project_name=f"hybrid_batch_{timestamp_now()}",
                )
                
                if result and result.success:
                    # Update realtime engine with batch results
                    if hasattr(self.realtime_engine, '_current_orthomosaic'):
                        if result.orthophoto is not None:
                            self.realtime_engine._current_orthomosaic = result.orthophoto
                            logger.info("Updated orthomosaic from batch processing")
                
            except Exception as e:
                logger.error(f"Error in batch processing: {e}")
    
    def set_batch_interval(self, interval: float) -> None:
        """Set batch processing interval (seconds)"""
        self._batch_interval = interval
    
    def trigger_batch_processing(self) -> None:
        """Manually trigger batch processing"""
        self._run_batch_processing()


def create_pyodm_client(config: Optional[ODMConfig] = None) -> PyODMClient:
    """Factory function to create PyODM client"""
    return PyODMClient(config)


def create_batch_generator(pyodm_client: Optional[PyODMClient] = None) -> BatchOrthomosaicGenerator:
    """Factory function to create batch generator"""
    return BatchOrthomosaicGenerator(pyodm_client)


def create_hybrid_engine(realtime_engine: Any, pyodm_client: Optional[PyODMClient] = None) -> HybridOrthomosaicEngine:
    """Factory function to create hybrid engine"""
    return HybridOrthomosaicEngine(realtime_engine, pyodm_client)
