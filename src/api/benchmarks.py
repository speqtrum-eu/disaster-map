"""
Performance Benchmarks and Optimization Notes for Disaster Map API
"""

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass

import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """Results from a performance benchmark."""
    name: str
    iterations: int
    total_time: float
    avg_time: float
    min_time: float
    max_time: float
    throughput: Optional[float] = None  # items per second


# ============================================================================
# Benchmark Setup
# ============================================================================

def setup_benchmark_environment():
    """Setup and validate benchmark environment."""
    results_dir = Path(__file__).parent.parent / "results" / "demo_20260920_230738"
    
    # Check demo files exist
    trajectory_file = results_dir / "poses" / "trajectory.json"
    ply_file = results_dir / "maps" / "pointcloud.ply"
    
    return {
        'results_dir': str(results_dir),
        'trajectory_exists': trajectory_file.exists(),
        'ply_exists': ply_file.exists()
    }


# ============================================================================
# Trajectory Loading Benchmarks
# ============================================================================

def benchmark_trajectory_loading(file_path: Optional[str] = None):
    """Benchmark trajectory JSON loading performance."""
    from src.api.data_processing import load_ply_points
    
    path = Path(file_path) if file_path else (Path(__file__).parent.parent / 
                                              "results" / "demo_20260920_230738" / 
                                              "poses" / "trajectory.json")
    
    if not path.exists():
        raise FileNotFoundError(f"Trajectory file not found: {path}")
    
    # Load data once for reference
    with open(path) as f:
        data = json.load(f)
    
    num_poses = len(data.get('poses', data))
    
    results = []
    
    # Test 1: JSON parsing time
    logger.info(f"Test 1: JSON Parsing ({num_poses} poses)")
    iterations = 100
    
    times = []
    for i in range(iterations):
        start = time.perf_counter()
        with open(path) as f:
            json.load(f)
        elapsed = (time.perf_counter() - start) * 1000  # ms
        
        times.append(elapsed)
    
    result = BenchmarkResult(
        name="JSON Parsing",
        iterations=iterations,
        total_time=sum(times),
        avg_time=np.mean(times),
        min_time=min(times),
        max_time=max(times),
        throughput=num_poses / (np.mean(times) / 1000)  # poses per ms
    )
    results.append(result)
    
    logger.info(f"  Avg: {result.avg_time:.3f}ms, Min: {result.min_time:.3f}ms, "
                f"Max: {result.max_time:.3f}ms")
    
    # Test 2: Pose extraction time
    logger.info(f"\nTest 2: Pose Extraction ({num_poses} poses)")
    times = []
    
    for i in range(iterations):
        start = time.perf_counter()
        
        poses = []
        for pose_data in data.get('poses', data)[:100]:  # Sample first 100
            if isinstance(pose_data, dict):
                x = pose_data.get('x', 0)
                y = pose_data.get('y', 0)
                z = pose_data.get('z', 0)
            else:
                x = float(pose_data[1]) if len(pose_data) > 1 else 0
                y = float(pose_data[2]) if len(pose_data) > 2 else 0
                z = float(pose_data[3]) if len(pose_data) > 3 else 0
            
            poses.append((x, y, z))
        
        elapsed = (time.perf_counter() - start) * 1000
        times.append(elapsed)
    
    result = BenchmarkResult(
        name="Pose Extraction",
        iterations=iterations,
        total_time=sum(times),
        avg_time=np.mean(times),
        min_time=min(times),
        max_time=max(times),
        throughput=num_poses / (np.mean(times) / 1000)
    )
    results.append(result)
    
    logger.info(f"  Avg: {result.avg_time:.3f}ms, Min: {result.min_time:.3f}ms")
    
    return results


# ============================================================================
# Point Cloud Loading Benchmarks
# ============================================================================

