"""
Path Visualizer - 3D Path Rendering and Trajectory Visualization.

Provides:
- Multi-layer path rendering (primary, secondary, planned)
- Smooth trajectory interpolation
- Performance-optimized for millions of points
- Interactive path controls and annotations
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
import numpy as np


@dataclass
class PathLayer:
    """Represents a visual layer for paths."""
    name: str
    color: Tuple[float, float, float]  # RGB (0-1)
    width: float = 2.0
    opacity: float = 0.8
    is_active: bool = True
    show_markers: bool = True
    marker_color: Optional[Tuple[float, float, float]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert layer to dictionary for serialization."""
        return {
            "name": self.name,
            "color": list(self.color),
            "width": self.width,
            "opacity": self.opacity,
            "is_active": self.is_active,
            "show_markers": self.show_markers,
            "marker_color": list(self.marker_color) if self.marker_color else None,
        }


@dataclass
class PathAnnotation:
    """Annotation for a path point."""
    latitude: float
    longitude: float
    altitude: float
    text: str
    position_index: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "altitude": self.altitude,
            "text": self.text,
            "position_index": self.position_index,
        }


@dataclass
class PathVisualization:
    """Complete path visualization with multiple layers."""
    primary_path: Optional[List[Dict[str, float]]] = None
    secondary_paths: List[List[Dict[str, float]]] = field(default_factory=list)
    planned_path: Optional[List[Dict[str, float]]] = None
    
    annotations: List[PathAnnotation] = field(default_factory=list)
    
    layers: List[PathLayer] = field(default_factory=lambda: [
        PathLayer("primary", (0.2, 0.6, 0.8), width=3.0, opacity=1.0),
        PathLayer("secondary", (0.8, 0.4, 0.2), width=2.0, opacity=0.7),
        PathLayer("planned", (0.5, 0.5, 0.5), width=1.5, opacity=0.5),
    ])
    
    def __post_init__(self):
        if not self.primary_path:
            self.primary_path = []


