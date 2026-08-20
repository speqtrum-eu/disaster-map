"""
Orthomosaic engine - main processing pipeline
"""

import os
import time
import asyncio
import threading
from typing import Optional, List, Dict, Any, Tuple, Callable
from dataclasses import dataclass, field
from pathlib import Path
from queue import Queue, Empty
from enum import Enum

import cv2
import numpy as np

from ..core.models import (
    Frame,
    OrthomosaicTile,
    ProcessingConfig,
    StreamConfig,
    GPSData,
)
from ..core.utils import get_logger, timestamp_now, ensure_directory
from .stitcher import OrthoStitcher, IncrementalStitcher, create_stitcher, StitchingConfig
from .feature_matcher import FeatureMatcher
from ..streaming.extractors import KeyframeExtractor, FrameBuffer

logger = get_logger("processing.ortho_engine")


class EngineStatus(Enum):
    """Orthomosaic engine status"""
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


@dataclass
class TileGenerator:
    """Generates tiles from orthomosaic"""
    
    tile_size: int = 256
    overlap: int = 20  # percent
    max_zoom: int = 5
    
    def generate_tiles(self, orthomosaic: np.ndarray, timestamp: float) -> List[OrthomosaicTile]:
        """Generate tiles at multiple zoom levels"""
        tiles = []
        
        for zoom in range(self.max_zoom + 1):
n            # Calculate scale
            scale = 1.0 / (2 ** zoom)
            
            # Resize orthomosaic for this zoom level
            if scale != 1.0:
                scaled = cv2.resize(
                    orthomosaic, 
                    None, 
                    fx=scale, 
                    fy=scale, 
                    interpolation=cv2.INTER_AREA
                )
            else:
                scaled = orthomosaic
            
            # Generate tiles
            h, w = scaled.shape[:2]
            for y in range(0, h, self.tile_size):
                for x in range(0, w, self.tile_size):
                    tile_data = scaled[y:y+self.tile_size, x:x+self.tile_size]
                    if tile_data.size > 0:
                        # Pad to tile size if needed
                        if tile_data.shape[0] < self.tile_size or tile_data.shape[1] < self.tile_size:
                            pad_h = max(0, self.tile_size - tile_data.shape[0])
                            pad_w = max(0, self.tile_size - tile_data.shape[1])
                            tile_data = cv2.copyMakeBorder(
                                tile_data, 
                                0, pad_h, 
                                0, pad_w, 
                                cv2.BORDER_CONSTANT, 
                                value=[0, 0, 0]
                            )
                        
                        tile_obj = OrthomosaicTile(
                            x=x // self.tile_size,
                            y=y // self.tile_size,
                            z=zoom,
                            data=tile_data.copy(),
                            timestamp=timestamp,
                        )
                        tiles.append(tile_obj)
        
        return tiles


@dataclass
class Georegistrator:
    """Handles geospatial registration of orthomosaic"""
    
    coordinate_system: str = "EPSG:4326"  # WGS84
    target_system: str = "EPSG:3857"  # Web Mercator
    
    def __init__(self):
        self._gps_points: List[Tuple[float, float, float, float]] = []  # (x, y, lat, lon)
        self._bounds: Optional[Tuple[float, float, float, float]] = None  # (min_x, min_y, max_x, max_y)
        
        # Try to import pyproj for coordinate transformations
        try:
            import pyproj
            self._has_pyproj = True
            self._transformer = pyproj.Transformer.from_crs(
                self.coordinate_system, 
                self.target_system,
                always_xy=True
            )
        except ImportError:
            self._has_pyproj = False
            logger.warning("pyproj not available, geospatial features limited")
    
    def add_gps_point(self, image_x: float, image_y: float, lat: float, lon: float) -> None:
        """Add a GPS point for georegistration"""
        self._gps_points.append((image_x, image_y, lat, lon))
    
    def calculate_transform(self, image_width: int, image_height: int) -> Optional[np.ndarray]:
        """
        Calculate transformation matrix from image to world coordinates
        
        Args:
            image_width: Width of the orthomosaic
            image_height: Height of the orthomosaic
        
        Returns:
            3x3 transformation matrix or None
        """
        if len(self._gps_points) < 2:
            logger.warning("Need at least 2 GPS points for georegistration")
            return None
        
        # Simple affine transformation (would use more sophisticated method in production)
        # For now, return identity matrix
        return np.eye(3)
    
    def image_to_world(self, x: float, y: float, transform: np.ndarray) -> Optional[Tuple[float, float]]:
        """Convert image coordinates to world coordinates"""
        if transform is None:
            return None
        
        # Apply transformation
        coords = np.array([x, y, 1])
        world_coords = np.dot(transform, coords)
        
        return (world_coords[0], world_coords[1])
    
    def world_to_image(self, lon: float, lat: float, transform: np.ndarray) -> Optional[Tuple[float, float]]:
        """Convert world coordinates to image coordinates"""
        if transform is None:
            return None
        
        # Inverse transformation
        inv_transform = np.linalg.inv(transform)
        coords = np.array([lon, lat, 1])
        image_coords = np.dot(inv_transform, coords)
        
        return (image_coords[0], image_coords[1])


