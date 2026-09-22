"""
Data Processing Utilities for Disaster Map API
Handles PLY to 3D Tiles conversion, trajectory visualization data generation,
and timeline metadata extraction.
"""

import json
import logging
import mmap
import struct
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, asdict

import numpy as np
# from pythreejs import BufferGeometry, Material, Points  # Optional: for Three.js export

logger = logging.getLogger(__name__)


@dataclass
class PointCloudStats:
    """Statistics about a point cloud."""
    count: int
    dimensions: Tuple[int, ...]
    min_values: List[float]
    max_values: List[float]
    has_colors: bool
    has_normals: bool


@dataclass
class TrajectorySegment:
    """A segment of trajectory for visualization."""
    start_index: int
    end_index: int
    positions: np.ndarray
    timestamps: np.ndarray
    confidence: float


# ============================================================================
# PLY File Utilities (Memory-Mapped)
# ============================================================================

def parse_ply_header(file_path: Union[str, Path]) -> Dict:
    """
    Parse PLY file header using memory-mapped I/O for large files.
    
    Args:
        file_path: Path to PLY file
        
    Returns:
        Dictionary with header information and element counts
    """
    path = Path(file_path)
    
    if not path.exists():
        raise FileNotFoundError(f"PLY file not found: {path}")
    
    # Use memory mapping for efficient large file handling
    with open(path, 'rb') as f:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        
        try:
            # Read magic number
            magic = mm.read(4).decode('utf-8', errors='replace')
            if magic != 'PLY':
                raise ValueError("Invalid PLY file (bad magic)")
            
            version = mm.read(2).decode('utf-8').strip()
            if version not in ['1.0', '1.1']:
                logger.warning(f"Non-standard PLY version: {version}")
            
            # Parse elements and properties
            elements = []
            while True:
                elem_name = mm.read(8).decode('utf-8').strip()
                
                if not elem_name or elem_name == 'end_header':
                    break
                
                num_elements = struct.unpack('<I', mm.read(4))[0]
                
                for _ in range(num_elements):
                    prop_type = mm.read(2)
                    prop_name = mm.read(8).decode('utf-8').strip()
                    
                    # Map type codes to numpy types
                    type_map = {
                        b'char': 'i1',
                        b'short': 'i2',
                        b'int': 'i4',
                        b'long': 'i8',
                        b'float': 'f4',
                        b'double': 'f8',
                    }
                    
                    elements.append({
                        'name': prop_name,
                        'type': type_map.get(prop_type, 'f4'),
                        'count': 1
                    })
            
            # Read vertex count if present
            vertex_count = 0
            for elem in elements:
                if elem['name'] == 'vertex':
                    try:
                        vertex_count = struct.unpack('<I', mm.read(4))[0]
                    except (struct.error, IOError):
                        pass
            
        finally:
            mm.close()
    
    return {
        'version': version,
        'elements': elements,
        'vertex_count': vertex_count,
        'file_path': str(path)
    }


