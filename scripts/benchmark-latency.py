#!/usr/bin/env python3
"""
Latency Benchmark Script for Data Pipeline.

Measures end-to-end latency across all pipeline stages:
- Frame extraction latency
- SLAM processing latency  
- Map update latency
- Total end-to-end latency

Usage:
    python scripts/benchmark-latency.py [--iterations N] [--target-ms 50]
"""

import argparse
import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
from statistics import mean, stdev


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """Results from a latency benchmark."""
    stage_name: str
    iterations: int
    avg_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    std_dev_ms: float
    passed: bool  # True if under target threshold


def percentile(data: List[float], p: float) -> float:
    """Calculate percentile value."""
    k = (len(data) - 1) * p / 100.0
    f = int(k)
    c = min(f + 1, len(data) - 1) if f < len(data) else f
    return data[f] + (k - f) * (data[c] - data[f])


class LatencyBenchmark:
    """Runs latency benchmarks on pipeline stages."""
    
    def __init__(self, target_ms: float = 50.0):
        self.target_ms = target_ms
        self.results: List[BenchmarkResult] = []
        
    async def benchmark_stage(
        self, 
        stage_name: str,
        iterations: int = 100,
        process_func: Optional[Callable[[], None]] = None
    ) -> BenchmarkResult:
        """
        Benchmark a pipeline stage.
        
        Args:
            stage_name: Name of the stage being benchmarked
            iterations: Number of measurements to take
            process_func: Function to execute for each measurement
            
        Returns:
            BenchmarkResult with latency statistics
        """
        logger.info(f"Benchmarking {stage_name} ({iterations} iterations)")
        
        latencies = []
        
        for i in range(iterations):
            # Measure latency for this iteration
            start_time = time.perf_counter()
            
            try:
                if process_func:
                    await asyncio.get_event_loop().run_in_executor(
                        None, 
                        lambda: process_func()
                    )
                
            except Exception as e:
                logger.warning(f"Iteration {i+1}/{iterations} error: {e}")
                continue
            
            end_time = time.perf_counter()
            
            latency_ms = (end_time - start_time) * 1000
            latencies.append(latency_ms)
        
        if not latencies:
            logger.error(f"No valid measurements for {stage_name}")
            return BenchmarkResult(
                stage_name=stage_name,
                iterations=iterations,
                avg_latency_ms=0.0,
                min_latency_ms=0.0,
                max_latency_ms=0.0,
                p50_ms=0.0,
                p95_ms=0.0,
                p99_ms=0.0,
                std_dev_ms=0.0,
                passed=False,
            )
        
        # Calculate statistics
        avg_latency = mean(latencies)
        min_latency = min(latencies)
        max_latency = max(latencies)
        std_dev = stdev(latencies) if len(latencies) > 1 else 0.0
        
        sorted_latencies = sorted(latencies)
        
        result = BenchmarkResult(
            stage_name=stage_name,
            iterations=len(latencies),
            avg_latency_ms=round(avg_latency, 3),
            min_latency_ms=round(min_latency, 3),
            max_latency_ms=round(max_latency, 3),
            p50_ms=round(percentile(sorted_latencies, 50), 3),
            p95_ms=round(percentile(sorted_latencies, 95), 3),
            p99_ms=round(percentile(sorted_latencies, 99), 3),
            std_dev_ms=round(std_dev, 3),
            passed=avg_latency < self.target_ms,
        )
        
        self.results.append(result)
        
        logger.info(
            f"{stage_name}: avg={result.avg_latency_ms:.2f}ms, "
            f"min={result.min_latency_ms:.2f}ms, max={result.max_latency_ms:.2f}ms, "
            f"P95={result.p95_ms:.2f}ms | {'✓ PASS' if result.passed else '✗ FAIL'}"
        )
        
        return result
    
    async def benchmark_end_to_end(
        self, 
        iterations: int = 100,
        pipeline_func: Optional[Callable[[], None]] = None
    ) -> BenchmarkResult:
        """
        Benchmark complete end-to-end pipeline.
        
        Args:
            iterations: Number of measurements to take
            pipeline_func: Function representing full pipeline
            
        Returns:
            BenchmarkResult with total latency statistics
        """
        logger.info(f"Benchmarking end-to-end pipeline ({iterations} iterations)")
        
        latencies = []
        
        for i in range(iterations):
            start_time = time.perf_counter()
            
            try:
                if pipeline_func:
                    await asyncio.get_event_loop().run_in_executor(
                        None, 
                        lambda: pipeline_func()
                    )
                
            except Exception as e:
                logger.warning(f"Iteration {i+1}/{iterations} error: {e}")
                continue
            
            end_time = time.perf_counter()
            
            latency_ms = (end_time - start_time) * 1000
            latencies.append(latency_ms)
        
        if not latencies:
            return BenchmarkResult(
                stage_name="end_to_end",
                iterations=iterations,
                avg_latency_ms=0.0,
                min_latency_ms=0.0,
                max_latency_ms=0.0,
                p50_ms=0.0,
                p95_ms=0.0,
                p99_ms=0.0,
                std_dev_ms=0.0,
                passed=False,
            )
        
        avg_latency = mean(latencies)
        min_latency = min(latencies)
        max_latency = max(latencies)
        sorted_latencies = sorted(latencies)
        
        result = BenchmarkResult(
            stage_name="end_to_end",
            iterations=len(latencies),
            avg_latency_ms=round(avg_latency, 3),
            min_latency_ms=round(min_latency, 3),
            max_latency_ms=round(max_latency, 3),
            p50_ms=round(percentile(sorted_latencies, 50), 3),
            p95_ms=round(percentile(sorted_latencies, 95), 3),
            p99_ms=round(percentile(sorted_latencies, 99), 3),
            std_dev_ms=0.0,
            passed=avg_latency < self.target_ms,
        )
        
        self.results.append(result)
        
        logger.info(
            f"End-to-End: avg={result.avg_latency_ms:.2f}ms, "
            f"P95={result.p95_ms:.2f}ms | {'✓ PASS' if result.passed else '✗ FAIL'}"
        )
        
        return result
    
    def print_summary(self) -> None:
        """Print benchmark summary."""
        logger.info("=" * 80)
        logger.info("LATENCY BENCHMARK SUMMARY")
        logger.info("=" * 80)
        
        for result in self.results:
            status = "✓ PASS" if result.passed else "✗ FAIL"
            logger.info(
                f"\n{result.stage_name}:"
                f" avg={result.avg_latency_ms:.2f}ms | {status}"
            )
        
        # Calculate overall success rate
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        success_rate = (passed / max(1, total)) * 100
        
        logger.info("\n" + "=" * 80)
        logger.info(f"OVERALL: {passed}/{total} stages passed ({success_rate:.1f}%)")
        
        # Check if target was met
        all_passed = all(r.passed for r in self.results)
        logger.info("=" * 80)
        
        return all_passed