def benchmark_pointcloud_loading(file_path: Optional[str] = None):
    """Benchmark PLY point cloud loading performance."""
    from src.api.data_processing import load_ply_points, get_pointcloud_stats
    
    path = Path(file_path) if file_path else (Path(__file__).parent.parent / 
                                              "results" / "demo_20260920_230738" / 
                                              "maps" / "pointcloud.ply")
    
    if not path.exists():
        raise FileNotFoundError(f"PLY file not found: {path}")
    
    stats = get_pointcloud_stats(path)
    num_points = stats.count
    
    results = []
    
    # Test 1: Header parsing time
    logger.info(f"Test 1: PLY Header Parsing ({num_points} points)")
    iterations = 50
    
    times = []
    for i in range(iterations):
        start = time.perf_counter()
        
        from src.api.data_processing import parse_ply_header
        parse_ply_header(path)
        
        elapsed = (time.perf_counter() - start) * 1000
        times.append(elapsed)
    
    result = BenchmarkResult(
        name="Header Parsing",
        iterations=iterations,
        total_time=sum(times),
        avg_time=np.mean(times),
        min_time=min(times),
        max_time=max(times)
    )
    results.append(result)
    
    logger.info(f"  Avg: {result.avg_time:.3f}ms")
    
    # Test 2: Point loading time (memory-mapped)
    if num_points > 1000:
        logger.info(f"\nTest 2: Point Loading with Memory Mapping ({num_points:,} points)")
        
        times = []
        for i in range(iterations):
            start = time.perf_counter()
            
            positions, colors = load_ply_points(path, use_mmap=True)
            
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)
        
        result = BenchmarkResult(
            name="Point Loading (mmap)",
            iterations=iterations,
            total_time=sum(times),
            avg_time=np.mean(times),
            min_time=min(times),
            max_time=max(times),
            throughput=num_points / (np.mean(times) / 1000)  # points per ms
        )
        results.append(result)
        
        logger.info(f"  Avg: {result.avg_time:.3f}ms, Throughput: {result.throughput:.2f} pts/ms")
    
    return results


# ============================================================================
# API Endpoint Benchmarks
# ============================================================================

def benchmark_api_endpoints():
    """Benchmark API endpoint response times."""
    import httpx
    
    # Start FastAPI server in background for testing
    from src.api.server import app, TRAJECTORY_FILE
    
    async def run_endpoint_benchmarks():
        results = []
        
        # Test /api/trajectory endpoint
        logger.info("Benchmarking /api/trajectory endpoint")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            times = []
            
            for i in range(20):
                start = time.perf_counter()
                response = await client.get("/api/trajectory")
                elapsed = (time.perf_counter() - start) * 1000
                
                if response.status_code == 200:
                    times.append(elapsed)
            
            avg_time = np.mean(times)
            result = BenchmarkResult(
                name="/api/trajectory",
                iterations=20,
                total_time=sum(times),
                avg_time=avg_time,
                min_time=min(times),
                max_time=max(times),
                throughput=1 / (avg_time / 1000)  # requests per second
            )
            results.append(result)
            
            logger.info(f"  Avg: {result.avg_time:.3f}ms, Throughput: {result.throughput:.2f} req/s")
        
        return results
    

# ============================================================================
# Memory Usage Benchmarks
# ============================================================================

def benchmark_memory_usage(file_path: Optional[str] = None):
    """Benchmark memory usage for data loading."""
    import psutil
    
    path = Path(file_path) if file_path else (Path(__file__).parent.parent / 
                                              "results" / "demo_20260920_230738" / 
                                              "maps" / "pointcloud.ply")
    
    if not path.exists():
        raise FileNotFoundError(f"PLY file not found: {path}")
    
    stats = get_pointcloud_stats(path)
    num_points = stats.count
    
    results = []
    
    # Test 1: Memory for positions array
    logger.info("Test 1: Positions Array Memory")
    
    positions, colors = load_ply_points(path)
    
    memory_mb = psutil.Process().memory_info().rss / (1024 * 1024)
    
    result = BenchmarkResult(
        name="Positions Array",
        iterations=1,
        total_time=time.perf_counter(),
        avg_time=time.perf_counter(),
        min_time=time.perf_counter(),
        max_time=time.perf_counter(),
        throughput=num_points / memory_mb  # points per MB
    )
    results.append(result)
    
    logger.info(f"  Memory: {memory_mb:.2f} MB, Points/MB: {result.throughput:.1f}")
    
    return results


