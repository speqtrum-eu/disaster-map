#!/usr/bin/env python3
"""
Main entry point for the Disaster Map application

This application provides:
- Multi-stream video ingestion (RTSP, RTMP, HTTP, WebRTC, File)
- Real-time orthomosaic generation
- Interactive web viewer with pan/zoom and time-axis navigation
- Configurable processing pipelines
"""

import os
import sys
import asyncio
import signal
import argparse
from typing import Optional, List, Dict, Any
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.core.models import (
    StreamConfig,
    StreamType,
    ProcessingConfig,
    Frame,
    VideoStream,
)
from src.core.utils import get_logger, load_config, validate_config, timestamp_now
from src.streaming.ingestors import MultiStreamManager, create_ingestor
from src.streaming.extractors import KeyframeExtractor, FrameBuffer
from src.processing.ortho_engine import OrthomosaicEngine, MultiStreamOrthoEngine
from src.storage.tile_manager import TileManager, TileStorage
from src.storage.time_series_db import TimeSeriesDB

logger = get_logger("disaster_map.main")


class DisasterMapApplication:
    """
    Main application class
    
    Manages all components:
    - Stream ingestion
    - Frame processing
    - Orthomosaic generation
    - Storage
    """
    
    def __init__(self, config_path: str = "config/streams.yaml"):
        self.config_path = config_path
        self._config: Dict[str, Any] = {}
        self._running: bool = False
        
        # Components
        self._stream_manager: Optional[MultiStreamManager] = None
        self._ortho_engine: Optional[MultiStreamOrthoEngine] = None
        self._tile_manager: Optional[TileManager] = None
        self._time_series_db: Optional[TimeSeriesDB] = None
        
        # State
        self._start_time: float = 0.0
        self._frame_count: int = 0
        self._keyframe_count: int = 0
        
        # Load configuration
        self.load_config()
    
    def load_config(self) -> bool:
        """Load application configuration"""
        try:
            self._config = load_config(self.config_path)
            if not validate_config(self._config):
                logger.error("Invalid configuration")
                return False
            
            logger.info(f"Loaded configuration from {self.config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            return False
    
    def initialize(self) -> bool:
        """Initialize all components"""
        logger.info("Initializing Disaster Map application...")
        
        try:
            # Create stream manager
            self._stream_manager = MultiStreamManager()
            
            # Load stream configurations
            streams_config = self._config.get("streams", {})
            processing_config = self._config.get("processing", {})
            storage_config = self._config.get("storage", {})
            
            # Create orthomosaic engine
            proc_config = ProcessingConfig.from_dict(processing_config)
            self._ortho_engine = MultiStreamOrthoEngine(proc_config)
            
            # Create storage components
            tile_storage = TileStorage(
                backend=storage_config.get("tiles", {}).get("backend", "filesystem"),
                path=storage_config.get("tiles", {}).get("path", "data/tiles"),
            )
            self._tile_manager = TileManager(tile_storage)
            
            # Create time-series database
            db_path = storage_config.get("path", "data") + "/time_series.db"
            self._time_series_db = TimeSeriesDB(db_path)
            
            # Initialize streams
            for stream_id, stream_config in streams_config.items():
                if stream_config.get("enabled", True):
                    self._add_stream(stream_id, stream_config)
            
            # Setup callbacks
            self._setup_callbacks()
            
            logger.info("Application initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing application: {e}")
            return False
    
    def _add_stream(self, stream_id: str, config: Dict[str, Any]) -> bool:
        """Add a stream to the manager"""
        try:
            stream_config = StreamConfig.from_dict({"id": stream_id, **config})
            
            # Add to stream manager
            if self._stream_manager:
                success = self._stream_manager.add_stream(stream_config)
                if success:
                    # Add to ortho engine
                    if self._ortho_engine:
                        self._ortho_engine.add_stream(stream_id, stream_config)
                    
                    logger.info(f"Added stream: {stream_id}")
                    return True
                else:
                    logger.error(f"Failed to add stream: {stream_id}")
                    return False
            else:
                logger.error("Stream manager not initialized")
                return False
                
        except Exception as e:
            logger.error(f"Error adding stream {stream_id}: {e}")
            return False
    
    def _setup_callbacks(self) -> None:
        """Setup callbacks between components"""
        if not self._stream_manager or not self._ortho_engine:
            return
        
        # Connect stream manager to ortho engine
        def frame_callback(frame: Frame) -> None:
            self._frame_count += 1
            
            # Add to ortho engine
            if self._ortho_engine:
                self._ortho_engine.add_frame(frame.stream_id, frame)
        
        self._stream_manager.add_frame_callback(frame_callback)
        
        # Connect ortho engine to storage
        if self._tile_manager:
            def tile_callback(tiles: List) -> None:
                self._tile_manager.save_tiles(tiles)
            
            # Would need to connect to individual stream engines
            # This is a simplified version
        
        logger.info("Callbacks setup completed")
    
    def start(self) -> bool:
        """Start the application"""
        if self._running:
            logger.warning("Application already running")
            return False
        
        logger.info("Starting Disaster Map application...")
        
        try:
            # Start stream manager
            if self._stream_manager:
                self._stream_manager.start_all()
            
            # Start ortho engine
            if self._ortho_engine:
                self._ortho_engine.start_all()
            
            self._running = True
            self._start_time = timestamp_now()
            
            logger.info("Application started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error starting application: {e}")
            return False
    
    def stop(self) -> None:
        """Stop the application"""
        if not self._running:
            return
        
        logger.info("Stopping Disaster Map application...")
        
        try:
            # Stop stream manager
            if self._stream_manager:
                self._stream_manager.stop_all()
            
            # Stop ortho engine
            if self._ortho_engine:
                self._ortho_engine.stop_all()
            
            self._running = False
            
            logger.info("Application stopped")
            
        except Exception as e:
            logger.error(f"Error stopping application: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get application statistics"""
        stats = {
            "running": self._running,
            "uptime": timestamp_now() - self._start_time if self._running else 0.0,
            "frame_count": self._frame_count,
            "keyframe_count": self._keyframe_count,
            "start_time": self._start_time,
        }
        
        if self._stream_manager:
            stats["streams"] = {
                s_id: s.to_dict() for s_id, s in self._stream_manager.get_streams().items()
            }
        
        if self._ortho_engine:
            stats["ortho_engine"] = self._ortho_engine.get_stats()
        
        if self._tile_manager:
            stats["tile_manager"] = self._tile_manager.get_stats()
        
        return stats
    
    def get_orthomosaic(self, stream_id: Optional[str] = None) -> Optional[np.ndarray]:
        """Get current orthomosaic"""
        if stream_id:
            if self._ortho_engine:
                return self._ortho_engine.get_stream_orthomosaic(stream_id)
        else:
            if self._ortho_engine:
                return self._ortho_engine.get_combined_orthomosaic()
        return None
    
    def get_tiles(self, stream_id: Optional[str] = None) -> List:
        """Get orthomosaic tiles"""
        if stream_id:
            if self._ortho_engine:
                engine = self._ortho_engine.get_ingestor(stream_id)
                if engine:
                    return engine.get_tiles()
        else:
            if self._tile_manager:
                return self._tile_manager.get_tiles_at_zoom(0)
        return []


# Global application instance
_app: Optional[DisasterMapApplication] = None


def get_app() -> Optional[DisasterMapApplication]:
    """Get the global application instance"""
    return _app


def create_app(config_path: str = "config/streams.yaml") -> DisasterMapApplication:
    """Create and initialize the application"""
    global _app
    
    _app = DisasterMapApplication(config_path)
    if not _app.initialize():
        raise RuntimeError("Failed to initialize application")
    
    return _app


def signal_handler(signum, frame) -> None:
    """Handle termination signals"""
    logger.info(f"Received signal {signum}, shutting down...")
    if _app:
        _app.stop()
    sys.exit(0)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Disaster Map - Multi-Stream Orthomosaic System"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config/streams.yaml",
        help="Path to configuration file"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run in test mode (process test video)"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run without web interface"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    
    args = parser.parse_args()
    
    # Set debug logging if requested
    if args.debug:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Create application
        app = create_app(args.config)
        
        # Start application
        if not app.start():
            logger.error("Failed to start application")
            sys.exit(1)
        
        # Run until interrupted
        if args.test:
            # Run test
            run_test(app)
        else:
            # Main loop
            try:
                while app._running:
                    time.sleep(1.0)
                    
                    # Print stats periodically
                    if app._running:
                        stats = app.get_stats()
                        logger.info(f"Stats: {stats}")
                        
            except KeyboardInterrupt:
                pass
        
        # Cleanup
        app.stop()
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


def run_test(app: DisasterMapApplication) -> None:
    """Run a test with sample data"""
    logger.info("Running in test mode...")
    
    # Create a test stream configuration
    test_config = {
        "type": "file",
        "url": "data/test_video.mp4",
        "enabled": True,
        "name": "Test Video",
        "gps": False,
        "resolution": [1280, 720],
        "fps": 30,
    }
    
    # Add test stream
    app._add_stream("test_stream", test_config)
    
    # Start test stream
    if app._stream_manager:
        app._stream_manager.start_stream("test_stream")
    
    # Run for 30 seconds
    start_time = timestamp_now()
    while app._running and (timestamp_now() - start_time) < 30.0:
        time.sleep(1.0)
        
        # Print stats
        stats = app.get_stats()
        logger.info(f"Test stats: {stats}")
    
    logger.info("Test completed")


if __name__ == "__main__":
    import time
    main()