def load_ply_points(file_path: Union[str, Path], 
                   use_mmap: bool = True) -> Tuple[np.ndarray, np.ndarray]:
    """
    Load point cloud data from PLY file with optional memory mapping.
    
    Args:
        file_path: Path to PLY file
        use_mmap: Use memory-mapped I/O for large files
        
    Returns:
        Tuple of (positions array, colors array if available)
    """
    path = Path(file_path)
    
    # Parse header first
    header = parse_ply_header(path)
    
    if header['vertex_count'] == 0:
        raise ValueError("No vertices found in PLY file")
    
    # Determine expected point format from elements
    x_elem = y_elem = z_elem = None
    colors = []
    normals = []
    
    for elem in header['elements']:
        if elem['name'] == 'x':
            x_elem = elem
        elif elem['name'] == 'y':
            y_elem = elem
        elif elem['name'] == 'z':
            z_elem = elem
        elif elem['name'] == 'red' or elem['name'] == 'r':
            colors.append(elem)
        elif elem['name'] == 'green' or elem['name'] == 'g':
            colors.append(elem)
        elif elem['name'] == 'blue' or elem['name'] == 'b':
            colors.append(elem)
    
    if not (x_elem and y_elem and z_elem):
        raise ValueError("PLY file missing x, y, z coordinates")
    
    # Load points using memory mapping for efficiency
    dtype = np.dtype([
        ('x', x_elem['type']),
        ('y', y_elem['type']),
        ('z', z_elem['type'])
    ])
    
    if use_mmap and header['vertex_count'] > 10000:
        # Memory-mapped loading for large files
        with open(path, 'rb') as f:
            mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
            
            try:
                # Skip to vertex data (after header)
                offset = struct.calcsize('4s2s') + sum(
                    struct.calcsize('8sI') + 
                    sum(struct.calcsize(elem['type'] * elem['count']) 
                        for elem in header['elements'])
                    for _ in range(len(header['elements']))
                )
                
                # Read points directly
                positions = np.frombuffer(mm[offset:], dtype=dtype, count=header['vertex_count'])
            finally:
                mm.close()
    else:
        # Standard loading
        with open(path, 'rb') as f:
            # Skip header
            header_size = struct.calcsize('4s2s') + sum(
                struct.calcsize('8sI') + 
                sum(struct.calcsize(elem['type'] * elem['count']) 
                    for elem in header['elements'])
                for _ in range(len(header['elements']))
            )
            
            f.seek(header_size)
            positions = np.fromfile(f, dtype=dtype, count=header['vertex_count'])
    
    # Extract colors if available
    color_array = None
    if len(colors) == 3:
        r_dtype = c_dtype = b_dtype = colors[0]['type']
        
        with open(path, 'rb') as f:
            header_size = struct.calcsize('4s2s') + sum(
                struct.calcsize('8sI') + 
                sum(struct.calcsize(elem['type'] * elem['count']) 
                    for elem in header['elements'])
                for _ in range(len(header['elements']))
            )
            
            f.seek(header_size)
            
            # Read colors after positions
            color_dtype = np.dtype([
                ('r', r_dtype),
                ('g', c_dtype),
                ('b', b_dtype)
            ])
            
            try:
                color_array = np.fromfile(f, dtype=color_dtype, count=header['vertex_count'])
            except (struct.error, IOError):
                pass
    
    return positions, color_array


def get_pointcloud_stats(file_path: Union[str, Path]) -> PointCloudStats:
    """Get statistics about a point cloud file."""
    path = Path(file_path)
    
    if not path.exists():
        raise FileNotFoundError(f"PLY file not found: {path}")
    
    positions, colors = load_ply_points(path)
    
    min_vals = np.min(positions, axis=0).tolist()
    max_vals = np.max(positions, axis=0).tolist()
    
    return PointCloudStats(
        count=len(positions),
        dimensions=positions.shape,
        min_values=min_vals,
        max_values=max_vals,
        has_colors=colors is not None and len(colors) == 3,
        has_normals=False  # Would need to parse normal elements
    )


# ============================================================================
# PLY to 3D Tiles Conversion
# ============================================================================

