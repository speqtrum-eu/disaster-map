"""Health Check Endpoints for LOG Server.

Provides REST API endpoints for monitoring server status:
- GET /health - Basic health check
- GET /status - Detailed system statistics
- POST /process/batch - Submit batch for processing (async)
- GET /outputs - List generated orthomosaics
"""

import os
import json
import time
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

# Import LOG components
from src.integration import SystemIntegrator, PipelineConfig


class HealthCheckHandler:
    """Handles health check and monitoring endpoints."""
    
    def __init__(self):
        self.server = None
        self.config = None
    
    def initialize(self, server: Any) -> None:
        """Initialize handler with LOG server instance."""
        self.server = server
        self.config = PipelineConfig(
            batch_size=32,
            max_parallel_workers=4,
        )
    
    def get_health(self) -> Dict[str, Any]:
        """Return basic health status."""
        return {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'version': '1.0.0',
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Return detailed system statistics."""
        if not self.server:
            return {'error': 'Server not initialized'}
        
        try:
            # Get GPU status
            gpu_available = False
            try:
                from src.vision.gpu import is_gpu_available
                gpu_available = is_gpu_available()
            except Exception:
                pass
            
            # Get output directory status
            output_dir = Path(self.config.output_dir) if hasattr(self, 'config') else Path('./outputs')
            
            return {
                'status': 'running',
                'timestamp': datetime.utcnow().isoformat(),
                'gpu_available': gpu_available,
                'output_directory': str(output_dir),
                'output_exists': output_dir.exists(),
                'server_initialized': self.server.integrator is not None,
            }
        except Exception as e:
            return {'error': str(e)}
    
    def list_outputs(self) -> Dict[str, Any]:
        """List generated orthomosaics."""
        try:
            output_dir = Path('./outputs')
            
            if not output_dir.exists():
                return {
                    'success': True,
                    'count': 0,
                    'files': [],
                }
            
            # Find all orthomosaic files
            files = []
            for ext in ['*.tif', '*.webp']:
                files.extend(output_dir.glob(ext))
            
            # Sort by modification time (newest first)
            files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            return {
                'success': True,
                'count': len(files),
                'files': [
                    {
                        'name': f.name,
                        'size_bytes': f.stat().st_size,
                        'modified': datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                    }
                    for f in files[:10]  # Limit to first 10
                ],
            }
        except Exception as e:
            return {'error': str(e)}


# Global handler instance
health_handler = HealthCheckHandler()