class OrthomosaicEngine:
    """
    Main orthomosaic processing engine
    
    This engine:
    1. Receives frames from video streams
    2. Extracts keyframes
    3. Performs feature matching and stitching
    4. Generates orthomosaic tiles
    5. Manages time-series data
    """
    
    def __init__(self, config: Optional[ProcessingConfig] = None):
        self.config = config or ProcessingConfig()
        self.status = EngineStatus.STOPPED
        
        # Processing components
        self._stitcher: Optional[OrthoStitcher] = None
        self._keyframe_extractor = KeyframeExtractor(
            strategy="interval",
            interval=self.config.keyframe_interval
        )
        self._frame_buffer = FrameBuffer(max_size=100)
        self._tile_generator = TileGenerator(
            tile_size=self.config.tile_size,
            overlap=self.config.overlap
        )
        self._georegistrator = Georegistrator()
        
        # Threading
        self._processing_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._frame_queue: Queue = Queue(maxsize=50)
        
        # State
        self._current_orthomosaic: Optional[np.ndarray] = None
        self._current_tiles: List[OrthomosaicTile] = []
        self._last_update_time: float = 0.0
        self._frame_count: int = 0
        self._keyframe_count: int = 0
        
        # Callbacks
        self._update_callbacks: List[Callable[[np.ndarray, float], None]] = []
        self._tile_callbacks: List[Callable[[List[OrthomosaicTile]], None]] = []
        
        # Initialize stitcher
        self._initialize_stitcher()
    
    def _initialize_stitcher(self) -> None:
        """Initialize the stitcher based on config"""
        stitching_config = StitchingConfig.from_processing_config(self.config)
        self._stitcher = create_stitcher(
            self.config.stitching.method if hasattr(self.config, 'stitching') else "incremental",
            stitching_config
        )
    
    def start(self) -> bool:
        """Start the processing engine"""
        if self.status == EngineStatus.RUNNING:
            logger.warning("Engine already running")
            return False
        
        self.status = EngineStatus.RUNNING
        self._stop_event.clear()
        
        # Start processing thread
        self._processing_thread = threading.Thread(
            target=self._processing_loop,
            daemon=True,
            name="OrthoEngine-Processing"
        )
        self._processing_thread.start()
        
        logger.info("Orthomosaic engine started")
        return True
    
    def stop(self) -> None:
        """Stop the processing engine"""
        if self.status == EngineStatus.STOPPED:
            return
        
        self.status = EngineStatus.STOPPED
        self._stop_event.set()
        
        # Wait for thread to finish
        if self._processing_thread:
            self._processing_thread.join(timeout=5.0)
        
        logger.info("Orthomosaic engine stopped")
    
    def pause(self) -> None:
        """Pause the processing engine"""
        if self.status == EngineStatus.RUNNING:
            self.status = EngineStatus.PAUSED
            logger.info("Orthomosaic engine paused")
    
    def resume(self) -> None:
        """Resume the processing engine"""
        if self.status == EngineStatus.PAUSED:
            self.status = EngineStatus.RUNNING
            logger.info("Orthomosaic engine resumed")
    
    def _processing_loop(self) -> None:
        """Main processing loop"""
        logger.info("Processing loop started")
        
        while not self._stop_event.is_set():
            # Check if paused
            if self.status == EngineStatus.PAUSED:
                time.sleep(0.1)
                continue
            
            try:
                # Get frame from queue
                frame = self._frame_queue.get(timeout=0.1)
                
                # Process frame
                self._process_frame(frame)
                
            except Empty:
                # No frames available, continue
                continue
            except Exception as e:
                logger.error(f"Error in processing loop: {e}")
                self.status = EngineStatus.ERROR
        
        logger.info("Processing loop stopped")
    
    def _process_frame(self, frame: Frame) -> None:
        """Process a single frame"""
        self._frame_count += 1
        
        # Store in buffer
        self._frame_buffer.add_frame(frame)
        
        # Extract keyframe
        keyframe = self._keyframe_extractor.extract(frame)
        
        if keyframe is not None:
            self._keyframe_count += 1
            
            # Add GPS data if available
            if frame.gps:
                self._georegistrator.add_gps_point(
                    frame.resolution[0] / 2, 
                    frame.resolution[1] / 2,
                    frame.gps.latitude,
                    frame.gps.longitude
                )
            
            # Add to stitcher
            if self._stitcher:
                success = self._stitcher.add_frame(keyframe)
                if success:
                    # Get updated orthomosaic
                    orthomosaic = self._stitcher.get_orthomosaic()
                    if orthomosaic is not None:
                        self._current_orthomosaic = orthomosaic.copy()
                        self._last_update_time = timestamp_now()
                        
                        # Generate tiles
                        self._current_tiles = self._tile_generator.generate_tiles(
                            orthomosaic, 
                            self._last_update_time
                        )
                        
                        # Notify callbacks
                        for callback in self._update_callbacks:
                            try:
                                callback(orthomosaic, self._last_update_time)
                            except Exception as e:
                                logger.error(f"Error in update callback: {e}")
                        
                        for callback in self._tile_callbacks:
                            try:
                                callback(self._current_tiles)
                            except Exception as e:
                                logger.error(f"Error in tile callback: {e}")
    
    def add_frame(self, frame: Frame) -> bool:
        """Add a frame for processing"""
        try:
            self._frame_queue.put_nowait(frame)
            return True
        except Exception:
            logger.warning("Frame queue full, dropping frame")
            return False
    
    async def add_frame_async(self, frame: Frame) -> bool:
        """Add a frame for processing (async)"""
        return self.add_frame(frame)
    
    def get_orthomosaic(self) -> Optional[np.ndarray]:
        """Get the current orthomosaic"""
        return self._current_orthomosaic
    
    def get_tiles(self, zoom_level: Optional[int] = None) -> List[OrthomosaicTile]:
        """Get orthomosaic tiles at specified zoom level"""
        if zoom_level is not None:
            # Filter by zoom level
            return [t for t in self._current_tiles if t.z == zoom_level]
        return self._current_tiles
    
    def get_stats(self) -> Dict[str, Any]:
        """Get engine statistics"""
        return {
            "status": self.status.value,
            "frame_count": self._frame_count,
            "keyframe_count": self._keyframe_count,
            "last_update_time": self._last_update_time,
            "orthomosaic_size": self._current_orthomosaic.shape if self._current_orthomosaic is not None else None,
            "tile_count": len(self._current_tiles),
            "queue_size": self._frame_queue.qsize(),
        }
    
    def add_update_callback(self, callback: Callable[[np.ndarray, float], None]) -> None:
        """Add callback for orthomosaic updates"""
        self._update_callbacks.append(callback)
    
    def remove_update_callback(self, callback: Callable[[np.ndarray, float], None]) -> None:
        """Remove update callback"""
        if callback in self._update_callbacks:
            self._update_callbacks.remove(callback)
    
    def add_tile_callback(self, callback: Callable[[List[OrthomosaicTile]], None]) -> None:
        """Add callback for tile updates"""
        self._tile_callbacks.append(callback)
    
    def remove_tile_callback(self, callback: Callable[[List[OrthomosaicTile]], None]) -> None:
        """Remove tile callback"""
        if callback in self._tile_callbacks:
            self._tile_callbacks.remove(callback)
    
    def reset(self) -> None:
        """Reset the engine"""
        self.stop()
        
        if self._stitcher:
            self._stitcher.reset()
        
        self._frame_buffer.clear()
        self._current_orthomosaic = None
        self._current_tiles = []
        self._frame_count = 0
        self._keyframe_count = 0
        self._last_update_time = 0.0
        
        # Clear queues
        while not self._frame_queue.empty():
            try:
                self._frame_queue.get_nowait()
            except Empty:
                break
        
        logger.info("Orthomosaic engine reset")
    
    def save_orthomosaic(self, path: str) -> bool:
        """Save current orthomosaic to file"""
        if self._current_orthomosaic is None:
            logger.warning("No orthomosaic to save")
            return False
        
        try:
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            success = cv2.imwrite(str(path), self._current_orthomosaic)
            if success:
                logger.info(f"Saved orthomosaic to {path}")
            else:
                logger.error(f"Failed to save orthomosaic to {path}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error saving orthomosaic: {e}")
            return False
    
    def load_orthomosaic(self, path: str) -> bool:
        """Load orthomosaic from file"""
        try:
            path = Path(path)
            if not path.exists():
                logger.error(f"Orthomosaic file not found: {path}")
                return False
            
            image = cv2.imread(str(path))
            if image is None:
                logger.error(f"Failed to load orthomosaic from {path}")
                return False
            
            self._current_orthomosaic = image
            self._last_update_time = timestamp_now()
            
            # Generate tiles
            self._current_tiles = self._tile_generator.generate_tiles(
                image, 
                self._last_update_time
            )
            
            # Notify callbacks
            for callback in self._update_callbacks:
                try:
                    callback(image, self._last_update_time)
                except Exception as e:
                    logger.error(f"Error in update callback: {e}")
            
            for callback in self._tile_callbacks:
                try:
                    callback(self._current_tiles)
                except Exception as e:
                    logger.error(f"Error in tile callback: {e}")
            
            logger.info(f"Loaded orthomosaic from {path}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading orthomosaic: {e}")
            return False