def ply_to_3dtiles(
    input_path: Union[str, Path],
    output_dir: Union[str, Path] = None,
    tile_size: float = 10.0,
    compression: str = "async"
) -> Dict:
    """
    Convert PLY point cloud to Cesium 3D Tiles format.
    
    Args:
        input_path: Input PLY file path
        output_dir: Output directory for 3D Tiles (creates if needed)
        tile_size: Size of each tile in meters
        compression: Compression type ('async', 'sync', or None)
        
    Returns:
        Dictionary with conversion results and output paths
    """
    import os
    
    input_path = Path(input_path)
    
    if not input_path.exists():
        raise FileNotFoundError(f"Input PLY file not found: {input_path}")
    
    # Create output directory
    if output_dir is None:
        output_dir = input_path.parent / "3dtiles"
    else:
        output_dir = Path(output_dir)
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Load point cloud data
    positions, colors = load_ply_points(input_path)
    
    if len(positions) == 0:
        raise ValueError("No points loaded from PLY file")
    
    # Calculate bounding box for tiling
    min_pos = np.min(positions, axis=0)
    max_pos = np.max(positions, axis=0)
    extent = max_pos - min_pos
    
    logger.info(f"Point cloud: {len(positions)} points, "
                f"extent: [{min_pos.tolist()}, {max_pos.tolist()}]")
    
    # Generate tile set structure
    tiles_dir = output_dir / "tiles"
    os.makedirs(tiles_dir, exist_ok=True)
    
    # Create tile hierarchy based on extent and tile size
    tiles_generated = []
    
    def create_tile(
        x: float, y: float, z: float, 
        level: int, positions_subset: np.ndarray, 
        colors_subset: Optional[np.ndarray] = None
    ) -> Dict:
        """Create a single 3D Tiles tile."""
        tile_id = f"{level}_{x}_{y}_{z}"
        
        # Calculate tile bounds
        half_size = tile_size / 2
        
        tile_data = {
            'id': tile_id,
            'positions': positions_subset.tolist(),
            'colors': colors_subset.tolist() if colors_subset is not None else None,
            'bounds': {
                'minX': x - half_size,
                'maxX': x + half_size,
                'minY': y - half_size,
                'maxY': y + half_size,
                'minZ': z - half_size,
                'maxZ': z + half_size
            },
            'tile_content': f"{tiles_dir}/{tile_id}.json"
        }
        
        return tile_data
    
    # Simple tiling strategy: one large tile for small clouds, hierarchical for large
    if extent[0] < tile_size * 2 and extent[1] < tile_size * 2 and extent[2] < tile_size * 2:
        # Single tile covers entire point cloud
        tile = create_tile(
            (min_pos[0] + max_pos[0]) / 2,
            (min_pos[1] + max_pos[1]) / 2,
            (min_pos[2] + max_pos[2]) / 2,
            level=0,
            positions_subset=positions,
            colors_subset=colors if colors is not None else None
        )
        
        # Write tile metadata
        with open(tiles_dir / f"{tile['id']}.json", 'w') as f:
            json.dump(tile, f, indent=2)
        
        tiles_generated.append(tile)
    else:
        # Hierarchical tiling for large point clouds
        current_x = min_pos[0]
        current_y = min_pos[1]
        current_z = min_pos[2]
        level = 0
        
        while True:
            tile_positions = positions[(positions[:, 0] >= current_x) & 
                                      (positions[:, 0] < current_x + tile_size)]
            
            if len(tile_positions) == 0:
                break
            
            # Find max extent in this tile region
            tile_max = np.max(tile_positions, axis=0)
            
            if tile_max[0] >= current_x + tile_size or \
               tile_max[1] >= current_y + tile_size or \
               tile_max[2] >= current_z + tile_size:
                # Create child tiles
                create_child_tiles(
                    positions, colors, 
                    current_x, current_y, current_z,
                    level + 1, tile_size / 2
                )
                break
            
            # Create this tile
            tile = create_tile(
                current_x, current_y, current_z,
                level, tile_positions,
                colors[(positions[:, 0] >= current_x) & 
                      (positions[:, 0] < current_x + tile_size)] if colors is not None else None
            )
            
            tiles_generated.append(tile)
            
            # Move to next position
            current_x = max(current_x + tile_size, min_pos[0])
            current_y = max(current_y + tile_size, min_pos[1])
            current_z = max(current_z + tile_size, min_pos[2])
    
    # Create root tile set JSON
    root_tileset = {
        'asset': {
            'version': '1.0',
            'description': f'3D Tiles from PLY: {input_path.name}',
            'licenseId': 'Apache-2.0'
        },
        'geometricError': max(extent) / 4,
        'root': {
            'boundingVolume': {
                'box': [min_pos.tolist(), max_pos.tolist()]
            },
            'refine': 'add',
            'children': [t['tile_content'] for t in tiles_generated] if tiles_generated else []
        }
    }
    
    # Write tile set
    with open(output_dir / "tileset.json", 'w') as f:
        json.dump(root_tileset, f, indent=2)
    
    return {
        'input_file': str(input_path),
        'output_directory': str(output_dir),
        'tile_count': len(tiles_generated),
        'point_count': len(positions),
        'bounding_box': {
            'min': min_pos.tolist(),
            'max': max_pos.tolist()
        }
    }


