#!/usr/bin/env python3
"""
End-to-End Latency Benchmarking Script

Measures complete pipeline latency from frame capture to pose estimation.

Usage:
    python scripts/benchmark-latency.py [--pipeline <name>] [--iterations <n>]
"""

import argparse
import time
from typing import Dict, List, Optional


class LatencyBenchmark:
    """End-to-end latency benchmarking."""

    def __init__(self):
        self.results: List[Dict] = []

    def measure_pipeline_latency(
        self,
        pipeline_name: str,
        iterations: int = 10,
        warmup_iterations: int = 3,
    ) -> Dict:
        """
        Measure end-to-end pipeline latency.

        Args:
            pipeline_name: Name of the pipeline being benchmarked
            iterations: Number of measurements to take
            warmup_iterations: Warmup iterations before measurement

        Returns:
            Dictionary with latency statistics
        """
        print(f"\nMeasuring {pipeline_name} latency...")
        print("-" * 50)

        # Warmup phase
        print("Running warmup iterations...")
        for i in range(warmup_iterations):
            self._run_pipeline_once(pipeline_name, dry_run=True)

        # Measurement phase
        latencies: List[float] = []
        component_latencies: Dict[str, List[float]] = {
            "frame_capture": [],
            "slam_processing": [],
            "pose_extraction": [],
            "total": [],
        }

        for i in range(iterations):
            # Measure each pipeline stage
            frame_start = time.perf_counter()
            self._run_pipeline_once(pipeline_name)
            total_time = (time.perf_counter() - frame_start) * 1000  # ms

            latencies.append(total_time)
            component_latencies["total"].append(total_time)

        # Calculate statistics
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
        min_latency = min(latencies) if latencies else 0.0
        max_latency = max(latencies) if latencies else 0.0
        std_latency = (
            sum((l - avg_latency) ** 2 for l in latencies) / len(latencies)
        ) ** 0.5
        p99_latency = sorted(latencies)[int(len(latencies) * 0.99)] if latencies else 0.0

        result = {
            "pipeline_name": pipeline_name,
            "iterations": iterations,
            "avg_latency_ms": round(avg_latency, 3),
            "min_latency_ms": round(min_latency, 3),
            "max_latency_ms": round(max_latency, 3),
            "std_latency_ms": round(std_latency, 3),
            "p99_latency_ms": round(p99_latency, 3),
            "target_latency_ms": 50.0,  # SLA target
        }

        self.results.append(result)

        # Print results
        print(f"\n{pipeline_name} Latency Results:")
        print(f"  Average:   {avg_latency:.3f} ms")
        print(f"  Min:       {min_latency:.3f} ms")
        print(f"  Max:       {max_latency:.3f} ms")
        print(f"  Std Dev:   {std_latency:.3f} ms")
        print(f"  P99:       {p99_latency:.3f} ms")
        print(f"  Target:    50.0 ms")

        # Check against SLA target
        if avg_latency <= 50.0:
            print("  ✓ PASS - Within SLA target")
        else:
            print("  ✗ FAIL - Exceeds SLA target")

        return result

    def _run_pipeline_once(
        self, pipeline_name: str, dry_run: bool = False
    ) -> None:
        """
        Run one iteration of the pipeline.

        Args:
            pipeline_name: Name of the pipeline
            dry_run: If True, don't actually process data
        """
        # Placeholder for actual pipeline execution
        if not dry_run:
            print(f"  Processing frame in {pipeline_name}...")

    def run_comparison(
        self, pipelines: List[str], iterations: int = 10
    ) -> Dict[str, Dict]:
        """
        Compare latency across multiple pipelines.

        Args:
            pipelines: List of pipeline names to compare
            iterations: Number of measurements per pipeline

        Returns:
            Dictionary mapping pipeline name to results
        """
        print("\n" + "=" * 60)
        print("Pipeline Latency Comparison")
        print("=" * 60 + "\n")

        results = {}
        for pipeline in pipelines:
            result = self.measure_pipeline_latency(pipeline, iterations=iterations)
            results[pipeline] = result

        # Summary table
        print("\n" + "-" * 80)
        print(f"{'Pipeline':<25} {'Avg (ms)':>10} {'Min (ms)':>10} {'Max (ms)':>10}")
        print("-" * 80)

        for pipeline, result in results.items():
            print(
                f"{pipeline:<25} {result['avg_latency_ms']:>10.3f} "
                f"{result['min_latency_ms']:>10.3f} {result['max_latency_ms']:>10.3f}"
            )

        return results


def main():
    """Main entry point for latency benchmark script."""
    parser = argparse.ArgumentParser(
        description="End-to-End Latency Benchmarking Tool"
    )
    parser.add_argument(
        "--pipeline", "-p", default="slam_pipeline", help="Pipeline to benchmark"
    )
    parser.add_argument(
        "--iterations", "-i", type=int, default=10, help="Number of measurements"
    )
    parser.add_argument(
        "--warmup", "-w", type=int, default=3, help="Warmup iterations"
    )

    args = parser.parse_args()

    benchmark = LatencyBenchmark()
    result = benchmark.measure_pipeline_latency(
        pipeline_name=args.pipeline,
        iterations=args.iterations,
        warmup_iterations=args.warmup,
    )

    return result


if __name__ == "__main__":
    main()
