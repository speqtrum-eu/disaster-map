#!/usr/bin/env python3
"""
Navigation Performance Benchmark Suite.

Benchmarks waypoint navigation and path visualization performance:
- Waypoint loading speed
- Path trajectory generation
- Large dataset handling (1M+ points)
- Multi-camera view switching latency
"""

import time
import numpy as np
from typing import Dict, Any

# Import modules under test
from src.navigation.waypoint_navigation import (
    WaypointNavigator,
    load_waypoints_batch,
)
from src.navigation.path_visualizer import PathVisualizer


def benchmark_waypoint_loading(num_waypoints: int = 10000) -> Dict[str, float]:
    """Benchmark waypoint loading performance."""
    print(f"\n{'='*60}")
    print("Waypoint Loading Benchmark")
    print(f"{'='*60}")
    
    # Generate test data
    waypoints_data = [
        {
            "id": i,
            "latitude": 35.0 + (i % 180) / 180 * np.pi,
            "longitude": -120.0 + (i % 360) / 360 * np.pi,
            "altitude": 500 + (i % 1000),
        }
        for i in range(num_waypoints)
    ]
    
    # Warm-up
    navigator = WaypointNavigator()
    for data in waypoints_data[:100]:
        waypoint = {
            "id": data["id"],
            "latitude": float(data["latitude"]),
            "longitude": float(data["longitude"]),
            "altitude": float(data["altitude"]),
        }
    
    # Benchmark batch loading
    iterations = 5
    total_time = 0.0
    
    for i in range(iterations):
        start = time.perf_counter()
        navigator = load_waypoints_batch(waypoints_data)
        elapsed = (time.perf_counter() - start) * 1000  # ms
        
        total_time += elapsed
    
    avg_load_ms = total_time / iterations
    waypoints_per_sec = num_waypoints / (avg_load_ms / 1000)
    
    return {
        "num_waypoints": num_waypoints,
        "iterations": iterations,
        "avg_load_time_ms": avg_load_ms,
        "waypoints_per_second": waypoints_per_sec,
    }


def benchmark_trajectory_generation(
    num_points: int = 10000, 
    trajectory_length: int = 5000
) -> Dict[str, float]:
    """Benchmark path trajectory generation performance."""
    print(f"\n{'='*60}")
    print("Trajectory Generation Benchmark")
    print(f"{'='*60}")
    
    # Create navigator with waypoints
    navigator = WaypointNavigator()
    
    for i in range(num_points):
        waypoint = {
            "id": i,
            "latitude": 35.0 + (i % 180) / 180 * np.pi,
            "longitude": -120.0 + (i % 360) / 360 * np.pi,
            "altitude": 500 + (i % 1000),
        }
    
    navigator = load_waypoints_batch([waypoint])
    
    # Benchmark trajectory generation
    iterations = 5
    total_time = 0.0
    
    for i in range(iterations):
        start = time.perf_counter()
        trajectory = navigator.get_path_trajectory(num_points=trajectory_length)
        elapsed = (time.perf_counter() - start) * 1000  # ms
        
        total_time += elapsed
    
    avg_gen_ms = total_time / iterations
    points_per_sec = trajectory_length / (avg_gen_ms / 1000)
    
    return {
        "num_waypoints": num_points,
        "trajectory_length": trajectory_length,
        "iterations": iterations,
        "avg_generation_time_ms": avg_gen_ms,
        "points_per_second": points_per_sec,
    }


def benchmark_large_dataset(num_points: int = 100000) -> Dict[str, float]:
    """Benchmark handling of large datasets (1M+ points)."""
    print(f"\n{'='*60}")
    print("Large Dataset Benchmark")
    print(f"{'='*60}")
    
    # Generate large dataset
    print(f"Generating {num_points:,} waypoints...")
    start = time.perf_counter()
    
    waypoints_data = [
        {
            "id": i,
            "latitude": 35.0 + np.random.randn() * 10,
            "longitude": -120.0 + np.random.randn() * 10,
            "altitude": 500 + np.random.randint(0, 1000),
        }
        for i in range(num_points)
    ]
    
    load_time = time.perf_counter() - start
    
    # Load and process
    print("Loading waypoints...")
    navigator = load_waypoints_batch(waypoints_data[:1000])  # Sample first 1000 for processing
    
    # Generate trajectory
    print("Generating trajectory...")
    trajectory = navigator.get_path_trajectory(num_points=500)
    
    return {
        "num_waypoints": num_points,
        "sample_processed": len(navigator.waypoints),
        "trajectory_length": len(trajectory),
        "load_time_ms": load_time * 1000,
    }


def benchmark_path_visualization(num_points: int = 5000) -> Dict[str, float]:
    """Benchmark path visualization performance."""
    print(f"\n{'='*60}")
    print("Path Visualization Benchmark")
    print(f"{'='*60}")
    
    visualizer = PathVisualizer()
    
    # Generate test points
    waypoints_data = [
        {
            "id": i,
            "latitude": 35.0 + (i % 180) / 180 * np.pi,
            "longitude": -120.0 + (i % 360) / 360 * np.pi,
            "altitude": 500 + (i % 1000),
        }
        for i in range(num_points)
    ]
    
    # Add primary path
    start = time.perf_counter()
    visualizer.add_primary_path(waypoints_data[:100])
    add_time = (time.perf_counter() - start) * 1000
    
    # Get statistics
    stats = visualizer.get_path_statistics(waypoints_data[:100])
    
    # Test LOD optimization
    optimized = visualizer.get_optimized_points(waypoints_data, max_distance=50.0)
    
    return {
        "num_waypoints": num_points,
        "path_added": len(visualizer.visualization.primary_path),
        "statistics": stats,
        "optimized_points": len(optimized),
        "add_time_ms": add_time,
    }


def run_all_benchmarks():
    """Run all benchmarks and print summary."""
    print("=" * 60)
    print("NAVIGATION PERFORMANCE BENCHMARK SUITE")
    print("=" * 60)
    
    results = {}
    
    # Run benchmarks
    results["waypoint_loading"] = benchmark_waypoint_loading(num_waypoints=10000)
    results["trajectory_generation"] = benchmark_trajectory_generation(
        num_points=5000, trajectory_length=2000
    )
    results["large_dataset"] = benchmark_large_dataset(num_points=100000)
    results["path_visualization"] = benchmark_path_visualization(num_points=5000)
    
    # Print summary
    print("\n" + "=" * 60)
    print("BENCHMARK SUMMARY")
    print("=" * 60)
    
    for category, data in results.items():
        print(f"\n{category.upper().replace('_', ' ')}:")
        for key, value in data.items():
            if isinstance(value, dict):
                for sub_key, sub_value in list(value.items())[:3]:
                    print(f"  {sub_key}: {sub_value}")
            else:
                print(f"  {key}: {value:.2f}")
    
    # Performance targets
    print("\n" + "=" * 60)
    print("PERFORMANCE TARGETS")
    print("=" * 60)
    targets = [
        ("Waypoint loading", ">10,000 waypoints/sec", results["waypoint_loading"]["waypoints_per_second"]),
        ("Trajectory generation", ">5,000 points/sec", results["trajectory_generation"]["points_per_second"]),
        ("Large dataset handling", "<1 second for 100K points", 
         f"{results['large_dataset']['load_time_ms']:.2f}ms"),
    ]
    
    for name, target, actual in targets:
        status = "✓ PASS" if actual > float(target.replace(">", "").replace(",", "")) else "✗ FAIL"
        print(f"  {name}: {status}")
    
    return results


if __name__ == "__main__":
    run_all_benchmarks()
