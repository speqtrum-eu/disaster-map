"""
Hybrid processing pipeline combining real-time and batch processing

This module provides a comprehensive processing pipeline that:
1. Processes frames in real-time for quick updates
2. Runs batch processing (PyODM) for high-quality results
3. Combines results for best of both worlds
4. Manages multi-stream synchronization
5. Handles advanced georegistration
"""

import os
import time
import threading
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum

import numpy as np
import cv2

from ..core.models import Frame, OrthomosaicTile, GPSData, ProcessingConfig, StreamConfig
from ..core.utils import get_logger, timestamp_now, ensure_directory
from .ortho_engine import OrthomosaicEngine, MultiStreamOrthoEngine
from .stitcher import OrthoStitcher, create_stitcher, StitchingConfig
from .multi_stream_sync import StreamSynchronizer, SyncGroup, SyncConfig
from .pyodm_integration import PyODMClient, ODMConfig, BatchOrthomosaicGenerator
from .dem_generator import DEMEngine, DEMConfig
from .point_cloud import PointCloudGenerator, PointCloud
from .advanced_georegistration import GeoregistrationEngine, GeoregistrationConfig

logger = get_logger("processing.hybrid_pipeline")


class PipelineMode(Enum):
    """Processing pipeline modes"""
    REALTIME_ONLY = "realtime_only"
    BATCH_ONLY = "batch_only"
    HYBRID = "hybrid"


class PipelineStatus(Enum):
    """Pipeline status"""
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


@dataclass
class HybridPipelineConfig:
    """Configuration for hybrid processing pipeline"""
    # Mode
    mode: PipelineMode = PipelineMode.HYBRID
    
    # Real-time settings
    realtime_enabled: bool = True
    keyframe_interval: float = 1.0  # seconds
    stitching_method: str = "incremental"
    
    # Batch settings
    batch_enabled: bool = True
    batch_interval: float = 300.0  # 5 minutes
    batch_min_frames: int = 20
    
    # PyODM settings
    pyodm_enabled: bool = False
    pyodm_host: str = "localhost"
    pyodm_port: int = 8000
    pyodm_api_token: Optional[str] = None
    
    # DEM settings
    dem_enabled: bool = False
    dem_method: str = "stereo_sgbm"
    
    # Point cloud settings
    point_cloud_enabled: bool = False
    
    # Multi-stream settings
    multi_stream_enabled: bool = False
    sync_method: str = "hybrid"
    
    # Georegistration settings
    georegistration_enabled: bool = False
    georegistration_method: str = "homography"
    
    # Quality settings
    use_gpu: bool = False
    resolution: float = 0.1  # meters per pixel
    
    # Directories
    temp_dir: str = "temp/hybrid_pipeline"
    output_dir: str = "data/hybrid_pipeline"
    
    @classmethod
    def from_processing_config(cls, config: ProcessingConfig) -> "HybridPipelineConfig":
        """Create from ProcessingConfig"""
        return cls(
            keyframe_interval=config.keyframe_interval if hasattr(config, 'keyframe_interval') else 1.0,
            use_gpu=config.use_gpu,
            resolution=config.resolution if config.resolution else 0.1,
        )


@dataclass
class PipelineResult:
    """Result from pipeline processing"""
    orthomosaic: Optional[np.ndarray] = None
    tiles: List[OrthomosaicTile] = field(default_factory=list)
    dem: Optional[np.ndarray] = None
    point_cloud: Optional[PointCloud] = None
    sync_groups: List[SyncGroup] = field(default_factory=list)
    processing_time: float = 0.0
    success: bool = False
    error: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "has_orthomosaic": self.orthomosaic is not None,
            "has_dem": self.dem is not None,
            "has_point_cloud": self.point_cloud is not None,
            "tile_count": len(self.tiles),
            "sync_group_count": len(self.sync_groups),
            "processing_time": self.processing_time,
            "success": self.success,
            "error": self.error,
            "metadata": self.metadata,
        }