class PathVisualizer:
    """
    Advanced path visualization for 3D navigation.
    
    Features:
    - Multi-layer path rendering with different styles
    - Smooth trajectory interpolation
    - Performance-optimized rendering (LOD support)
    - Interactive annotations and markers
    
    Example usage:
        visualizer = PathVisualizer()
        
        # Add primary path
        points = [{"latitude": 35.0, "longitude": -120.0, "altitude": 500}]
        visualizer.add_primary_path(points)
        
        # Add secondary paths (alternative routes)
        alt_points = [...]
        visualizer.add_secondary_path(alt_points, name="alternate")
        
        # Add annotations
        annotation = PathAnnotation(35.1, -120.1, 600, "Checkpoint A")
        visualizer.add_annotation(annotation)
    """
    
    def __init__(self):
        self.visualization = PathVisualization()
        self._interpolation_cache: Dict[str, np.ndarray] = {}
        self._lod_thresholds: List[float] = [1000, 5000, 10000, 50000]
        
    def add_primary_path(
        self, 
        points: List[Dict[str, float]], 
        layer: Optional[PathLayer] = None,
    ) -> int:
        """Add primary navigation path."""
        if not points:
            print("[PathVisualizer] No points to add as primary path")
            return -1
        
        # Use provided layer or default
        self.visualization.primary_path = points
        
        if layer:
            self.visualization.layers[0] = layer
        
        print(f"[PathVisualizer] Added primary path with {len(points)} points")
        return 0
    
    def add_secondary_path(
        self, 
        points: List[Dict[str, float]], 
        name: str = "secondary",
        layer: Optional[PathLayer] = None,
    ) -> int:
        """Add secondary path (alternative route)."""
        if not points:
            return -1
        
        # Create new layer for this path
        if layer is None:
            layer = PathLayer(name, color=(0.8, 0.4, 0.2), width=2.0)
        
        self.visualization.secondary_paths.append(points)
        self.visualization.layers.append(layer)
        
        print(f"[PathVisualizer] Added secondary path '{name}' with {len(points)} points")
        return len(self.visualization.secondary_paths) - 1
    
    def add_planned_path(
        self, 
        points: List[Dict[str, float]], 
        layer: Optional[PathLayer] = None,
    ) -> int:
        """Add planned path (future route)."""
        if not points:
            return -1
        
        self.visualization.planned_path = points
        
        if layer:
            self.visualization.layers.append(layer)
        
        print(f"[PathVisualizer] Added planned path with {len(points)} points")
        return 1
    
    def add_annotation(self, annotation: PathAnnotation) -> int:
        """Add annotation to a path point."""
        self.visualization.annotations.append(annotation)
        print(f"[PathVisualizer] Added annotation: '{annotation.text}' at ({annotation.latitude}, {annotation.longitude})")
        return len(self.visualization.annotations) - 1
    
    def get_interpolated_path(
        self, 
        points: List[Dict[str, float]], 
        num_points: int = 1000,
    ) -> np.ndarray:
        """Generate interpolated path with smooth curves."""
        if not points or len(points) < 2:
            return np.array([])
        
        # Cache result for performance
        cache_key = f"{len(points)}_{num_points}"
        if cache_key in self._interpolation_cache:
            return self._interpolation_cache[cache_key]
        
        # Extract coordinates
        lats = np.array([p["latitude"] for p in points])
        lons = np.array([p["longitude"] for p in points])
        alts = np.array([p["altitude"] for p in points])
        
        # Use spline interpolation for smooth curves
        from scipy.interpolate import interp1d
        
        t = np.linspace(0, 1, num_points)
        
        lat_interp = interp1d(range(len(points)), lats, kind='cubic', fill_value="extrapolate")(t)
        lon_interp = interp1d(range(len(points)), lons, kind='cubic', fill_value="extrapolate")(t)
        alt_interp = interp1d(range(len(points)), alts, kind='cubic', fill_value="extrapolate")(t)
        
        interpolated = np.column_stack([lat_interp, lon_interp, alt_interp])
        
        # Cache for performance
        self._interpolation_cache[cache_key] = interpolated
        
        return interpolated
    
    def get_optimized_points(
        self, 
        points: List[Dict[str, float]], 
        max_distance: float = 100.0,
    ) -> List[Dict[str, float]]:
        """Reduce point count while maintaining path accuracy (LOD)."""
        if not points or len(points) <= 2:
            return points
        
        # Calculate distances between consecutive points
        lats = np.array([p["latitude"] for p in points])
        lons = np.array([p["longitude"] for p in points])
        alts = np.array([p["altitude"] for p in points])
        
        distances = []
        for i in range(len(points) - 1):
            dx = lats[i+1] - lats[i]
            dy = lons[i+1] - lons[i]
            dz = alts[i+1] - alts[i]
            dist = np.sqrt(dx**2 + dy**2 + dz**2) * 111000  # Convert to meters (approx)
            distances.append(dist)
        
        # Keep points where distance exceeds threshold
        optimized = [points[0]]
        current_distance = 0.0
        
        for i, dist in enumerate(distances):
            if current_distance + dist > max_distance:
                # Add point at this location
                optimized.append(points[i+1])
                current_distance = 0.0
            else:
                current_distance += dist
        
        # Ensure last point is included
        if len(optimized) < len(points):
            optimized.append(points[-1])
        
        print(f"[PathVisualizer] LOD optimization: {len(points)} -> {len(optimized)} points")
        return optimized
    
    def get_path_statistics(self, points: List[Dict[str, float]]) -> Dict[str, float]:
        """Calculate path statistics for analysis."""
        if not points or len(points) < 2:
            return {"distance_km": 0.0, "max_altitude": 0.0, "min_altitude": 0.0}
        
        lats = np.array([p["latitude"] for p in points])
        lons = np.array([p["longitude"] for p in points])
        alts = np.array([p["altitude"] for p in points])
        
        # Calculate distance (simplified)
        distances = []
        for i in range(len(points) - 1):
            dx = lats[i+1] - lats[i]
            dy = lons[i+1] - lons[i]
            dz = alts[i+1] - alts[i]
            dist = np.sqrt(dx**2 + dy**2 + dz**2) * 111000  # meters
            distances.append(dist)
        
        total_distance_km = sum(distances) / 1000
        
        return {
            "distance_km": float(total_distance_km),
            "max_altitude": float(max(alts)),
            "min_altitude": float(min(alts)),
            "point_count": len(points),
        }
    
    def update_layer_style(
        self, 
        layer_index: int, 
        color: Optional[Tuple[float, float, float]] = None,
        width: Optional[float] = None,
        opacity: Optional[float] = None,
    ):
        """Update visual style of a path layer."""
        if 0 <= layer_index < len(self.visualization.layers):
            layer = self.visualization.layers[layer_index]
            
            if color is not None:
                layer.color = color
            if width is not None:
                layer.width = width
            if opacity is not None:
                layer.opacity = opacity
            
            print(f"[PathVisualizer] Updated layer {layer_index}: color={color}, width={width}, opacity={opacity}")
    
    def toggle_layer_visibility(self, layer_index: int) -> bool:
        """Toggle visibility of a path layer."""
        if 0 <= layer_index < len(self.visualization.layers):
            self.visualization.layers[layer_index].is_active = not self.visualization.layers[layer_index].is_active
            return True
        return False
    
    def get_visualization_state(self) -> Dict[str, Any]:
        """Get complete visualization state for export/serialization."""
        return {
            "primary_path": self.visualization.primary_path,
            "secondary_paths": [p for p in self.visualization.secondary_paths],
            "planned_path": self.visualization.planned_path,
            "annotations": [a.to_dict() for a in self.visualization.annotations],
            "layers": [l.to_dict() for l in self.visualization.layers],
        }
    
    def load_visualization_state(self, state: Dict[str, Any]) -> bool:
        """Load visualization state from dictionary."""
        try:
            if state.get("primary_path"):
                self.add_primary_path(state["primary_path"])
            
            for path in state.get("secondary_paths", []):
                self.add_secondary_path(path)
            
            if state.get("planned_path"):
                self.add_planned_path(state["planned_path"])
            
            for annotation_data in state.get("annotations", []):
                annotation = PathAnnotation(
                    latitude=annotation_data["latitude"],
                    longitude=annotation_data["longitude"],
                    altitude=annotation_data["altitude"],
                    text=annotation_data["text"],
                )
                self.add_annotation(annotation)
            
            return True
        except Exception as e:
            print(f"[PathVisualizer] Error loading state: {e}")
            return False
    
    def reset(self):
        """Clear all paths and annotations."""
        self.visualization = PathVisualization()
        self._interpolation_cache.clear()
        print("[PathVisualizer] All paths and annotations cleared")