# ============================================================================
# Optimization Recommendations
# ============================================================================

def generate_optimization_report(benchmark_results: List[BenchmarkResult]):
    """Generate optimization recommendations based on benchmark results."""
    report = []
    
    # General recommendations
    report.append("=" * 60)
    report.append("DISASTER MAP API - OPTIMIZATION REPORT")
    report.append("=" * 60)
    
    # Analyze trajectory loading
    traj_results = [r for r in benchmark_results if "Trajectory" in r.name]
    if traj_results:
        avg_time = np.mean([r.avg_time for r in traj_results])
        
        if avg_time < 10:
            report.append("\n✓ Trajectory Loading: EXCELLENT")
            report.append(f"  Average time: {avg_time:.3f}ms (target: <50ms)")
        elif avg_time < 50:
            report.append("\n⚠ Trajectory Loading: GOOD")
            report.append(f"  Average time: {avg_time:.3f}ms (target: <50ms)")
            report.append("  Recommendation: Consider JSON compression for large files")
        else:
            report.append("\n✗ Trajectory Loading: NEEDS OPTIMIZATION")
            report.append(f"  Average time: {avg_time:.3f}ms (target: <50ms)")
    
    # Analyze point cloud loading
    pc_results = [r for r in benchmark_results if "Point" in r.name]
    if pc_results:
        avg_time = np.mean([r.avg_time for r in pc_results])
        
        if avg_time < 100:
            report.append("\n✓ Point Cloud Loading: EXCELLENT")
            report.append(f"  Average time: {avg_time:.3f}ms (target: <200ms)")
        elif avg_time < 500:
            report.append("\n⚠ Point Cloud Loading: ACCEPTABLE")
            report.append(f"  Average time: {avg_time:.3f}ms (target: <200ms)")
            report.append("  Recommendation: Use memory-mapped I/O for files >10MB")
        else:
            report.append("\n✗ Point Cloud Loading: NEEDS OPTIMIZATION")
            report.append(f"  Average time: {avg_time:.3f}ms (target: <200ms)")
    
    # API endpoint recommendations
    api_results = [r for r in benchmark_results if "/" in r.name and "api" in r.name]
    if api_results:
        avg_time = np.mean([r.avg_time for r in api_results])
        
        if avg_time < 100:
            report.append("\n✓ API Endpoints: EXCELLENT")
            report.append(f"  Average response time: {avg_time:.3f}ms (target: <100ms)")
        elif avg_time < 500:
            report.append("\n⚠ API Endpoints: ACCEPTABLE")
            report.append(f"  Average response time: {avg_time:.3f}ms (target: <100ms)")
            report.append("  Recommendation: Implement caching for static data")
        else:
            report.append("\n✗ API Endpoints: NEEDS OPTIMIZATION")
            report.append(f"  Average response time: {avg_time:.3f}ms (target: <100ms)")
    
    # General optimization recommendations
    report.append("\n" + "=" * 60)
    report.append("OPTIMIZATION RECOMMENDATIONS")
    report.append("=" * 60)
    
    optimizations = [
        {
            "priority": "HIGH",
            "title": "Enable Response Compression",
            "description": "Add gzip compression to API responses for JSON data",
            "impact": "30-50% reduction in bandwidth usage"
        },
        {
            "priority": "HIGH",
            "title": "Implement Data Caching",
            "description": "Cache trajectory and waypoint data with Redis or in-memory cache",
            "impact": "90%+ reduction in repeated query times"
        },
        {
            "priority": "MEDIUM",
            "title": "Use Async I/O for File Operations",
            "description": "Replace synchronous file operations with async equivalents",
            "impact": "Better throughput under load"
        },
        {
            "priority": "MEDIUM",
            "title": "Implement Pagination for Large Datasets",
            "description": "Add pagination to point cloud and trajectory endpoints",
            "impact": "Faster initial response, client-side control"
        },
        {
            "priority": "LOW",
            "title": "Database Indexing",
            "description": "Add indexes on frequently queried fields in production database",
            "impact": "Faster queries for waypoint lookups"
        }
    ]
    
    for opt in optimizations:
        report.append(f"\n[{opt['priority']}] {opt['title']}")
        report.append(f"  {opt['description']}")
        report.append(f"  Expected impact: {opt['impact']}")
    
    # Performance targets summary
    report.append("\n" + "=" * 60)
    report.append("PERFORMANCE TARGETS SUMMARY")
    report.append("=" * 60)
    
    targets = [
        ("Trajectory loading", "<50ms", "JSON parsing and pose extraction"),
        ("Point cloud loading", "<200ms", "Memory-mapped I/O for large files"),
        ("API endpoint response", "<100ms", "With caching enabled"),
        ("WebSocket connection setup", "<100ms", "Initial handshake"),
        ("Real-time update delivery", "<50ms", "Per message latency")
    ]
    
    for name, target, description in targets:
        report.append(f"\n{name}: {target}")
        report.append(f"  Description: {description}")
    
    return "\n".join(report)