class HybridProcessingPipeline:
    """
    Hybrid processing pipeline for orthomosaic generation
    
    This pipeline:
    1. Processes frames in real-time using incremental stitching
    2. Periodically runs batch processing (PyODM) for high-quality results
    3. Generates DEM and point clouds
    4. Handles multi-stream synchronization
    5. Performs advanced georegistration
    """
    
    def __init__(self, config: Optional[HybridPipelineConfig] = None):
        self.config = config or HybridPipelineConfig()
        self.status = PipelineStatus.STOPPED
        
        # Initialize components
        self._realtime_engine: Optional[OrthomosaicEngine] = None
        self._multi_stream_engine: Optional[MultiStreamOrthoEngine] = None
        self._batch_generator: Optional[BatchOrthomosaicGenerator] = None
        self._dem_engine: Optional[DEMEngine] = None
        self._point_cloud_generator: Optional[PointCloudGenerator] = None
        self._synchronizer: Optional[StreamSynchronizer] = None
        self._georegistrator: Optional[GeoregistrationEngine] = None
        
        # State
        self._frame_buffer: Dict[str, List[Frame]] = {}
        self._last_batch_time: float = 0.0
        self._last_realtime_update: float = 0.0
        
        # Threading
        self._stop_event = threading.Event()
        self._processing_thread: Optional[threading.Thread] = None
        
        # Callbacks
        self._result_callbacks: List[Callable[[PipelineResult], None]] = []
        
        # Initialize based on config
        self._initialize_components()
    
    def _initialize_components(self) -> None:
        """Initialize processing components based on config"""
        # Create processing config
        processing_config = ProcessingConfig(
            keyframe_interval=self.config.keyframe_interval,
            use_gpu=self.config.use_gpu,
            resolution=self.config.resolution,
        )
        
        # Real-time engine
        if self.config.realtime_enabled:
            self._realtime_engine = OrthomosaicEngine(processing_config)
        
        # Multi-stream engine
        if self.config.multi_stream_enabled:
            self._multi_stream_engine = MultiStreamOrthoEngine(processing_config)
        
        # Batch generator (PyODM)
        if self.config.batch_enabled and self.config.pyodm_enabled:
            try:
                pyodm_config = ODMConfig(
                    host=self.config.pyodm_host,
                    port=self.config.pyodm_port,
                    api_token=self.config.pyodm_api_token,
                    gpu_mode=self.config.use_gpu,
                )
                pyodm_client = PyODMClient(pyodm_config)
                if pyodm_client.is_available:
                    self._batch_generator = BatchOrthomosaicGenerator(pyodm_client)
                    logger.info("PyODM batch generator initialized")
                else:
                    logger.warning("PyODM not available, batch processing disabled")
            except Exception as e:
                logger.warning(f"Failed to initialize PyODM: {e}")
        
        # DEM engine
        if self.config.dem_enabled:
            dem_config = DEMConfig(
                method=self.config.dem_method,
                resolution=self.config.resolution,
            )
            self._dem_engine = DEMEngine(dem_config)
        
        # Point cloud generator
        if self.config.point_cloud_enabled:
            self._point_cloud_generator = PointCloudGenerator()
        
        # Synchronizer
        if self.config.multi_stream_enabled:
            sync_config = SyncConfig(
                method=self.config.sync_method,
                frame_buffer_size=100,
            )
            self._synchronizer = StreamSynchronizer(sync_config)
        
        # Georegistrator
        if self.config.georegistration_enabled:
            geo_config = GeoregistrationConfig(
                warping_method=self.config.georegistration_method,
            )
            self._georegistrator = GeoregistrationEngine(geo_config)
    
    def start(self) -> bool:
        """Start the processing pipeline"""
        if self.status == PipelineStatus.RUNNING:
            logger.warning("Pipeline already running")
            return False
        
        self.status = PipelineStatus.RUNNING
        self._stop_event.clear()
        self._last_batch_time = timestamp_now()
        
        # Start real-time engine
        if self._realtime_engine:
            self._realtime_engine.start()
        
        # Start multi-stream engine
        if self._multi_stream_engine:
            self._multi_stream_engine.start_all()
        
        # Start processing thread
        self._processing_thread = threading.Thread(
            target=self._processing_loop,
            daemon=True,
            name="HybridPipeline-Processing"
        )
        self._processing_thread.start()
        
        logger.info("Hybrid processing pipeline started")
        return True
    
    def stop(self) -> None:
        """Stop the processing pipeline"""
        if self.status == PipelineStatus.STOPPED:
            return
        
        self.status = PipelineStatus.STOPPED
        self._stop_event.set()
        
        # Stop real-time engine
        if self._realtime_engine:
            self._realtime_engine.stop()
        
        # Stop multi-stream engine
        if self._multi_stream_engine:
            self._multi_stream_engine.stop_all()
        
        # Wait for thread to finish
        if self._processing_thread:
            self._processing_thread.join(timeout=5.0)
        
        logger.info("Hybrid processing pipeline stopped")
    
    def pause(self) -> None:
        """Pause the processing pipeline"""
        if self.status == PipelineStatus.RUNNING:
            self.status = PipelineStatus.PAUSED
            
            if self._realtime_engine:
                self._realtime_engine.pause()
            
            if self._multi_stream_engine:
                for stream_id in self._multi_stream_engine._stream_engines:
                    self._multi_stream_engine._stream_engines[stream_id].pause()
            
            logger.info("Hybrid processing pipeline paused")
    
    def resume(self) -> None:
        """Resume the processing pipeline"""
        if self.status == PipelineStatus.PAUSED:
            self.status = PipelineStatus.RUNNING
            
            if self._realtime_engine:
                self._realtime_engine.resume()
            
            if self._multi_stream_engine:
                for stream_id in self._multi_stream_engine._stream_engines:
                    self._multi_stream_engine._stream_engines[stream_id].resume()
            
            logger.info("Hybrid processing pipeline resumed")
    
    def _processing_loop(self) -> None:
        """Main processing loop"""
        logger.info("Processing loop started")
        
        while not self._stop_event.is_set():
            # Check if paused
            if self.status == PipelineStatus.PAUSED:
                time.sleep(0.1)
                continue
            
            try:
                # Check if it's time for batch processing
                current_time = timestamp_now()
                if self._should_run_batch():
                    self._run_batch_processing()
                    self._last_batch_time = current_time
                
                # Check for sync groups
                if self._synchronizer:
                    self._check_sync_groups()
                
                # Sleep for a while
                time.sleep(1.0)
                
            except Exception as e:
                logger.error(f"Error in processing loop: {e}")
                self.status = PipelineStatus.ERROR
        
        logger.info("Processing loop stopped")
    
    def _should_run_batch(self) -> bool:
        """Check if batch processing should be run"""
        if not self.config.batch_enabled:
            return False
        
        if not self._batch_generator:
            return False
        
        current_time = timestamp_now()
        time_since_last = current_time - self._last_batch_time
        
        # Check time interval
        if time_since_last < self.config.batch_interval:
            return False
        
        # Check minimum frames
        total_frames = sum(len(frames) for frames in self._frame_buffer.values())
        if total_frames < self.config.batch_min_frames:
            return False
        
        return True
    
    def _run_batch_processing(self) -> None:
        """Run batch processing"""
        if not self._batch_generator:
            return
        
        try:
            # Collect all frames
            all_frames = []
            for frames in self._frame_buffer.values():
                all_frames.extend(frames)
            
            if not all_frames:
                return
            
            logger.info(f"Running batch processing with {len(all_frames)} frames")
            
            # Generate orthomosaic with PyODM
            result = self._batch_generator.generate_from_frames(
                all_frames,
                project_name=f"batch_{timestamp_now()}",
                wait=True,
            )
            
            if result and result.success:
                # Update real-time engine with batch results
                if self._realtime_engine and result.orthophoto is not None:
                    self._realtime_engine._current_orthomosaic = result.orthophoto
                    self._last_realtime_update = timestamp_now()
                    
                    # Generate tiles
                    tile_gen = self._realtime_engine._tile_generator
                    self._realtime_engine._current_tiles = tile_gen.generate_tiles(
                        result.orthophoto,
                        self._last_realtime_update,
                    )
                
                # Generate DEM if enabled
                if self.config.dem_enabled and self._dem_engine:
                    dem_result = self._dem_engine.generate(
                        self.config.dem_method,
                        frames=all_frames,
                    )
                    if dem_result and dem_result.success:
                        # Store DEM
                        pass
                
                # Generate point cloud if enabled
                if self.config.point_cloud_enabled and self._point_cloud_generator:
                    pcl = self._point_cloud_generator.generate_from_frames(
                        all_frames,
                        method="stereo",
                    )
                    if pcl:
                        # Store point cloud
                        pass
                
                # Notify callbacks
                self._notify_result_callbacks(result)
                
            logger.info("Batch processing completed")
            
        except Exception as e:
            logger.error(f"Error in batch processing: {e}")
    
    def _check_sync_groups(self) -> None:
        """Check for synchronization groups"""
        if not self._synchronizer:
            return
        
        try:
            groups = self._synchronizer.find_sync_groups()
            
            for group in groups:
                logger.info(f"Found sync group with {len(group.frames)} streams")
                
                # Process synchronized frames
                self._process_sync_group(group)
                
        except Exception as e:
            logger.error(f"Error checking sync groups: {e}")
    
    def _process_sync_group(self, group: SyncGroup) -> None:
        """Process a synchronization group"""
        # For now, just add frames to real-time engine
        if self._realtime_engine:
            for stream_id, frame in group.frames.items():
                self._realtime_engine.add_frame(frame)
        
        # If multi-stream enabled
        if self._multi_stream_engine:
            for stream_id, frame in group.frames.items():
                self._multi_stream_engine.add_frame(stream_id, frame)
    
    def add_frame(self, frame: Frame, stream_id: str = "default") -> bool:
        """Add a frame to the pipeline"""
        try:
            # Store in buffer
            if stream_id not in self._frame_buffer:
                self._frame_buffer[stream_id] = []
            
            self._frame_buffer[stream_id].append(frame)
            
            # Limit buffer size
            if len(self._frame_buffer[stream_id]) > 1000:
                self._frame_buffer[stream_id] = self._frame_buffer[stream_id][-1000:]
            
            # Add to real-time engine
            if self._realtime_engine:
                self._realtime_engine.add_frame(frame)
            
            # Add to multi-stream engine
            if self._multi_stream_engine:
                self._multi_stream_engine.add_frame(stream_id, frame)
            
            # Add to synchronizer
            if self._synchronizer:
                self._synchronizer.add_frame(stream_id, frame)
            
            return True
            
        except Exception as e:
            logger.error(f"Error adding frame: {e}")
            return False
    
    async def add_frame_async(self, frame: Frame, stream_id: str = "default") -> bool:
        """Add a frame to the pipeline (async)"""
        return self.add_frame(frame, stream_id)
    
    def add_stream(self, stream_id: str, config: Optional[StreamConfig] = None) -> bool:
        """Add a stream to the pipeline"""
        if self._multi_stream_engine:
            return self._multi_stream_engine.add_stream(stream_id, config)
        
        if self._synchronizer:
            return self._synchronizer.add_stream(stream_id, config)
        
        return False
    
    def remove_stream(self, stream_id: str) -> bool:
        """Remove a stream from the pipeline"""
        if self._multi_stream_engine:
            self._multi_stream_engine.remove_stream(stream_id)
        
        if self._synchronizer:
            self._synchronizer.remove_stream(stream_id)
        
        if stream_id in self._frame_buffer:
            del self._frame_buffer[stream_id]
        
        return True
    
    def get_orthomosaic(self, stream_id: Optional[str] = None) -> Optional[np.ndarray]:
        """Get the current orthomosaic"""
        if stream_id and self._multi_stream_engine:
            return self._multi_stream_engine.get_stream_orthomosaic(stream_id)
        
        if self._realtime_engine:
            return self._realtime_engine.get_orthomosaic()
        
        return None
    
    def get_tiles(self, zoom_level: Optional[int] = None) -> List[OrthomosaicTile]:
        """Get orthomosaic tiles"""
        if self._realtime_engine:
            return self._realtime_engine.get_tiles(zoom_level)
        
        return []
    
    def get_dem(self) -> Optional[np.ndarray]:
        """Get the current DEM"""
        if self._dem_engine:
            # For now, return the latest DEM
            dem_list = self._dem_engine.get_dem_list()
            if dem_list:
                return self._dem_engine.load_dem(dem_list[-1])
        
        return None
    
    def get_point_cloud(self) -> Optional[PointCloud]:
        """Get the current point cloud"""
        # For now, point cloud is not stored, so return None
        return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pipeline statistics"""
        stats = {
            "status": self.status.value,
            "mode": self.config.mode.value,
            "frame_count": sum(len(frames) for frames in self._frame_buffer.values()),
            "stream_count": len(self._frame_buffer),
            "last_batch_time": self._last_batch_time,
            "last_realtime_update": self._last_realtime_update,
            "realtime_enabled": self.config.realtime_enabled,
            "batch_enabled": self.config.batch_enabled,
            "pyodm_enabled": self.config.pyodm_enabled and self._batch_generator is not None,
            "dem_enabled": self.config.dem_enabled,
            "point_cloud_enabled": self.config.point_cloud_enabled,
        }
        
        if self._realtime_engine:
            stats["realtime_stats"] = self._realtime_engine.get_stats()
        
        if self._multi_stream_engine:
            stats["multi_stream_stats"] = self._multi_stream_engine.get_stats()
        
        if self._synchronizer:
            stats["sync_stats"] = self._synchronizer.get_stats()
        
        return stats
    
    def add_result_callback(self, callback: Callable[[PipelineResult], None]) -> None:
        """Add callback for pipeline results"""
        self._result_callbacks.append(callback)
    
    def remove_result_callback(self, callback: Callable[[PipelineResult], None]) -> None:
        """Remove result callback"""
        if callback in self._result_callbacks:
            self._result_callbacks.remove(callback)
    
    def _notify_result_callbacks(self, result: Any) -> None:
        """Notify all result callbacks"""
        # Convert result to PipelineResult
        pipeline_result = self._convert_to_pipeline_result(result)
        
        for callback in self._result_callbacks:
            try:
                callback(pipeline_result)
            except Exception as e:
                logger.error(f"Error in result callback: {e}")
    
    def _convert_to_pipeline_result(self, result: Any) -> PipelineResult:
        """Convert various result types to PipelineResult"""
        pipeline_result = PipelineResult()
        
        if hasattr(result, 'orthophoto'):
            pipeline_result.orthomosaic = result.orthophoto
        
        if hasattr(result, 'dsm'):
            pipeline_result.dem = result.dsm
        
        pipeline_result.success = getattr(result, 'success', False)
        pipeline_result.error = getattr(result, 'error_message', '') or getattr(result, 'error', '')
        pipeline_result.processing_time = getattr(result, 'processing_time', 0.0)
        
        return pipeline_result
    
    def reset(self) -> None:
        """Reset the pipeline"""
        self.stop()
        
        self._frame_buffer.clear()
        self._last_batch_time = 0.0
        self._last_realtime_update = 0.0
        
        if self._realtime_engine:
            self._realtime_engine.reset()
        
        if self._multi_stream_engine:
            self._multi_stream_engine.reset()
        
        if self._synchronizer:
            self._synchronizer.reset()
        
        logger.info("Hybrid processing pipeline reset")
    
    def trigger_batch_processing(self) -> None:
        """Manually trigger batch processing"""
        if self._should_run_batch():
            self._run_batch_processing()
        else:
            logger.info("Batch processing conditions not met")
    
    def save_orthomosaic(self, path: str) -> bool:
        """Save current orthomosaic to file"""
        ortho = self.get_orthomosaic()
        if ortho is None:
            logger.warning("No orthomosaic to save")
            return False
        
        try:
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            success = cv2.imwrite(str(path), ortho)
            if success:
                logger.info(f"Saved orthomosaic to {path}")
            else:
                logger.error(f"Failed to save orthomosaic to {path}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error saving orthomosaic: {e}")
            return False


def create_hybrid_pipeline(config: Optional[HybridPipelineConfig] = None) -> HybridProcessingPipeline:
    """Factory function to create hybrid processing pipeline"""
    return HybridProcessingPipeline(config)


class PipelineManager:
    """
    Manager for multiple processing pipelines
    
    This manager:
    1. Creates and manages multiple pipelines
    2. Routes frames to appropriate pipelines
    3. Provides centralized control
    """
    
    def __init__(self):
        self._pipelines: Dict[str, HybridProcessingPipeline] = {}
        self._default_pipeline: Optional[HybridProcessingPipeline] = None
    
    def create_pipeline(
        self,
        name: str,
        config: Optional[HybridPipelineConfig] = None,
        is_default: bool = False,
    ) -> HybridProcessingPipeline:
        """Create a new processing pipeline"""
        pipeline = HybridProcessingPipeline(config)
        self._pipelines[name] = pipeline
        
        if is_default or self._default_pipeline is None:
            self._default_pipeline = pipeline
        
        return pipeline
    
    def get_pipeline(self, name: str) -> Optional[HybridProcessingPipeline]:
        """Get a pipeline by name"""
        return self._pipelines.get(name)
    
    def get_default_pipeline(self) -> Optional[HybridProcessingPipeline]:
        """Get the default pipeline"""
        return self._default_pipeline
    
    def add_frame(
        self,
        frame: Frame,
        pipeline_name: Optional[str] = None,
        stream_id: str = "default",
    ) -> bool:
        """Add a frame to a pipeline"""
        if pipeline_name:
            pipeline = self._pipelines.get(pipeline_name)
        else:
            pipeline = self._default_pipeline
        
        if pipeline is None:
            logger.warning(f"Pipeline {pipeline_name or 'default'} not found")
            return False
        
        return pipeline.add_frame(frame, stream_id)
    
    def start_all(self) -> None:
        """Start all pipelines"""
        for pipeline in self._pipelines.values():
            pipeline.start()
    
    def stop_all(self) -> None:
        """Stop all pipelines"""
        for pipeline in self._pipelines.values():
            pipeline.stop()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics for all pipelines"""
        stats = {
            "pipeline_count": len(self._pipelines),
            "pipelines": {}
        }
        
        for name, pipeline in self._pipelines.items():
            stats["pipelines"][name] = pipeline.get_stats()
        
        return stats
    
    def remove_pipeline(self, name: str) -> bool:
        """Remove a pipeline"""
        if name in self._pipelines:
            pipeline = self._pipelines[name]
            pipeline.stop()
            del self._pipelines[name]
            
            if self._default_pipeline == pipeline:
                self._default_pipeline = None
            
            return True
        
        return False