def create_child_tiles(
    positions: np.ndarray, 
    colors: Optional[np.ndarray],
    x: float, y: float, z: float,
    level: int, tile_size: float
) -> List[Dict]:
    """Recursively create child tiles for hierarchical tiling."""
    tiles = []
    
    # Process each quadrant/region
    quadrants = [
        (x, y), (x + tile_size, y), (x, y + tile_size), (x + tile_size, y + tile_size)
    ]
    
    for qx, qy in quadrants:
        mask = (positions[:, 0] >= qx - tile_size/2) & \
               (positions[:, 0] < qx + tile_size/2) & \
               (positions[:, 1] >= qy - tile_size/2) & \
               (positions[:, 1] < qy + tile_size/2)
        
        if np.any(mask):
            tile_positions = positions[mask]
            
            if len(tile_positions) > 0:
                tile = create_tile(
                    qx, qy, z, level, tile_positions,
                    colors[mask] if colors is not None else None
                )
                tiles.append(tile)
    
    return tiles


# ============================================================================
# Trajectory Visualization Data Generation
# ============================================================================

def generate_trajectory_visualization_data(trajectory: Dict) -> Dict:
    """
    Generate visualization data for trajectory in the web viewer.
    
    Args:
        trajectory: Dictionary with 'poses' list containing pose data
        
    Returns:
        Dictionary with lines, markers, and animation data
    """
    poses = trajectory.get('poses', [])
    
    if not poses:
        return {
            'lines': [],
            'markers': [],
            'animation': None
        }
    
    # Extract positions and timestamps
    positions = []
    timestamps = []
    confidences = []
    
    for pose in poses:
        x, y, z = pose.get('x', 0), pose.get('y', 0), pose.get('z', 0)
        positions.append([x, y, z])
        timestamps.append(pose.get('timestamp', 0))
        confidences.append(pose.get('confidence', 1.0))
    
    positions = np.array(positions)
    timestamps = np.array(timestamps)
    
    # Generate line segments for trajectory path
    lines = []
    if len(positions) > 1:
        # Create smooth curve using quadratic interpolation points
        num_segments = min(len(positions), 500)  # Limit for performance
        
        for i in range(num_segments - 1):
            p1 = positions[i]
            p2 = positions[i + 1]
            
            line = {
                'start': [round(p1[0], 4), round(p1[1], 4), round(p1[2], 4)],
                'end': [round(p2[0], 4), round(p2[1], 4), round(p2[2], 4)],
                'color': f'rgb({int(50 + confidences[i] * 50)}, {int(150 - confidences[i] * 50)}, {int(50 + confidences[i] * 50)})',
                'width': round(confidences[i] * 2, 1),
                'opacity': min(confidences[i], 1.0)
            }
            lines.append(line)
    
    # Generate markers at key points (every N poses or at waypoints)
    markers = []
    marker_interval = max(1, len(positions) // 50)  # Max 50 markers
    
    for i in range(0, len(positions), marker_interval):
        pose_data = poses[i] if i < len(poses) else {}
        
        marker = {
            'position': [round(positions[i][0], 4), 
                        round(positions[i][1], 4), 
                        round(positions[i][2], 4)],
            'timestamp': round(timestamps[i], 3),
            'confidence': round(confidences[i], 2),
            'type': 'waypoint' if i % marker_interval == 0 else 'checkpoint',
            'label': f"Frame {i}"
        }
        
        # Add special markers for high-confidence points or waypoints
        if confidences[i] > 0.95:
            marker['type'] = 'high_confidence'
        elif pose_data.get('name'):
            marker['name'] = pose_data.get('name')
        
        markers.append(marker)
    
    # Generate animation data for smooth playback
    animation = {
        'duration_seconds': (timestamps[-1] - timestamps[0]) if len(timestamps) > 1 else 1.0,
        'frame_rate': trajectory.get('frame_rate', 30),
        'keyframes': [
            {
                'timestamp': round(timestamps[i], 3),
                'position': positions[i].tolist(),
                'orientation': {
                    'roll': np.degrees(pose_data.get('roll', 0)),
                    'pitch': np.degrees(pose_data.get('pitch', 0)),
                    'yaw': np.degrees(pose_data.get('yaw', 0))
                }
            }
            for i in range(0, len(positions), max(1, len(positions) // 20))
        ]
    }
    
    return {
        'lines': lines,
        'markers': markers,
        'animation': animation,
        'metadata': {
            'total_poses': len(poses),
            'bounding_box': {
                'min': positions.min(axis=0).tolist(),
                'max': positions.max(axis=0).tolist()
            },
            'statistics': {
                'average_speed_mps': np.linalg.norm(positions[1:] - positions[:-1], axis=1).mean(),
                'total_distance_m': np.sum(np.linalg.norm(positions[1:] - positions[:-1], axis=1))
            }
        }
    }


# ============================================================================
# Timeline Metadata Generation
# ============================================================================

def generate_timeline_metadata(trajectory: Dict, 
                              frame_interval_ms: float = 100.0) -> Dict:
    """
    Generate timeline metadata for the web viewer's timeline component.
    
    Args:
        trajectory: Dictionary with pose data and timestamps
        frame_interval_ms: Time interval between frames in milliseconds
        
    Returns:
        Dictionary with timeline configuration and markers
    """
    poses = trajectory.get('poses', [])
    
    if not poses:
        return {
            'start_time': 0,
            'end_time': 0,
            'duration_ms': 0,
            'markers': []
        }
    
    # Calculate timeline bounds
    timestamps = [p.get('timestamp', 0) for p in poses]
    start_time = min(timestamps) if timestamps else 0
    end_time = max(timestamps) if timestamps else 0
    duration_ms = (end_time - start_time) * 1000
    
    # Generate markers at regular intervals and key points
    markers = []
    
    # Add frame markers every N frames for navigation
    marker_interval = max(1, len(poses) // 200)  # Max 200 markers
    
    for i in range(0, len(poses), marker_interval):
        pose_data = poses[i] if i < len(poses) else {}
        
        marker = {
            'index': i,
            'timestamp': round(timestamps[i], 3),
            'position': [round(pose_data.get('x', 0), 2), 
                       round(pose_data.get('y', 0), 2), 
                       round(pose_data.get('z', 0), 2)],
            'label': f"Frame {i}",
            'type': 'frame'
        }
        
        # Highlight important frames
        if pose_data.get('confidence', 1.0) > 0.95:
            marker['highlight'] = True
            marker['label'] = f"✓ Frame {i}"
        
        markers.append(marker)
    
    # Add start and end markers
    markers.insert(0, {
        'index': -1,
        'timestamp': 0,
        'position': [0, 0, 0],
        'label': 'Start',
        'type': 'start'
    })
    
    markers.append({
        'index': len(poses),
        'timestamp': end_time,
        'position': [0, 0, 0],
        'label': 'End',
        'type': 'end'
    })
    
    return {
        'start_time': start_time,
        'end_time': end_time,
        'duration_ms': round(duration_ms, 1),
        'frame_count': len(poses),
        'frame_interval_ms': frame_interval_ms,
        'markers': markers,
        'playback_rate': trajectory.get('frame_rate', 30)
    }


# ============================================================================
# Lazy Loading Utilities
# ============================================================================

class LazyPointCloud:
    """Lazy loading point cloud for memory-efficient handling of large datasets."""
    
    def __init__(self, file_path: Union[str, Path], chunk_size: int = 1024 * 1024):
        self.file_path = Path(file_path)
        self.chunk_size = chunk_size
        self._data = None
        self._positions = None
        self._colors = None
        self._stats = None
    
    def load(self, use_mmap: bool = True) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        """Load point cloud data lazily."""
        if self._positions is not None:
            return self._positions, self._colors
        
        logger.info(f"Loading point cloud from {self.file_path}")
        
        positions, colors = load_ply_points(self.file_path, use_mmap=use_mmap)
        
        self._positions = positions
        self._colors = colors
        
        # Calculate stats once
        if len(positions) > 0:
            self._stats = PointCloudStats(
                count=len(positions),
                dimensions=positions.shape,
                min_values=positions.min(axis=0).tolist(),
                max_values=positions.max(axis=0).tolist(),
                has_colors=colors is not None and len(colors) == 3,
                has_normals=False
            )
        
        logger.info(f"Loaded {len(positions)} points in {self._stats.dimensions}")
        
        return positions, colors
    
    @property
    def stats(self) -> Optional[PointCloudStats]:
        """Get point cloud statistics."""
        if self._stats is None:
            positions, _ = self.load()
            self._stats = PointCloudStats(
                count=len(positions),
                dimensions=positions.shape,
                min_values=positions.min(axis=0).tolist(),
                max_values=positions.max(axis=0).tolist(),
                has_colors=self._colors is not None and len(self._colors) == 3,
                has_normals=False
            )
        return self._stats
    
    def get_subset(self, x_min: float, x_max: float, 
                   y_min: float, y_max: float,
                   z_min: float, z_max: float) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        """Get a spatial subset of the point cloud."""
        positions, colors = self.load()
        
        mask = (positions[:, 0] >= x_min) & (positions[:, 0] <= x_max) & \
               (positions[:, 1] >= y_min) & (positions[:, 1] <= y_max) & \
               (positions[:, 2] >= z_min) & (positions[:, 2] <= z_max)
        
        return positions[mask], colors[mask] if self._colors is not None else None
    
    def get_bounding_box(self) -> Tuple[List[float], List[float]]:
        """Get the bounding box of the point cloud."""
        positions, _ = self.load()
        return positions.min(axis=0).tolist(), positions.max(axis=0).tolist()


# ============================================================================
# Main Processing Functions
# ============================================================================

def process_demo_data():
    """Process all demo data files and generate visualization assets."""
    logger.info("Processing demo data...")
    
    results = {
        'trajectory': None,
        'pointcloud': None,
        'visualization': None,
        'timeline': None
    }
    
    # Load trajectory
    if TRAJECTORY_FILE.exists():
        with open(TRAJECTORY_FILE) as f:
            data = json.load(f)
        
        results['trajectory'] = {
            'poses': data.get('poses', data),
            'file_path': str(TRAJECTORY_FILE)
        }
        logger.info(f"Loaded trajectory from {TRAJECTORY_FILE}")
    
    # Process point cloud if available
    ply_file = PLY_FILES_DIR / "pointcloud.ply"
    if ply_file.exists():
        stats = get_pointcloud_stats(ply_file)
        
        results['pointcloud'] = {
            'file_path': str(ply_file),
            'stats': asdict(stats)
        }
        
        # Convert to 3D Tiles
        try:
            tiles_result = ply_to_3dtiles(
                input_path=ply_file,
                output_dir=output_dir / "3dtiles",
                tile_size=10.0
            )
            results['pointcloud']['tiles'] = tiles_result
        except Exception as e:
            logger.warning(f"Failed to convert PLY to 3D Tiles: {e}")
    
    # Generate visualization data from trajectory
    if results['trajectory']:
        viz_data = generate_trajectory_visualization_data(results['trajectory'])
        results['visualization'] = viz_data
        
        timeline_meta = generate_timeline_metadata(
            results['trajectory'], 
            frame_interval_ms=100.0
        )
        results['timeline'] = timeline_meta
    
    return results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Process disaster map data")
    parser.add_argument("--convert", action="store_true", 
                       help="Convert PLY to 3D Tiles")
    parser.add_argument("--process-all", action="store_true",
                       help="Process all demo data")
    
    args = parser.parse_args()
    
    if args.convert:
        # Convert specific PLY file
        import sys
        ply_file = sys.argv[1] if len(sys.argv) > 1 else str(PLY_FILES_DIR / "pointcloud.ply")
        
        tiles_result = ply_to_3dtiles(ply_file, tile_size=5.0)
        print(f"Converted {tiles_result['input_file']} to 3D Tiles")
        print(f"Output: {tiles_result['output_directory']}")
    
    elif args.process_all:
        results = process_demo_data()
        print("Processing Results:")
        print(json.dumps(results, indent=2, default=str))
