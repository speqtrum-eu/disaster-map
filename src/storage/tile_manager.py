"""
Tile storage and management for orthomosaic
"""

import os
import json
import time
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
import threading

import numpy as np

from ..core.models import OrthomosaicTile
from ..core.utils import get_logger, ensure_directory

logger = get_logger("storage.tile_manager")


@dataclass
class TileStorage:
    """Stores orthomosaic tiles"""
    
    backend: str = "filesystem"  # filesystem, sqlite, s3
    path: str = "data/tiles"
    max_tiles: int = 10000
    quality: int = 85  # JPEG quality (0-100)
    
    def __post_init__(self):
        self._path = Path(self.path)
        ensure_directory(self.path)
        self._lock = threading.Lock()
    
    def save_tile(self, tile: OrthomosaicTile) -> bool:
        """Save a tile to storage"""
        if self.backend == "filesystem":
            return self._save_filesystem(tile)
        else:
            logger.warning(f"Backend {self.backend} not implemented")
            return False
    
    def _save_filesystem(self, tile: OrthomosaicTile) -> bool:
        """Save tile to filesystem"""
        try:
            # Create directory structure: path/z/x/y.png
            tile_dir = self._path / str(tile.z) / str(tile.x)
            ensure_directory(tile_dir)
            
            # Save as PNG
            tile_path = tile_dir / f"{tile.y}.png"
            success = cv2.imwrite(str(tile_path), tile.data, [cv2.IMWRITE_PNG_COMPRESSION, 9])
            
            if success:
                logger.debug(f"Saved tile {tile.z}/{tile.x}/{tile.y} to {tile_path}")
            else:
                logger.error(f"Failed to save tile {tile.z}/{tile.x}/{tile.y}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error saving tile: {e}")
            return False
    
    def load_tile(self, z: int, x: int, y: int) -> Optional[OrthomosaicTile]:
        """Load a tile from storage"""
        if self.backend == "filesystem":
            return self._load_filesystem(z, x, y)
        else:
            logger.warning(f"Backend {self.backend} not implemented")
            return None
    
    def _load_filesystem(self, z: int, x: int, y: int) -> Optional[OrthomosaicTile]:
        """Load tile from filesystem"""
        try:
            tile_path = self._path / str(z) / str(x) / f"{y}.png"
            if not tile_path.exists():
                return None
            
            image = cv2.imread(str(tile_path))
            if image is None:
                return None
            
            return OrthomosaicTile(
                x=x,
                y=y,
                z=z,
                data=image,
            )
            
        except Exception as e:
            logger.error(f"Error loading tile {z}/{x}/{y}: {e}")
            return None
    
    def delete_tile(self, z: int, x: int, y: int) -> bool:
        """Delete a tile from storage"""
        if self.backend == "filesystem":
            return self._delete_filesystem(z, x, y)
        else:
            logger.warning(f"Backend {self.backend} not implemented")
            return False
    
    def _delete_filesystem(self, z: int, x: int, y: int) -> bool:
        """Delete tile from filesystem"""
        try:
            tile_path = self._path / str(z) / str(x) / f"{y}.png"
            if tile_path.exists():
                tile_path.unlink()
                logger.debug(f"Deleted tile {z}/{x}/{y}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error deleting tile {z}/{x}/{y}: {e}")
            return False
    
    def list_tiles(self, z: Optional[int] = None) -> List[Dict[str, Any]]:
        """List all tiles"""
        if self.backend == "filesystem":
            return self._list_filesystem(z)
        else:
            logger.warning(f"Backend {self.backend} not implemented")
            return []
    
    def _list_filesystem(self, z: Optional[int] = None) -> List[Dict[str, Any]]:
        """List tiles from filesystem"""
        tiles = []
        
        if z is not None:
            # List specific zoom level
            zoom_path = self._path / str(z)
            if zoom_path.exists():
                for x_dir in zoom_path.iterdir():
                    if x_dir.is_dir():
                        for tile_file in x_dir.glob("*.png"):
                            y = int(tile_file.stem)
                            tiles.append({
                                "z": z,
                                "x": int(x_dir.name),
                                "y": y,
                                "path": str(tile_file.relative_to(self._path))
                            })
        else:
            # List all zoom levels
            for zoom_path in self._path.iterdir():
                if zoom_path.is_dir():
                    try:
                        z = int(zoom_path.name)
                        for x_dir in zoom_path.iterdir():
                            if x_dir.is_dir():
                                for tile_file in x_dir.glob("*.png"):
                                    y = int(tile_file.stem)
                                    tiles.append({
                                        "z": z,
                                        "x": int(x_dir.name),
                                        "y": y,
                                        "path": str(tile_file.relative_to(self._path))
                                    })
                    except ValueError:
                        continue
        
        return tiles


