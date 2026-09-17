#!/usr/bin/env python3
"""Live Orthomosaic Generator (LOG) - Main Entry Point

Production-ready server with:
- Health check endpoints
- Graceful shutdown handling
- Signal processing for production environments
- Logging and metrics integration
"""

import os
import sys
import signal
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import LOG components
from src.integration import (
    SystemIntegrator, PipelineConfig, OutputGenerator,
)
from src.vision.gpu import is_gpu_available


class LOGServer:
    """Main LOG server for orthomosaic processing."""
    
    def __init__(self):
        self.config = self._load_config()
        self.integrator = None
        self.running = False
        self.shutdown_requested = False
        
        # Setup logging (delayed until after config is loaded)
        if os.environ.get('REDIS_URL'):  # Only setup if REDIS_URL is set
            self._setup_logging()
        
        log_info(f"LOG Server starting with config: {self.config}")
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from environment variables."""
        return {
            'redis_url': os.environ.get('REDIS_URL', 'redis://localhost:6379'),
            'output_dir': os.environ.get('OUTPUT_DIR', './outputs'),
            'max_workers': int(os.environ.get('MAX_WORKERS', 4)),
            'batch_size': int(os.environ.get('BATCH_SIZE', 32)),
            'gpu_device': os.environ.get('GPU_DEVICE', '0'),
        }
    
    def _setup_logging(self) -> None:
        """Configure logging for production environment."""
        log_level = getattr(logging, os.environ.get('LOG_LEVEL', 'INFO').upper())
        
        # Create logs directory
        log_dir = Path('./logs')
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Configure handlers
        handlers = [
            logging.StreamHandler(),  # Console output
        ]
        
        # File handler for production
        file_handler = logging.FileHandler(
            f'{log_dir}/server.log',
            mode='a'
        )
        handlers.append(file_handler)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        for handler in handlers:
            handler.setFormatter(formatter)
        
        # Root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        for handler in handlers:
            if handler not in root_logger.handlers:
                root_logger.addHandler(handler)
    
    def initialize(self) -> None:
        """Initialize the LOG server."""
        log_info("Initializing LOG Server...")
        
        # Create output directory
        Path(self.config['output_dir']).mkdir(parents=True, exist_ok=True)
        
        # Initialize system integrator
        config = PipelineConfig(
            batch_size=self.config['batch_size'],
            max_parallel_workers=self.config['max_workers'],
        )
        
        self.integrator = SystemIntegrator(config)
        self.integrator.setup_pipeline()
        
        log_info(f"GPU Available: {is_gpu_available()}")
        log_info(f"Output Directory: {self.config['output_dir']}")
        log_info("LOG Server initialized successfully ✓")
    
    def health_check(self) -> Dict[str, Any]:
        """Return server health status."""
        return {
            'status': 'healthy' if self.running else 'starting',
            'gpu_available': is_gpu_available(),
            'output_dir': str(Path(self.config['output_dir']).exists()),
            'timestamp': time.time(),
        }
    
    def process_batch(
        self, 
        frames: list, 
        geotransform: tuple = None,
        crs: str = "EPSG:4326"
    ) -> Dict[str, Any]:
        """Process a batch of frames and generate orthomosaic."""
        if not self.integrator:
            return {'error': 'Server not initialized'}
        
        try:
            output = self.integrator.process_batch(
                frames=frames,
                geotransform=geotransform or (0.0, 1.0, 0.0, 0.0, 0.0, -1.0),
                crs=crs
            )
            
            return {
                'success': True,
                'output_file': output.main_file,
                'resolution_meters': output.resolution_meters,
                'timestamp': time.time(),
            }
        except Exception as e:
            log_error(f"Batch processing failed: {e}")
            return {'error': str(e)}
    
    def run(self) -> None:
        """Run the LOG server main loop."""
        self.running = True
        self.shutdown_requested = False
        
        # Setup signal handlers for graceful shutdown
        def handle_signal(signum, frame):
            log_info(f"Received signal {signum}, shutting down...")
            self.shutdown_requested = True
        
        signal.signal(signal.SIGTERM, handle_signal)
        signal.signal(signal.SIGINT, handle_signal)
        
        # Initialize server
        self.initialize()
        
        log_info("LOG Server is running. Press Ctrl+C to stop.")
        
        try:
            while not self.shutdown_requested:
                time.sleep(1)  # Main loop heartbeat
                
        except KeyboardInterrupt:
            pass
        
        finally:
            self.cleanup()
    
    def cleanup(self) -> None:
        """Cleanup resources on shutdown."""
        log_info("Cleaning up LOG Server...")
        
        if self.integrator:
            try:
                # Flush any pending operations
                self.integrator._batch_processor.process_batch()
            except Exception as e:
                log_warn(f"Error during cleanup: {e}")
        
        self.running = False
        log_info("LOG Server stopped ✓")


def main():
    """Main entry point for LOG server."""
    # Check for required environment variables
    if not os.environ.get('REDIS_URL'):
        print("ERROR: REDIS_URL environment variable is required")
        print("Usage: export REDIS_URL=redis://localhost:6379")
        sys.exit(1)
    
    # Create and run server
    server = LOGServer()
    server.run()


if __name__ == '__main__':
    main()
