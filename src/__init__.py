"""
Disaster Map - Multi-Stream Orthomosaic System

A comprehensive application for gathering video streams from drones and body cameras,
generating navigable orthomosaic maps with time-axis scrolling.
"""

__version__ = "1.0.0"
__author__ = "Speqtrum EU"
__license__ = "MIT"

# Submodule imports
from .core import models, utils
from .streaming import ingestors, extractors
from .processing import stitcher, ortho_engine
from .storage import tile_manager, time_series_db
from .api import server, websocket

__all__ = [
    "models",
    "utils",
    "ingestors",
    "extractors",
    "stitcher",
    "ortho_engine",
    "tile_manager",
    "time_series_db",
    "server",
    "websocket",
]
