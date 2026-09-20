"""
Incremental Map Mapper for Efficient Updates.

Provides:
- Incremental point cloud updates with memory management
- Automatic LOD (Level of Detail) generation
- Sparse grid optimization for large maps
- Real-time update batching

Example:
    >>> mapper = IncrementalMapper(
    ...     max_points=5_000_000,
    ...     lod_levels=4,
    ... )
    >>> async for frame in stream_frames():
    ...     mapper.update(frame)
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple, Any, Callable
from enum import Enum


logger = logging.getLogger(__name__)


@dataclass
class MapperConfig:
    """Configuration for incremental mapper."""
    # Point cloud settings
    max_points: int = 5_000_000
    min_point_distance: float = 0.1  # Minimum distance between points (meters)
    
    # Level of Detail (LOD)
    lod_levels: int = 4
    lod_thresholds: List[float] = field(default_factory=lambda: [10, 50, 100, 200])
    
    # Update settings
    batch_size: int = 1000  # Points per batch operation
    update_interval_ms: float = 10.0  # Minimum time between updates
    
    # Memory management
    max_memory_mb: float = 2048.0
    cleanup_age_seconds: float = 60.0
    
    # Optimization
    use_sparse_grid: bool = True
    grid_cell_size: float = 1.0  # Grid cell size in meters


@dataclass
class MapUpdateResult:
    """Result of applying a map update."""
    success: bool
    points_added: int
    points_removed: int
    memory_mb_before: float
    memory_mb_after: float
    
    # Timing
    processing_time_ms: float = 0.0
    
    # Metadata
    timestamp: float = 0.0
    update_id: Optional[int] = None


@dataclass
class LODLevel:
    """Level of Detail representation."""
    level: int
    points: List[Tuple[float, float, float]]  # [x, y, z] coordinates
    colors: List[Tuple[float, float, float]]  # [r, g, b] colors
    
    @property
    def point_count(self) -> int:
        return len(self.points)


class SparseGrid:
    """
    Sparse grid for efficient spatial queries and memory management.
    
    Features:
    - O(1) cell access
    - Automatic cleanup of empty cells
    - Support for point density filtering
    
    Example:
        >>> grid = SparseGrid(cell_size=1.0, max_points_per_cell=1000)
        >>> grid.add_point([x, y, z], color=[r, g, b])
        >>> neighbors = grid.get_neighbors([x, y, z])
    """
    
    def __init__(self, cell_size: float = 1.0, max_points_per_cell: int = 1000):
        self.cell_size = cell_size
        self.max_points_per_cell = max_points_per_cell
        
        # Grid cells indexed by (x_cell, y_cell)
        self._cells: Dict[Tuple[int, int], List[Any]] = {}
        
        # Point to cell mapping for quick lookup
        self._point_to_cell: Dict[int, Tuple[int, int]] = {}
        
        # Statistics
        self._total_points = 0
        self._total_cells = 0
    
    def get_cell_coords(self, x: float, y: float) -> Tuple[int, int]:
        """Get grid cell coordinates for a point."""
        return (int(x // self.cell_size), int(y // self.cell_size))
    
    def add_point(
        self, 
        x: float, 
        y: float, 
        z: float, 
        color: Optional[Tuple[float, float, float]] = None,
        point_id: Optional[int] = None
    ) -> bool:
        """
        Add a point to the grid.
        
        Args:
            x, y, z: Point coordinates
            color: Point color (optional)
            point_id: Unique point identifier (auto-generated if not provided)
            
        Returns:
            True if point added successfully
            
        Example:
            >>> success = grid.add_point(10.5, 20.3, 5.7, color=[0.2, 0.8, 0.3])
        """
        cell_x, cell_y = self.get_cell_coords(x, y)
        
        # Create new cell if needed
        if (cell_x, cell_y) not in self._cells:
            self._cells[(cell_x, cell_y)] = []
            self._total_cells += 1
        
        cell = self._cells[(cell_x, cell_y)]
        
        # Check max points per cell
        if len(cell) >= self.max_points_per_cell:
            return False
            
        point_id = point_id or id((x, y, z))
        
        point_data = {
            "id": point_id,
            "position": (x, y, z),
            "color": color or (0.5, 0.5, 0.5),
            "timestamp": time.time(),
        }
        
        cell.append(point_data)
        self._point_to_cell[point_id] = (cell_x, cell_y)
        self._total_points += 1
        
        return True
    
    def get_neighbors(
        self, 
        x: float, 
        y: float, 
        radius_cells: int = 2
    ) -> List[Tuple[int, int]]:
        """Get neighboring cells within a radius."""
        cell_x, cell_y = self.get_cell_coords(x, y)
        
        neighbors = []
        for dx in range(-radius_cells, radius_cells + 1):
            for dy in range(-radius_cells, radius_cells + 1):
                if dx == 0 and dy == 0:
                    continue
                    
                neighbor = (cell_x + dx, cell_y + dy)
                
                if neighbor in self._cells:
                    neighbors.append(neighbor)
        
        return neighbors
    
    def get_points_in_radius(
        self, 
        x: float, 
        y: float, 
        z: float, 
        radius: float = 5.0
    ) -> List[Tuple[float, float, float]]:
        """Get all points within a spherical radius."""
        results = []
        
        # Check current cell and neighbors
        cells_to_check = [self.get_cell_coords(x, y)] + \
                        self.get_neighbors(x, y)
        
        for (cell_x, cell_y) in cells_to_check:
            if (cell_x, cell_y) not in self._cells:
                continue
                
            for point_data in self._cells[(cell_x, cell_y)]:
                px, py, pz = point_data["position"]
                
                # Calculate distance
                dx = px - x
                dy = py - y
                dz = pz - z
                distance = (dx * dx + dy * dy + dz * dz) ** 0.5
                
                if distance <= radius:
                    results.append((px, py, pz))
        
        return results
    
    def cleanup_empty_cells(self, max_age_seconds: float = 60.0) -> int:
        """Remove empty or old cells."""
        current_time = time.time()
        removed_count = 0
        
        for cell_coords in list(self._cells.keys()):
            points = self._cells[cell_coords]
            
            # Check if all points are old
            if not any(p["timestamp"] > current_time - max_age_seconds 
                      for p in points):
                del self._cells[cell_coords]
                removed_count += 1
        
        return removed_count
    
    @property
    def point_count(self) -> int:
        """Get total number of points."""
        return self._total_points
    
    @property
    def cell_count(self) -> int:
        """Get number of active cells."""
        return len(self._cells)


class IncrementalMapper:
    """
    Incremental map mapper with efficient updates and memory management.
    
    Features:
    - Automatic LOD generation for visualization
    - Sparse grid optimization for large maps
    - Memory-aware point filtering
    - Real-time update batching
    
    Example:
        >>> mapper = IncrementalMapper(
        ...     max_points=5_000_000,
        ...     use_sparse_grid=True,
        ... )
        >>> async for frame in stream_frames():
        ...     result = mapper.update(frame)
        ...     if not result.success:
        ...         logger.error(f"Update failed: {result}")
    """
    
    def __init__(self, config: Optional[MapperConfig] = None):
        self.config = config or MapperConfig()
        
        # Point cloud storage
        self._points: List[Tuple[float, float, float]] = []
        self._colors: List[Tuple[float, float, float]] = []
        self._timestamps: List[float] = []
        
        # Sparse grid for spatial queries
        if self.config.use_sparse_grid:
            self._grid = SparseGrid(
                cell_size=self.config.grid_cell_size,
                max_points_per_cell=1000
            )
        else:
            self._grid = None
        
        # LOD levels
        self._lod_levels: List[LODLevel] = []
        
        # Update state
        self._last_update_time: float = time.time()
        self._update_counter = 0
        self._pending_updates: int = 0
        
        # Memory management
        self._memory_mb = 0.0
        self._cleanup_task: Optional[asyncio.Task] = None
        
    async def update(
        self, 
        points: List[Tuple[float, float, float]], 
        colors: Optional[List[Tuple[float, float, float]]] = None,
        timestamps: Optional[List[float]] = None,
        batch_id: Optional[int] = None
    ) -> MapUpdateResult:
        """
        Apply an incremental update to the map.
        
        Args:
            points: New point cloud data [N, 3]
            colors: Point colors (optional)
            timestamps: Capture timestamps (optional)
            batch_id: Batch identifier for tracking
            
        Returns:
            MapUpdateResult with statistics
            
        Example:
            >>> result = mapper.update(
            ...     points=[(x1,y1,z1), (x2,y2,z2)],
            ...     colors=[(r1,g1,b1), (r2,g2,b2)]
            ... )
        """
        start_time = time.perf_counter()
        
        # Calculate memory before update
        memory_before = self._estimate_memory_mb()
        
        try:
            points_array = list(points)
            colors_array = colors or [(0.5, 0.5, 0.5)] * len(points_array)
            timestamps_array = timestamps or [time.time()] * len(points_array)
            
            # Filter duplicate points (within min_distance threshold)
            filtered_points, filtered_colors, filtered_timestamps = [], [], []
            
            for i in range(len(points_array)):
                x, y, z = points_array[i]
                
                # Check if point is too close to existing points
                if self._grid:
                    neighbors = self._grid.get_points_in_radius(x, y, z, 
                                                                radius=self.config.min_point_distance)
                    
                    if len(neighbors) >= 100:  # Threshold for density check
                        continue
                
                filtered_points.append((x, y, z))
                filtered_colors.append(colors_array[i])
                filtered_timestamps.append(timestamps_array[i])
            
            points_added = len(filtered_points)
            
            if points_added == 0:
                return MapUpdateResult(
                    success=True,
                    points_added=0,
                    points_removed=0,
                    memory_mb_before=memory_before,
                    memory_mb_after=memory_before,
                    processing_time_ms=(time.perf_counter() - start_time) * 1000,
                    timestamp=time.time(),
                    update_id=batch_id,
                )
            
            # Add points to storage
            self._points.extend(filtered_points)
            self._colors.extend(filtered_colors)
            self._timestamps.extend(filtered_timestamps)
            
            # Update sparse grid if enabled
            if self._grid:
                for i in range(points_added):
                    x, y, z = filtered_points[i]
                    self._grid.add_point(x, y, z, 
                                       color=filtered_colors[i],
                                       point_id=len(self._points) - 1)
            
            # Generate/update LOD levels
            await self._update_lod_levels()
            
            # Check memory and cleanup if needed
            if self._memory_mb > self.config.max_memory_mb:
                await self._cleanup_old_points()
            
            # Update statistics
            self._update_counter += 1
            self._pending_updates = max(0, self._pending_updates - 1)
            
            memory_after = self._estimate_memory_mb()
            
            return MapUpdateResult(
                success=True,
                points_added=points_added,
                points_removed=0,
                memory_mb_before=memory_before,
                memory_mb_after=memory_after,
                processing_time_ms=(time.perf_counter() - start_time) * 1000,
                timestamp=time.time(),
                update_id=batch_id,
            )
            
        except Exception as e:
            logger.error(f"Failed to apply map update: {e}")
            
            return MapUpdateResult(
                success=False,
                points_added=0,
                points_removed=0,
                memory_mb_before=memory_before,
                memory_mb_after=memory_before,
                processing_time_ms=(time.perf_counter() - start_time) * 1000,
                timestamp=time.time(),
                update_id=batch_id,
            )
    
    async def _update_lod_levels(self) -> None:
        """Update Level of Detail representations."""
        if not self._points or len(self._lod_levels) >= self.config.lod_levels:
            return
        
        # Generate LOD for each level
        for lod_idx, threshold in enumerate(self.config.lod_thresholds):
            if lod_idx >= len(self._lod_levels):
                new_lod = LODLevel(
                    level=lod_idx,
                    points=[],
                    colors=[]
                )
                
                # Sample points based on threshold (lower density for higher levels)
                sample_rate = max(1, int(len(self._points) / threshold))
                
                for i in range(0, len(self._points), sample_rate):
                    new_lod.points.append(self._points[i])
                    new_lod.colors.append(self._colors[i])
                
                self._lod_levels.append(new_lod)
    
    async def _cleanup_old_points(self) -> int:
        """Remove old points to free memory."""
        if not self._timestamps:
            return 0
        
        cutoff_time = time.time() - self.config.cleanup_age_seconds
        
        # Find oldest point to keep
        min_valid_idx = None
        for i, ts in enumerate(self._timestamps):
            if ts >= cutoff_time:
                min_valid_idx = i
                break
        
        if min_valid_idx is None:
            return 0
        
        removed_count = len(self._points) - min_valid_idx
        
        # Remove old points from all structures
        self._points = self._points[min_valid_idx:]
        self._colors = self._colors[min_valid_idx:]
        self._timestamps = self._timestamps[min_valid_idx:]
        
        if self._grid:
            self._grid.cleanup_empty_cells(self.config.cleanup_age_seconds)
        
        return removed_count
    
    def _estimate_memory_mb(self) -> float:
        """Estimate current memory usage in megabytes."""
        # Rough estimate based on data structures
        point_size = 12  # 3 floats for position (float64) + 3 for color (float32)
        total_bytes = len(self._points) * point_size
        
        return total_bytes / (1024 * 1024)
    
    def get_point_cloud(
        self, 
        start_idx: int = 0, 
        end_idx: Optional[int] = None
    ) -> Tuple[List[Tuple[float, float, float]], List[Tuple[float, float, float]]]:
        """Get point cloud data as lists."""
        end_idx = end_idx or len(self._points)
        
        return (
            list(self._points[start_idx:end_idx]),
            list(self._colors[start_idx:end_idx])
        )
    
    def get_point_cloud_numpy(
        self, 
        start_idx: int = 0, 
        end_idx: Optional[int] = None
    ):
        """Get point cloud data as numpy arrays."""
        try:
            import numpy as np
            
            positions = np.array(self._points[start_idx:end_idx], dtype=np.float64)
            colors = np.array(self._colors[start_idx:end_idx], dtype=np.float32)
            
            return positions, colors
            
        except ImportError:
            # Fallback to lists if numpy not available
            return self.get_point_cloud(start_idx, end_idx)
    
    def get_lod_data(
        self, 
        level: Optional[int] = None
    ) -> Optional[LODLevel]:
        """Get LOD data for a specific level."""
        if level is None:
            # Return highest detail level (lowest index)
            return self._lod_levels[0] if self._lod_levels else None
        
        if 0 <= level < len(self._lod_levels):
            return self._lod_levels[level]
        
        return None
    
    def get_map_bounds(self) -> Optional[Tuple[Tuple[float, float, float], 
                                               Tuple[float, float, float]]]:
        """Get bounding box of the map."""
        if not self._points:
            return None
            
        positions = list(self._points)
        
        min_pt = min(positions, key=lambda p: (p[0] ** 2 + p[1] ** 2 + p[2] ** 2))
        max_pt = max(positions, key=lambda p: (p[0] ** 2 + p[1] ** 2 + p[2] ** 2))
        
        return (min_pt, max_pt)
    
    def reset(self) -> None:
        """Reset mapper state."""
        logger.info("Resetting incremental mapper...")
        
        self._points.clear()
        self._colors.clear()
        self._timestamps.clear()
        
        if self._grid:
            self._grid = SparseGrid(
                cell_size=self.config.grid_cell_size,
                max_points_per_cell=1000
            )
        
        self._lod_levels.clear()
        self._update_counter = 0
        
    def get_stats(self) -> Dict[str, Any]:
        """Get mapper statistics."""
        bounds = self.get_map_bounds()
        
        return {
            "point_count": len(self._points),
            "memory_mb": round(self._estimate_memory_mb(), 2),
            "lod_levels": len(self._lod_levels),
            "bounds": {
                "min": list(bounds[0]) if bounds else None,
                "max": list(bounds[1]) if bounds else None,
            },
        }