# Performance benchmarking utilities
def benchmark_path_rendering(
    num_points: int, 
    iterations: int = 10,
) -> Dict[str, float]:
    """Benchmark path rendering performance."""
    import time
    
    # Generate test data
    points = [{"latitude": i % 360, "longitude": (i * 2) % 360, "altitude": 500 + (i % 100)} 
              for i in range(num_points)]
    
    visualizer = PathVisualizer()
    
    # Warm-up
    for _ in range(3):
        interpolated = visualizer.get_interpolated_path(points, num_points)
    
    # Benchmark interpolation
    start_time = time.time()
    total_interpolation_time = 0.0
    
    for i in range(iterations):
        interpolated = visualizer.get_interpolated_path(points, num_points)
        elapsed = (time.time() - start_time) * 1000  # ms
        total_interpolation_time += elapsed
    
    avg_interpolation_ms = total_interpolation_time / iterations
    
    # Benchmark LOD optimization
    start_time = time.time()
    optimized = visualizer.get_optimized_points(points, max_distance=50.0)
    lod_time = (time.time() - start_time) * 1000
    
    return {
        "num_points": num_points,
        "iterations": iterations,
        "avg_interpolation_ms": avg_interpolation_ms,
        "lod_optimization_ms": lod_time,
        "optimized_point_count": len(optimized),
        "fps_estimate": 1000 / (avg_interpolation_ms + lod_time) if (avg_interpolation_ms + lod_time) > 0 else 0,
    }


# Example usage and demonstration
if __name__ == "__main__":
    print("=" * 60)
    print("Path Visualizer Demo")
    print("=" * 60)
    
    # Create visualizer
    visualizer = PathVisualizer()
    
    # Generate sample path (disaster response scenario)
    num_points = 100
    points = [
        {"latitude": 35.0 + i * 0.01, "longitude": -120.0 + i * 0.01, "altitude": 500 + (i % 200)}
        for i in range(num_points)
    ]
    
    # Add primary path
    visualizer.add_primary_path(points)
    
    # Get statistics
    stats = visualizer.get_path_statistics(points)
    print(f"\nPath Statistics:")
    print(f"  Distance: {stats['distance_km']:.2f} km")
    print(f"  Altitude Range: {stats['min_altitude']} - {stats['max_altitude']} m")
    
    # Test LOD optimization
    optimized = visualizer.get_optimized_points(points, max_distance=100.0)
    print(f"\nLOD Optimization:")
    print(f"  Original points: {len(points)}")
    print(f"  Optimized points: {len(optimized)}")
    
    # Test interpolation
    interpolated = visualizer.get_interpolated_path(points, num_points=500)
    print(f"\nInterpolation:")
    print(f"  Generated {len(interpolated)} interpolated points")
    
    # Benchmark performance
    print("\nPerformance Benchmark:")
    benchmark_results = benchmark_path_rendering(num_points=num_points, iterations=10)
    for key, value in benchmark_results.items():
        print(f"  {key}: {value:.2f}")
    
    # Get visualization state
    state = visualizer.get_visualization_state()
    print(f"\nVisualization State:")
    print(f"  Primary path points: {len(state['primary_path'])}")
    print(f"  Annotations: {len(state['annotations'])}")
    
    print("\nDemo complete!")
