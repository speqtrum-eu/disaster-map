"""
3D Tiles Export Pipeline for Disaster Map Visualization.

Converts point cloud and trajectory data into CesiumJS 3D Tiles format
for efficient streaming and rendering in web browsers.
"""

import json
import os
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, asdict
import numpy as np
from datetime import datetime


@dataclass
class TilesetMetadata:
    """Metadata for a 3D Tiles tileset."""
    name: str
    description: str = ""
    version: str = "1.0"
    created_at: str = ""
    point_count: int = 0
    bounding_volume_type: str = "box"
    minimum_bounding_box: Dict[str, float] = None
    maximum_bounding_box: Dict[str, float] = None


@dataclass
class TileMetadata:
    """Metadata for a single tile."""
    name: str
    parent_ids: List[str] = None
    bounding_volume_type: str = "box"
    minimum_bounding_box: Dict[str, float] = None
    maximum_bounding_box: Dict[str, float] = None
    content: List[Dict[str, Any]] = None


@dataclass
class PointBatch:
    """Point batch within a tile."""
    position: np.ndarray  # (N, 3) coordinates in ECEF or local frame
    color: Optional[np.ndarray] = None  # (N, 4) RGBA
    intensity: Optional[np.ndarray] = None  # (N,) for point lights
    classification: Optional[np.ndarray] = None  # (N,) classification codes


class TileConverterError(Exception):
    """Exception raised during tile conversion."""
    pass