# ============================================================================
# Example Pipeline Stages (for demonstration)
# ============================================================================

async def example_frame_extraction():
    """Example frame extraction stage."""
    # Simulate frame extraction from RTSP/RTMP stream
    import time
    
    start = time.perf_counter()
    
    # Simulate network I/O and decoding
    await asyncio.sleep(0.01)  # ~10ms simulated latency
    
    return (time.perf_counter() - start) * 1000


async def example_slam_processing():
    """Example SLAM processing stage."""
    import time
    
    start = time.perf_counter()
    
    # Simulate feature extraction and pose calculation
    await asyncio.sleep(0.02)  # ~20ms simulated latency
    
    return (time.perf_counter() - start) * 1000


async def example_map_update():
    """Example map update stage."""
    import time
    
    start = time.perf_counter()
    
    # Simulate point cloud insertion and memory management
    await asyncio.sleep(0.015)  # ~15ms simulated latency
    
    return (time.perf_counter() - start) * 1000


async def example_full_pipeline():
    """Example complete pipeline."""
    import time
    
    start = time.perf_counter()
    
    await asyncio.gather(
        example_frame_extraction(),
        example_slam_processing(),
        example_map_update(),
    )
    
    return (time.perf_counter() - start) * 1000


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Latency Benchmark for Data Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default settings (50ms target)
  python scripts/benchmark-latency.py
  
  # Run with custom iterations and target
  python scripts/benchmark-latency.py --iterations 200 --target-ms 30
  
  # Benchmark specific stages only
  python scripts/benchmark-latency.py --stages frame_extraction,slam_processing
        """
    )
    
    parser.add_argument(
        "--iterations", "-i",
        type=int,
        default=100,
        help="Number of iterations per benchmark (default: 100)"
    )
    
    parser.add_argument(
        "--target-ms", "-t",
        type=float,
        default=50.0,
        help="Target latency in milliseconds (default: 50)"
    )
    
    parser.add_argument(
        "--stages", "-s",
        type=str,
        default=None,
        help="Comma-separated list of stages to benchmark (default: all)"
    )
    
    args = parser.parse_args()
    
    # Set up logging
    logger.setLevel(logging.INFO)
    
    # Create benchmark runner
    target_ms = args.target_ms
    iterations = args.iterations
    
    logger.info(f"Starting latency benchmarks")
    logger.info(f"  Iterations: {iterations}")
    logger.info(f"  Target: {target_ms}ms")
    logger.info("-" * 80)
    
    # Create benchmark runner
    benchmark = LatencyBenchmark(target_ms=target_ms)
    
    all_passed = True
    
    try:
        # Benchmark individual stages
        if args.stages is None or "frame_extraction" in args.stages.split(","):
            result = asyncio.run(
                benchmark.benchmark_stage("Frame Extraction", iterations, example_frame_extraction)
            )
            if not result.passed:
                all_passed = False
        
        if args.stages is None or "slam_processing" in args.stages.split(","):
            result = asyncio.run(
                benchmark.benchmark_stage("SLAM Processing", iterations, example_slam_processing)
            )
            if not result.passed:
                all_passed = False
        
        if args.stages is None or "map_update" in args.stages.split(","):
            result = asyncio.run(
                benchmark.benchmark_stage("Map Update", iterations, example_map_update)
            )
            if not result.passed:
                all_passed = False
        
        # Benchmark end-to-end pipeline
        logger.info("-" * 80)
        logger.info("End-to-End Pipeline")
        logger.info("-" * 80)
        
        result = asyncio.run(
            benchmark.benchmark_end_to_end(iterations, example_full_pipeline)
        )
        if not result.passed:
            all_passed = False
        
    except KeyboardInterrupt:
        logger.warning("\nBenchmark interrupted by user")
    
    # Print summary
    benchmark.print_summary()
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit(main())