class TileManager:
    """
    Manages orthomosaic tiles for efficient access and caching
    """
    
    def __init__(self, storage: Optional[TileStorage] = None):
        self.storage = storage or TileStorage()
        self._cache: Dict[Tuple[int, int, int], OrthomosaicTile] = {}
        self._cache_size: int = 1000
        self._lock = threading.Lock()
        self._access_order: List[Tuple[int, int, int]] = []
    
    def save_tile(self, tile: OrthomosaicTile) -> bool:
        """Save a tile and update cache"""
        success = self.storage.save_tile(tile)
        if success:
            with self._lock:
                # Add to cache
                key = (tile.z, tile.x, tile.y)
                self._cache[key] = tile
                self._access_order.append(key)
                
                # Clean cache if too large
                if len(self._cache) > self._cache_size:
                    self._clean_cache()
        
        return success
    
    def get_tile(self, z: int, x: int, y: int) -> Optional[OrthomosaicTile]:
        """Get a tile from cache or storage"""
        key = (z, x, y)
        
        # Check cache first
        with self._lock:
            if key in self._cache:
                # Move to end of access order
                self._access_order.remove(key)
                self._access_order.append(key)
                return self._cache[key]
        
        # Load from storage
        tile = self.storage.load_tile(z, x, y)
        if tile is not None:
            with self._lock:
                self._cache[key] = tile
                self._access_order.append(key)
                self._clean_cache()
        
        return tile
    
    def _clean_cache(self) -> None:
        """Clean least recently used tiles from cache"""
        with self._lock:
            while len(self._cache) > self._cache_size and self._access_order:
                # Remove least recently used
                oldest_key = self._access_order.pop(0)
                if oldest_key in self._cache:
                    del self._cache[oldest_key]
    
    def save_tiles(self, tiles: List[OrthomosaicTile]) -> int:
        """Save multiple tiles"""
        saved = 0
        for tile in tiles:
            if self.save_tile(tile):
                saved += 1
        return saved
    
    def get_tiles_in_bbox(self, z: int, min_x: int, min_y: int, max_x: int, max_y: int) -> List[OrthomosaicTile]:
        """Get all tiles in a bounding box"""
        tiles = []
        for x in range(min_x, max_x + 1):
            for y in range(min_y, max_y + 1):
                tile = self.get_tile(z, x, y)
                if tile is not None:
                    tiles.append(tile)
        return tiles
    
    def get_tiles_at_zoom(self, z: int) -> List[OrthomosaicTile]:
        """Get all tiles at a specific zoom level"""
        tile_list = self.storage.list_tiles(z)
        tiles = []
        
        for tile_info in tile_list:
            tile = self.get_tile(tile_info["z"], tile_info["x"], tile_info["y"])
            if tile is not None:
                tiles.append(tile)
        
        return tiles
    
    def clear_cache(self) -> None:
        """Clear the tile cache"""
        with self._lock:
            self._cache.clear()
            self._access_order.clear()
    
    def clear_all(self) -> None:
        """Clear cache and storage"""
        self.clear_cache()
        # Would need to implement bulk delete for storage
    
    def get_stats(self) -> Dict[str, Any]:
        """Get tile manager statistics"""
        with self._lock:
            return {
                "cache_size": len(self._cache),
                "storage_tiles": len(self.storage.list_tiles()),
                "max_cache_size": self._cache_size,
            }


# Import cv2
try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False
    logger.warning("OpenCV not available, tile manager will not work")