class MultiStreamOrthoEngine:
    """
    Orthomosaic engine for multiple streams
    
    This engine:
    1. Manages separate stitchers for each stream
    2. Combines orthomosaics from different streams
    3. Handles stream synchronization
    """
    
    def __init__(self, config: Optional[ProcessingConfig] = None):
        self.config = config or ProcessingConfig()
        self._stream_engines: Dict[str, OrthomosaicEngine] = {}
        self._combined_orthomosaic: Optional[np.ndarray] = None
        self._combined_tiles: List[OrthomosaicTile] = []
        
    def add_stream(self, stream_id: str, stream_config: Optional[StreamConfig] = None) -> bool:
        """Add a stream to the engine"""
        if stream_id in self._stream_engines:
            logger.warning(f"Stream {stream_id} already exists")
            return False
        
        # Create stream-specific config
        if stream_config and stream_config.processing:
            engine_config = stream_config.processing
        else:
            engine_config = self.config
        
        # Create engine for this stream
        engine = OrthomosaicEngine(engine_config)
        self._stream_engines[stream_id] = engine
        
        logger.info(f"Added stream {stream_id} to ortho engine")
        return True
    
    def remove_stream(self, stream_id: str) -> bool:
        """Remove a stream from the engine"""
        if stream_id not in self._stream_engines:
            logger.warning(f"Stream {stream_id} not found")
            return False
        
        engine = self._stream_engines[stream_id]
        engine.stop()
        del self._stream_engines[stream_id]
        
        logger.info(f"Removed stream {stream_id} from ortho engine")
        return True
    
    def add_frame(self, stream_id: str, frame: Frame) -> bool:
        """Add a frame from a specific stream"""
        if stream_id not in self._stream_engines:
            logger.warning(f"Stream {stream_id} not found")
            return False
        
        return self._stream_engines[stream_id].add_frame(frame)
    
    def start_all(self) -> None:
        """Start all stream engines"""
        for stream_id, engine in self._stream_engines.items():
            engine.start()
    
    def stop_all(self) -> None:
        """Stop all stream engines"""
        for engine in self._stream_engines.values():
            engine.stop()
    
    def get_stream_orthomosaic(self, stream_id: str) -> Optional[np.ndarray]:
        """Get orthomosaic for a specific stream"""
        if stream_id not in self._stream_engines:
            return None
        return self._stream_engines[stream_id].get_orthomosaic()
    
    def get_combined_orthomosaic(self) -> Optional[np.ndarray]:
        """Get combined orthomosaic from all streams"""
        orthomosaics = []
        for engine in self._stream_engines.values():
            ortho = engine.get_orthomosaic()
            if ortho is not None:
                orthomosaics.append(ortho)
        
        if not orthomosaics:
            return None
        
        # Simple combination: stack vertically (would use geospatial alignment in production)
        return np.vstack(orthomosaics)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get combined statistics"""
        stats = {
            "stream_count": len(self._stream_engines),
            "streams": {}
        }
        
        for stream_id, engine in self._stream_engines.items():
            stats["streams"][stream_id] = engine.get_stats()
        
        return stats
    
    def reset(self) -> None:
        """Reset all engines"""
        for engine in self._stream_engines.values():
            engine.reset()
        
        self._combined_orthomosaic = None
        self._combined_tiles = []