# ============================================================================
# Main Benchmark Runner
# ============================================================================

def run_all_benchmarks():
    """Run all benchmarks and generate report."""
    print("\n" + "=" * 60)
    print("DISASTER MAP API - PERFORMANCE BENCHMARKS")
    print("=" * 60 + "\n")
    
    # Setup environment
    env = setup_benchmark_environment()
    print(f"Environment: {env['results_dir']}")
    print(f"Trajectory file: {'✓' if env['trajectory_exists'] else '✗'}")
    print(f"PLY file: {'✓' if env['ply_exists'] else '✗'}\n")
    
    all_results = []
    
    # Run benchmarks
    if env['trajectory_exists']:
        results = benchmark_trajectory_loading()
        all_results.extend(results)
    
    if env['ply_exists']:
        results = benchmark_pointcloud_loading()
        all_results.extend(results)
    
    # Memory benchmarks
    print("\n" + "-" * 60)
    print("MEMORY USAGE BENCHMARKS")
    print("-" * 60)
    
    if env['ply_exists']:
        memory_results = benchmark_memory_usage()
        all_results.extend(memory_results)
    
    # API benchmarks (requires running server)
    print("\n" + "-" * 60)
    print("API ENDPOINT BENCHMARKS")
    print("-" * 60)
    
    try:
        api_results = benchmark_api_endpoints()
        all_results.extend(api_results)
    except Exception as e:
        logger.warning(f"Could not run API benchmarks: {e}")
    
    # Generate report
    print("\n")
    report = generate_optimization_report(all_results)
    print(report)
    
    return all_results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run performance benchmarks")
    parser.add_argument("--api", action="store_true", 
                       help="Include API endpoint benchmarks (requires server)")
    parser.add_argument("--json", action="store_true",
                       help="Output results as JSON")
    
    args = parser.parse_args()
    
    if args.json:
        import json
        
        results = run_all_benchmarks()
        
        # Convert to serializable format
        output = {
            "benchmarks": [
                {
                    "name": r.name,
                    "avg_time_ms": round(r.avg_time, 3),
                    "min_time_ms": round(r.min_time, 3),
                    "max_time_ms": round(r.max_time, 3),
                    "throughput": round(r.throughput, 2) if r.throughput else None
                }
                for r in results
            ]
        }
        
        print(json.dumps(output, indent=2))
    else:
        run_all_benchmarks()