class TileConverter:
    """
    Converts point cloud and trajectory data to CesiumJS 3D Tiles format.
    
    Features:
    - Point cloud export with color/intensity support
    - Trajectory/waypoint visualization
    - LOD (Level of Detail) tile generation
    - Bounding volume optimization
    
    Example usage:
        converter = TileConverter()
        
        # Convert point cloud to 3D Tiles
        tiles, metadata = converter.convert_point_cloud(
            positions=positions,
            colors=colors,
            output_path="./tiles"
        )
        
        # Export trajectory as waypoints
        waypoints = converter.export_trajectory(waypoints)
    """
    
    def __init__(
        self,
        tile_size: float = 1000.0,
        max_points_per_tile: int = 100000,
        lod_levels: int = 4,
        coordinate_system: str = "ECEF",
    ):
        """
        Initialize the tile converter.
        
        Args:
            tile_size: Size of each tile in meters (default: 1000m)
            max_points_per_tile: Maximum points per tile for LOD
            lod_levels: Number of LOD levels to generate
            coordinate_system: Coordinate system ('ECEF' or 'local')
        """
        self.tile_size = tile_size
        self.max_points_per_tile = max_points_per_tile
        self.lod_levels = lod_levels
        self.coordinate_system = coordinate_system
        
        # Output directory
        self.output_dir: Optional[Path] = None
    
    def convert_point_cloud(
        self,
        positions: np.ndarray,
        colors: Optional[np.ndarray] = None,
        intensities: Optional[np.ndarray] = None,
        classifications: Optional[np.ndarray] = None,
        output_path: str = "./tiles",
        tileset_name: str = "point_cloud",
    ) -> Tuple[Dict[str, Any], TilesetMetadata]:
        """
        Convert a point cloud to 3D Tiles format.
        
        Args:
            positions: (N, 3) array of [x, y, z] coordinates
            colors: Optional (N, 4) RGBA color values
            intensities: Optional (N,) intensity values for point lights
            classifications: Optional (N,) classification codes
            output_path: Directory to save tileset files
            tileset_name: Name of the tileset
            
        Returns:
            Tuple of (tileset_json, metadata)
        """
        if positions.shape[0] == 0:
            raise TileConverterError("Empty point cloud")
        
        # Validate input dimensions
        if positions.ndim != 2 or positions.shape[1] != 3:
            raise TileConverterError(
                f"Invalid positions shape: {positions.shape}, expected (N, 3)"
            )
        
        if colors is not None and (colors.shape[0] != len(positions) or colors.shape[1] != 4):
            raise TileConverterError(
                f"Invalid colors shape: {colors.shape}, expected ({len(positions)}, 4)"
            )
        
        # Create output directory
        self.output_dir = Path(output_path)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Calculate bounding box
        min_pos = positions.min(axis=0).tolist()
        max_pos = positions.max(axis=0).tolist()
        
        # Generate LOD levels
        lod_tiles: List[Dict[str, Any]] = []
        
        for level in range(self.lod_levels):
            points_per_tile = self._calculate_points_per_tile(level)
            
            # Create tiles for this LOD level
            tile_data = self._create_lod_tiles(
                positions=positions,
                colors=colors,
                intensities=intensities,
                classifications=classifications,
                points_per_tile=points_per_tile,
                lod_level=level,
            )
            
            lod_tiles.extend(tile_data)
        
        # Create tileset JSON
        tileset_json = self._create_tileset_json(
            lod_tiles=lod_tiles,
            metadata=TilesetMetadata(
                name=tileset_name,
                description=f"Point cloud exported at {datetime.now().isoformat()}",
                point_count=len(positions),
                minimum_bounding_box={
                    "west": min_pos[0],
                    "south": min_pos[1],
                    "bottom": min_pos[2],
                    "east": max_pos[0],
                    "north": max_pos[1],
                    "top": max_pos[2],
                },
                maximum_bounding_box={
                    "west": max_pos[0],
                    "south": max_pos[1],
                    "bottom": max_pos[2],
                    "east": min_pos[0],
                    "north": min_pos[1],
                    "top": min_pos[2],
                },
            ),
        )
        
        # Save tileset JSON
        tileset_path = self.output_dir / f"{tileset_name}.json"
        with open(tileset_path, 'w') as f:
            json.dump(tileset_json, f, indent=2)
        
        print(f"[TileConverter] Created tileset: {tileset_path}")
        print(f"  - Total tiles: {len(lod_tiles)}")
        print(f"  - Bounding box: ({min_pos[0]:.1f}, {min_pos[1]:.1f}, {min_pos[2]:.1f}) to "
              f"({max_pos[0]:.1f}, {max_pos[1]:.1f}, {max_pos[2]:.1f})")
        
        return tileset_json, metadata
    
    def _calculate_points_per_tile(self, lod_level: int) -> int:
        """Calculate points per tile for a given LOD level."""
        # Exponential decrease with LOD level
        base = self.max_points_per_tile
        factor = 0.5 ** lod_level
        return max(100, int(base * factor))
    
    def _create_lod_tiles(
        self,
        positions: np.ndarray,
        colors: Optional[np.ndarray],
        intensities: Optional[np.ndarray],
        classifications: Optional[np.ndarray],
        points_per_tile: int,
        lod_level: int,
    ) -> List[Dict[str, Any]]:
        """Create tiles for a specific LOD level."""
        tiles = []
        
        # Sort positions by z-coordinate for better rendering order
        sort_indices = np.argsort(positions[:, 2])
        sorted_positions = positions[sort_indices]
        
        if colors is not None:
            sorted_colors = colors[sort_indices]
        else:
            sorted_colors = None
        
        # Create tiles in a grid pattern
        tile_width = int(np.ceil(np.sqrt(len(positions) / points_per_tile)))
        
        for i in range(tile_width):
            for j in range(tile_width):
                start_idx = (i * tile_width + j) * points_per_tile
                end_idx = min(start_idx + points_per_tile, len(positions))
                
                if end_idx <= start_idx:
                    continue
                
                tile_positions = sorted_positions[start_idx:end_idx]
                
                # Calculate tile bounding box
                tile_min = tile_positions.min(axis=0).tolist()
                tile_max = tile_positions.max(axis=0).tolist()
                
                # Create tile content
                tile_content = []
                
                if colors is not None:
                    tile_colors = sorted_colors[start_idx:end_idx].tolist()
                    tile_content.append({
                        "uri": f"colors_{i}_{j}.bin",
                        "byteLength": len(tile_colors) * 16,  # RGBA float32
                        "format": {
                            "schemaUri": "https://cesium.com/ion/schemas/3d-tiles/content/color.schema.json",
                            "componentType": "FLOAT",
                            "channels": ["red", "green", "blue", "alpha"],
                        },
                    })
                
                tile_data = {
                    "uri": f"points_{i}_{j}.bin",
                    "byteLength": len(tile_positions) * 12,  # XYZ float32
                    "format": {
                        "schemaUri": "https://cesium.com/ion/schemas/3d-tiles/content/binary.schema.json",
                        "bufferViews": [
                            {
                                "uri": f"points_{i}_{j}.bin",
                                "byteOffset": 0,
                                "byteLength": len(tile_positions) * 12,
                                "target": 34962,  # ARRAY_BUFFER
                            },
                        ],
                        "buffers": [],
                    },
                }
                
                tiles.append({
                    "name": f"tile_{i}_{j}_lod{lod_level}",
                    "boundingVolume": {
                        "box": tile_min + tile_max,
                    },
                    "geometricError": self.tile_size / (2 ** lod_level),
                    "content": [tile_data],
                })
        
        return tiles
    
    def _create_tileset_json(
        self,
        lod_tiles: List[Dict[str, Any]],
        metadata: TilesetMetadata,
    ) -> Dict[str, Any]:
        """Create the main tileset JSON structure."""
        # Group tiles by LOD level
        lod_groups = {}
        for tile in lod_tiles:
            name_parts = tile["name"].split("_")
            if len(name_parts) >= 3 and name_parts[2].startswith("lod"):
                try:
                    level = int(name_parts[2][3:])
                    if level not in lod_groups:
                        lod_groups[level] = []
                    lod_groups[level].append(tile)
                except (ValueError, IndexError):
                    pass
        
        # Create tilesets array with LOD levels
        tilesets = []
        for level, tiles in sorted(lod_groups.items()):
            tileset_entry = {
                "refine": "add",
                "geometricError": self.tile_size / (2 ** level),
                "children": [
                    {"name": f"lod{level}", "tiles": tiles}
                ],
            }
            tilesets.append(tileset_entry)
        
        return {
            "asset": {
                "version": metadata.version,
                "uri": "#",
            },
            "geometricError": self.tile_size / 2,
            "root": {
                "refine": "add",
                "boundingVolume": {
                    "box": [
                        metadata.minimum_bounding_box["west"],
                        metadata.minimum_bounding_box["south"],
                        metadata.minimum_bounding_box["bottom"],
                        metadata.maximum_bounding_box["east"],
                        metadata.maximum_bounding_box["north"],
                        metadata.maximum_bounding_box["top"],
                    ],
                },
                "geometricError": self.tile_size / 2,
                "content": [],
            },
            "tilesets": tilesets if tilesets else None,
        }
    
    def export_trajectory(
        self,
        waypoints: List[Tuple[float, float, float]],
        trajectory_name: str = "trajectory",
        output_path: str = "./tiles",
    ) -> Dict[str, Any]:
        """
        Export a trajectory as 3D Tiles waypoints.
        
        Args:
            waypoints: List of (x, y, z) coordinates along the path
            trajectory_name: Name for the trajectory tileset
            output_path: Directory to save files
            
        Returns:
            Tileset JSON structure
        """
        if not waypoints:
            raise TileConverterError("No waypoints provided")
        
        positions = np.array(waypoints)
        
        # Create a line visualization using multiple small tiles
        tileset_json, metadata = self.convert_point_cloud(
            positions=positions,
            output_path=output_path,
            tileset_name=trajectory_name,
        )
        
        return tileset_json
    
    def export_waypoint_markers(
        self,
        waypoints: List[Tuple[float, float, float]],
        colors: Optional[List[Tuple[int, int, int, int]]] = None,
        output_path: str = "./tiles",
    ) -> Dict[str, Any]:
        """
        Export individual waypoint markers as 3D Tiles.
        
        Args:
            waypoints: List of (x, y, z) coordinates for markers
            colors: Optional list of RGBA colors for each marker
            output_path: Directory to save files
            
        Returns:
            Tileset JSON structure
        """
        if not waypoints:
            raise TileConverterError("No waypoints provided")
        
        # Create a small point cloud with larger points for visibility
        positions = np.array(waypoints)
        
        # Add some offset to make markers visible as spheres
        offsets = [
            [-0.5, -0.5, 0], [0.5, -0.5, 0], [-0.5, 0.5, 0], [0.5, 0.5, 0]
        ]
        
        all_positions = []
        all_colors = None
        
        for i, (pos, offset) in enumerate(zip(positions, offsets)):
            # Create a small cluster of points around each waypoint
            cluster_size = 3
            cluster_positions = np.array([
                pos + offset + np.random.randn(cluster_size, 3) * 0.1
                for _ in range(5)
            ])
            all_positions.extend(cluster_positions)
            
            if colors:
                color = colors[i % len(colors)]
                cluster_colors = np.tile(color, (cluster_size, 1))
                if all_colors is None:
                    all_colors = cluster_colors
                else:
                    all_colors = np.vstack([all_colors, cluster_colors])
        
        positions = np.array(all_positions)
        colors = all_colors
        
        return self.convert_point_cloud(
            positions=positions,
            colors=colors,
            output_path=output_path,
            tileset_name=f"waypoints_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        )
    
    def validate_tileset(self, tileset_path: str) -> Dict[str, Any]:
        """
        Validate a 3D Tiles file against CesiumJS schema.
        
        Args:
            tileset_path: Path to the .json tileset file
            
        Returns:
            Validation result with errors and warnings
        """
        try:
            with open(tileset_path, 'r') as f:
                data = json.load(f)
            
            errors = []
            warnings = []
            
            # Check required fields
            if "asset" not in data:
                errors.append("Missing 'asset' field")
            elif "version" not in data["asset"]:
                warnings.append("No version specified in asset")
            
            if "root" not in data:
                errors.append("Missing 'root' field")
            else:
                # Check bounding volume
                if "boundingVolume" not in data["root"]:
                    errors.append("Root missing 'boundingVolume'")
                
                # Validate bounding box format
                bbox = data["root"].get("boundingVolume", {})
                if isinstance(bbox, dict) and "box" in bbox:
                    box = bbox["box"]
                    if len(box) != 6:
                        errors.append(f"Bounding box must have 6 values, got {len(box)}")
            
            # Check tilesets array
            if "tilesets" in data:
                for i, ts in enumerate(data["tilesets"]):
                    if "children" not in ts:
                        warnings.append(f"Tileset {i} missing 'children'")
                    
                    for j, child in enumerate(ts.get("children", [])):
                        if "tiles" not in child:
                            warnings.append(f"Child {j} of tileset {i} missing 'tiles'")
            
            return {
                "valid": len(errors) == 0,
                "errors": errors,
                "warnings": warnings,
            }
            
        except json.JSONDecodeError as e:
            return {"valid": False, "errors": [f"Invalid JSON: {e}"], "warnings": []}
        except FileNotFoundError:
            return {"valid": False, "errors": [f"File not found: {tileset_path}"], "warnings": []}


# Utility functions for batch processing

def convert_directory(
    input_dir: str,
    output_dir: str = "./tiles",
    recursive: bool = True,
) -> List[Dict[str, Any]]:
    """
    Convert all point cloud files in a directory to 3D Tiles.
    
    Args:
        input_dir: Directory containing .npy or .npz point cloud files
        output_dir: Output directory for tilesets
        recursive: Whether to process subdirectories
        
    Returns:
        List of conversion results
    """
    import glob
    
    converter = TileConverter()
    results = []
    
    # Find all numpy point cloud files
    patterns = ["*.npy", "*.npz"]
    if recursive:
        patterns.append("**/*.npy")
        patterns.append("**/*.npz")
    
    files = glob.glob(os.path.join(input_dir, *patterns))
    
    for file_path in sorted(files):
        try:
            # Load point cloud data
            if file_path.endswith('.npz'):
                data = np.load(file_path)
                positions = data.get('positions', data.get('data'))
                colors = data.get('colors')
                intensities = data.get('intensities')
            else:
                positions = np.load(file_path)
                colors = None
            
            # Extract filename for tileset name
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            
            # Convert to 3D Tiles
            result, metadata = converter.convert_point_cloud(
                positions=positions,
                colors=colors,
                intensities=intensities,
                output_path=output_dir,
                tileset_name=f"{base_name}_tiles",
            )
            
            results.append({
                "input": file_path,
                "output": os.path.join(output_dir, f"{base_name}.json"),
                "point_count": len(positions),
                "success": True,
            })
            
        except Exception as e:
            results.append({
                "input": file_path,
                "error": str(e),
                "success": False,
            })
    
    return results


if __name__ == "__main__":
    import numpy as np
    
    print("=" * 60)
    print("3D Tiles Converter Demo")
    print("=" * 60)
    
    # Create sample point cloud
    np.random.seed(42)
    positions = np.random.randn(5000, 3) * 1000 + [0, 0, 50000]
    colors = np.random.rand(5000, 4)
    
    print(f"\nSample data: {positions.shape[0]} points")
    print(f"Bounding box: ({positions.min(axis=0).tolist()}, {positions.max(axis=0).tolist()})")
    
    # Convert to 3D Tiles
    converter = TileConverter(
        tile_size=1000.0,
        max_points_per_tile=50000,
        lod_levels=4,
    )
    
    tileset_json, metadata = converter.convert_point_cloud(
        positions=positions,
        colors=colors,
        output_path="./tiles",
        tileset_name="demo_terrain",
    )
    
    # Validate the result
    validator = TileConverter()
    validation = validator.validate_tileset("./tiles/demo_terrain.json")
    
    print(f"\nValidation Result:")
    print(f"  Valid: {validation['valid']}")
    if validation['errors']:
        for error in validation['errors']:
            print(f"  Error: {error}")
    if validation['warnings']:
        for warning in validation['warnings']:
            print(f"  Warning: {warning}")
    
    # Export trajectory example
    waypoints = [
        (0, 0, 50000),
        (1000, 500, 49500),
        (2000, 1000, 49000),
        (3000, 1500, 48500),
    ]
    
    print(f"\nExporting trajectory with {len(waypoints)} waypoints...")
    traj_json = converter.export_trajectory(waypoints, "demo_trajectory")
    print("Trajectory exported successfully!")
    
    # Export waypoint markers
    marker_colors = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255)]
    print(f"\nExporting {len(waypoints)} waypoint markers...")
    marker_json = converter.export_waypoint_markers(waypoints, marker_colors)
    print("Waypoint markers exported successfully!")
    
    print("\nDemo complete! Check './tiles/' directory for output files.")
