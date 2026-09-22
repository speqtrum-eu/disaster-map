"""
Performance Benchmarks for Disaster Map System.
Measures FPS, latency, and memory usage under various conditions.
"""

import time
import json
import tracemalloc
from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np


class PerformanceBenchmark:
    """Main benchmark class for performance testing."""

    def __init__(self):
        self.results: Dict[str, Dict] = {}
        self.baseline_fps = 0.0
        self.baseline_latency = 0.0
        self.baseline_memory = 0

    def measure_fps(self, duration_seconds: float = 5.0) -> Tuple[float, List[float]]:
        """Measure frames per second over a given duration."""
        frame_count = 0
        timestamps = []
        
        start_time = time.time()
        
        while time.time() - start_time < duration_seconds:
            # Simulate frame processing (replace with actual frame processing)
            timestamp = time.time()
            timestamps.append(timestamp)
            
            if len(timestamps) > 1:
                delta = timestamps[-1] - timestamps[-2]
                fps = 1.0 / delta if delta > 0 else 0.0
                frame_count += 1
            
            # Simulate some processing work
            _ = np.random.rand(100, 100)

        elapsed_time = time.time() - start_time
        
        avg_fps = frame_count / elapsed_time if elapsed_time > 0 else 0.0
        return avg_fps, timestamps

    def measure_latency(self, num_samples: int = 100) -> Tuple[float, List[float]]:
        """Measure end-to-end latency in milliseconds."""
        latencies = []
        
        for _ in range(num_samples):
            # Start timing
            start_time = time.perf_counter()
            
            # Simulate processing pipeline (replace with actual processing)
            _ = np.random.rand(50, 50)
            time.sleep(0.01)  # Simulate some I/O latency
            
            # End timing
            end_time = time.perf_counter()
            
            latency_ms = (end_time - start_time) * 1000
            latencies.append(latency_ms)

        avg_latency = np.mean(latencies)
        min_latency = np.min(latencies)
        max_latency = np.max(latencies)
        
        return avg_latency, latencies

    def measure_memory(self, operation: callable) -> Tuple[int, int]:
        """Measure memory usage before and after an operation."""
        tracemalloc.start()
        
        # Get baseline memory
        snapshot_before = tracemalloc.take_snapshot()
        self.baseline_memory = snapshot_before.statistics()[0].size if snapshot_before.statistics() else 0
        
        # Execute operation
        operation()
        
        # Get final memory
        snapshot_after = tracemalloc.take_snapshot()
        current, peak = tracemalloc.get_traced_memory()
        
        tracemalloc.stop()
        
        return int(current), int(peak)

    def benchmark_slam_processing(self, num_frames: int = 100) -> Dict[str, float]:
        """Benchmark SLAM processing performance."""
        print(f"\n{'='*60}")
        print("SLAM Processing Benchmark")
        print(f"{'='*60}")

        # Measure FPS during frame processing
        fps, _ = self.measure_fps(duration_seconds=10.0)
        
        # Measure latency per frame
        avg_latency, latencies = self.measure_latency(num_samples=num_frames)
        
        # Calculate memory usage
        def process_frame():
            import cv2
            # Simulate processing a frame (replace with actual processing)
            _ = np.random.rand(1080, 1920, 3).astype(np.uint8)

        current_mem, peak_mem = self.measure_memory(process_frame)

        results = {
            "fps": fps,
            "avg_latency_ms": avg_latency,
            "min_latency_ms": np.min(latencies),
            "max_latency_ms": np.max(latencies),
            "memory_current_mb": current_mem / (1024 * 1024),
            "memory_peak_mb": peak_mem / (1024 * 1024)
        }

        self.results["slam_processing"] = results
        
        print(f"FPS: {results['fps']:.2f}")
        print(f"Avg Latency: {results['avg_latency_ms']:.2f} ms")
        print(f"Min Latency: {results['min_latency_ms']:.2f} ms")
        print(f"Max Latency: {results['max_latency_ms']:.2f} ms")
        print(f"Memory (Current): {results['memory_current_mb']:.2f} MB")
        print(f"Memory (Peak): {results['memory_peak_mb']:.2f} MB")

        return results

    def benchmark_viewer_rendering(self, num_frames: int = 60) -> Dict[str, float]:
        """Benchmark web viewer rendering performance."""
        print(f"\n{'='*60}")
        print("Viewer Rendering Benchmark")
        print(f"{'='*60}")

        fps_samples = []
        
        # Simulate rendering loop (replace with actual rendering)
        for i in range(num_frames):
            start_time = time.perf_counter()
            
            # Simulate rendering work
            _ = np.random.rand(100, 100, 3)
            
            end_time = time.perf_counter()
            frame_time_ms = (end_time - start_time) * 1000
            
            fps = 1000.0 / frame_time_ms if frame_time_ms > 0 else 0.0
            fps_samples.append(fps)

        avg_fps = np.mean(fps_samples)
        min_fps = np.min(fps_samples)
        max_fps = np.max(fps_samples)

        results = {
            "avg_fps": avg_fps,
            "min_fps": min_fps,
            "max_fps": max_fps,
            "frame_time_ms": 1000.0 / avg_fps if avg_fps > 0 else 0
        }

        self.results["viewer_rendering"] = results
        
        print(f"Avg FPS: {results['avg_fps']:.2f}")
        print(f"Min FPS: {results['min_fps']:.2f}")
        print(f"Max FPS: {results['max_fps']:.2f}")
        print(f"Frame Time: {results['frame_time_ms']:.3f} ms")

        return results

    def benchmark_data_loading(self, file_path: str) -> Dict[str, float]:
        """Benchmark data loading performance."""
        print(f"\n{'='*60}")
        print("Data Loading Benchmark")
        print(f"{'='*60}")

        # Check if file exists (use demo files from results/demo_20260920_230738/)
        base_path = Path("/home/durburz/git/disaster-map/results/demo_20260920_230738/")
        
        # Test loading trajectory data
        trajectory_file = base_path / "poses" / "trajectory.json"
        
        if not trajectory_file.exists():
            print(f"Trajectory file not found: {trajectory_file}")
            return {}

        load_times = []
        
        for _ in range(10):  # Run multiple times for average
            start_time = time.perf_counter()
            
            # Load data (replace with actual loading)
            import json
            with open(trajectory_file, 'r') as f:
                data = json.load(f)

            end_time = time.perf_counter()
            load_time_ms = (end_time - start_time) * 1000
            load_times.append(load_time_ms)

        avg_load_time = np.mean(load_times)
        min_load_time = np.min(load_times)
        max_load_time = np.max(load_times)

        results = {
            "avg_load_time_ms": avg_load_time,
            "min_load_time_ms": min_load_time,
            "max_load_time_ms": max_load_time,
            "file_size_mb": trajectory_file.stat().st_size / (1024 * 1024)
        }

        self.results["data_loading"] = results
        
        print(f"Avg Load Time: {results['avg_load_time_ms']:.3f} ms")
        print(f"Min Load Time: {results['min_load_time_ms']:.3f} ms")
        print(f"Max Load Time: {results['max_load_time_ms']:.3f} ms")
        print(f"File Size: {results['file_size_mb']:.2f} MB")

        return results

    def benchmark_memory_stability(self, iterations: int = 10) -> Dict[str, float]:
        """Benchmark memory stability under repeated operations."""
        print(f"\n{'='*60}")
        print("Memory Stability Benchmark")
        print(f"{'='*60}")

        memory_samples = []
        
        for i in range(iterations):
            # Perform some operations
            _ = np.random.rand(100, 100)
            
            current_mem, peak_mem = self.measure_memory(lambda: None)
            memory_samples.append(current_mem / (1024 * 1024))

        avg_memory = np.mean(memory_samples)
        min_memory = np.min(memory_samples)
        max_memory = np.max(memory_samples)
        variance = np.var(memory_samples)

        results = {
            "avg_memory_mb": avg_memory,
            "min_memory_mb": min_memory,
            "max_memory_mb": max_memory,
            "variance_mb2": variance,
            "memory_leak_indicator": variance > 10.0  # High variance may indicate leak
        }

        self.results["memory_stability"] = results
        
        print(f"Avg Memory: {results['avg_memory_mb']:.2f} MB")
        print(f"Min Memory: {results['min_memory_mb']:.2f} MB")
        print(f"Max Memory: {results['max_memory_mb']:.2f} MB")
        print(f"Variance: {variance:.4f}")
        print(f"Memory Leak Indicator: {'WARNING' if results['memory_leak_indicator'] else 'OK'}")

        return results

    def run_all_benchmarks(self) -> Dict[str, Dict]:
        """Run all benchmarks and collect results."""
        print("=" * 60)
        print("DISASTER MAP PERFORMANCE BENCHMARKS")
        print("=" * 60)

        # Run all benchmarks
        self.benchmark_slam_processing()
        self.benchmark_viewer_rendering()
        self.benchmark_data_loading("/home/durburz/git/disaster-map/results/demo_20260920_230738/poses/trajectory.json")
        self.benchmark_memory_stability()

        return self.results

    def save_results(self, output_path: str = "benchmark_results.json"):
        """Save benchmark results to JSON file."""
        output_file = Path(output_path)
        
        # Add timestamp and summary
        results_with_metadata = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "summary": {
                "fps_target_met": self.results.get("slam_processing", {}).get("fps", 0) >= 30,
                "latency_target_met": self.results.get("slam_processing", {}).get("avg_latency_ms", float('inf')) <= 50,
                "memory_stable": not self.results.get("memory_stability", {}).get("memory_leak_indicator", True)
            },
            **self.results
        }

        with open(output_file, 'w') as f:
            json.dump(results_with_metadata, f, indent=2)

        print(f"\nResults saved to: {output_file}")


def main():
    """Main entry point for running benchmarks."""
    benchmark = PerformanceBenchmark()
    
    # Run all benchmarks
    results = benchmark.run_all_benchmarks()
    
    # Save results
    benchmark.save_results("benchmark_results.json")
    
    # Print summary
    print("\n" + "=" * 60)
    print("BENCHMARK SUMMARY")
    print("=" * 60)
    
    for category, data in results.items():
        print(f"\n{category.upper()}:")
        for key, value in data.items():
            if isinstance(value, float):
                print(f"  {key}: {value:.2f}")
            else:
                print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
