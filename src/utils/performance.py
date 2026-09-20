"""
Performance Monitoring Utilities.

Provides real-time performance tracking with:
- Latency measurement across pipeline stages
- FPS and throughput monitoring
- Memory usage tracking
- Statistical analysis (min, max, avg, percentiles)
"""

import asyncio
import logging
import statistics
import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable, Deque
from collections import deque


logger = logging.getLogger(__name__)


@dataclass
class LatencyMeasurement:
    """Single latency measurement."""
    timestamp: float
    stage: str
    value_ms: float  # Value in milliseconds
    context: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "stage": self.stage,
            "value_ms": round(self.value_ms, 3),
            "context": self.context or {},
        }


@dataclass
class PerformanceStats:
    """Aggregated performance statistics."""
    count: int = 0
    total_time_ms: float = 0.0
    
    # Min/Max/Avg
    min_value_ms: float = float('inf')
    max_value_ms: float = 0.0
    avg_value_ms: float = 0.0
    
    # Percentiles (for latency distribution)
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    
    # Throughput
    fps: float = 0.0
    items_per_second: float = 0.0
    
    @property
    def is_valid(self) -> bool:
        """Check if statistics are valid."""
        return self.count > 0 and not (self.min_value_ms == float('inf'))


class LatencyTracker:
    """
    Tracks latency across pipeline stages with statistical analysis.
    
    Features:
    - Multi-stage tracking with context
    - Real-time statistics calculation
    - Percentile computation for latency distribution
    - Configurable window size for rolling stats
    
    Example:
        >>> tracker = LatencyTracker(window_size=1000)
        >>> tracker.track("frame_extraction", 12.5, {"fps": 30})
        >>> stats = tracker.get_stats("frame_extraction")
    """
    
    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        
        # Per-stage tracking
        self._stages: Dict[str, Deque[LatencyMeasurement]] = {}
        
        # Global statistics
        self._global_start_time: float = time.time()
        self._total_items_processed = 0
    
    def track(
        self, 
        stage: str, 
        latency_ms: float, 
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Record a latency measurement.
        
        Args:
            stage: Pipeline stage name (e.g., "frame_extraction", "slam_processing")
            latency_ms: Latency in milliseconds
            context: Additional context data
            
        Example:
            >>> tracker.track("rtsp_connection", 45.2, {"url": "rtsp://example.com"})
        """
        measurement = LatencyMeasurement(
            timestamp=time.time(),
            stage=stage,
            value_ms=latency_ms,
            context=context
        )
        
        # Initialize stage if needed
        if stage not in self._stages:
            self._stages[stage] = deque(maxlen=self.window_size)
        
        # Add measurement to stage history
        self._stages[stage].append(measurement)
        
        # Update global counters
        self._total_items_processed += 1
    
    def get_stats(self, stage: Optional[str] = None) -> PerformanceStats:
        """
        Get statistics for a specific stage or all stages.
        
        Args:
            stage: Stage name to query (None for all stages combined)
            
        Returns:
            PerformanceStats object
            
        Example:
            >>> stats = tracker.get_stats("frame_extraction")
        """
        measurements = []
        
        if stage is None:
            # Combine all stages
            for stage_measurements in self._stages.values():
                measurements.extend(stage_measurements)
        else:
            measurements = list(self._stages.get(stage, deque()))
        
        if not measurements:
            return PerformanceStats()
        
        values = [m.value_ms for m in measurements]
        count = len(values)
        
        # Calculate statistics
        total_time = sum(values)
        min_val = min(values)
        max_val = max(values)
        avg_val = total_time / count
        
        # Calculate percentiles using numpy-like approach
        sorted_values = sorted(values)
        
        def percentile(data: List[float], p: float) -> float:
            """Calculate percentile value."""
            k = (len(data) - 1) * p / 100.0
            f = int(k)
            c = f + 1 if f + 1 < len(data) else f
            
            return data[f] + (k - f) * (data[c] - data[f])
        
        p50 = percentile(sorted_values, 50)
        p95 = percentile(sorted_values, 95)
        p99 = percentile(sorted_values, 99)
        
        # Calculate FPS/throughput
        time_span = measurements[-1].timestamp - measurements[0].timestamp if len(measurements) > 1 else 1.0
        fps = count / max(0.1, time_span)
        
        return PerformanceStats(
            count=count,
            total_time_ms=total_time,
            min_value_ms=min_val,
            max_value_ms=max_val,
            avg_value_ms=avg_val,
            p50_ms=p50,
            p95_ms=p95,
            p99_ms=p99,
            fps=fps,
        )
    
    def get_all_stats(self) -> Dict[str, PerformanceStats]:
        """Get statistics for all stages."""
        return {stage: self.get_stats(stage) for stage in self._stages}
    
    def reset_stage(self, stage: str) -> None:
        """Reset tracking for a specific stage."""
        if stage in self._stages:
            self._stages[stage].clear()
    
    def reset_all(self) -> None:
        """Reset all tracking data."""
        self._stages.clear()


class PerformanceMonitor:
    """
    Comprehensive performance monitoring for the entire pipeline.
    
    Features:
    - FPS and throughput monitoring
    - Memory usage tracking
    - Latency tracking integration
    - Real-time alerts and warnings
    
    Example:
        >>> monitor = PerformanceMonitor(thresholds={"fps": 30, "latency_ms": 50})
        >>> async for frame in stream:
        ...     monitor.record_frame(frame)
        ...     if monitor.check_thresholds():
        ...             logger.warning("Performance threshold exceeded!")
    """
    
    def __init__(
        self, 
        window_size: int = 60,
        thresholds: Optional[Dict[str, float]] = None
    ):
        self.window_size = window_size
        
        # Latency tracker for pipeline stages
        self.latency_tracker = LatencyTracker(window_size)
        
        # FPS tracking
        self._frame_timestamps: Deque[float] = deque(maxlen=window_size)
        self._items_processed: int = 0
        
        # Memory tracking (requires psutil or similar)
        try:
            import psutil
            self._psutil_available = True
        except ImportError:
            self._psutil_available = False
        
        # Thresholds for alerts
        self.thresholds = thresholds or {
            "fps": 30.0,      # Minimum acceptable FPS
            "latency_ms": 50.0,  # Maximum acceptable latency
            "memory_mb": 2048.0,  # Maximum memory usage
        }
        
        # Alert state
        self._alerts: List[Dict[str, Any]] = []
    
    def record_frame(self, timestamp: float) -> None:
        """Record a frame processing event."""
        self._frame_timestamps.append(timestamp)
        self.latency_tracker.track("frame_processing", 0.0)
    
    def record_latency(
        self, 
        stage: str, 
        latency_ms: float, 
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record a latency measurement for pipeline analysis."""
        self.latency_tracker.track(stage, latency_ms, context)
    
    def get_fps(self) -> float:
        """Calculate current FPS from recorded timestamps."""
        if len(self._frame_timestamps) < 2:
            return 0.0
            
        time_span = self._frame_timestamps[-1] - self._frame_timestamps[0]
        
        # Use sliding window for more accurate recent FPS
        window_size = min(len(self._frame_timestamps), self.window_size)
        recent_times = list(self._frame_timestamps)[-window_size:]
        
        if len(recent_times) < 2:
            return 0.0
            
        time_span = recent_times[-1] - recent_times[0]
        fps = window_size / max(0.1, time_span)
        
        return fps
    
    def get_throughput(self) -> float:
        """Get items processed per second."""
        if len(self._frame_timestamps) < 2:
            return 0.0
            
        time_span = self._frame_timestamps[-1] - self._frame_timestamps[0]
        
        # Calculate rate over recent window
        window_size = min(len(self._frame_timestamps), self.window_size)
        items_in_window = window_size
        
        throughput = items_in_window / max(0.1, time_span)
        
        return throughput
    
    def get_memory_usage_mb(self) -> Optional[float]:
        """Get current memory usage in megabytes."""
        if not self._psutil_available:
            return None
            
        try:
            # Get process memory (requires psutil.Process())
            import psutil
            process = psutil.Process()
            
            # Virtual memory (RSS + shared)
            mem_info = process.memory_info()
            total_mb = mem_info.rss / (1024 * 1024)
            
            return round(total_mb, 2)
        except Exception as e:
            logger.debug(f"Could not get memory usage: {e}")
            return None
    
    def check_thresholds(self) -> bool:
        """
        Check if performance is within acceptable thresholds.
        
        Returns:
            True if all metrics are within limits, False otherwise
            
        Example:
            >>> if monitor.check_thresholds():
            ...     logger.info("Performance OK")
            ... else:
            ...     logger.warning("Performance degraded!")
        """
        violations = []
        
        # Check FPS threshold
        fps = self.get_fps()
        if fps < self.thresholds["fps"]:
            violations.append(f"FPS {fps:.1f} below minimum {self.thresholds['fps']}")
        
        # Check latency thresholds
        stats = self.latency_tracker.get_stats()
        if stats.p95_ms > self.thresholds["latency_ms"]:
            violations.append(
                f"P95 latency {stats.p95_ms:.1f}ms exceeds threshold {self.thresholds['latency_ms']}ms"
            )
        
        # Check memory usage
        memory_mb = self.get_memory_usage_mb()
        if memory_mb is not None and memory_mb > self.thresholds["memory_mb"]:
            violations.append(
                f"Memory {memory_mb:.0f}MB exceeds limit {self.thresholds['memory_mb']}MB"
            )
        
        # Log violations
        if violations:
            for violation in violations:
                logger.warning(f"Performance threshold violated: {violation}")
                
                # Record alert
                self._alerts.append({
                    "timestamp": time.time(),
                    "type": "threshold_violation",
                    "message": violation,
                })
            
            return False
        
        return True
    
    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary."""
        stats = self.latency_tracker.get_all_stats()
        
        return {
            "fps": round(self.get_fps(), 2),
            "throughput": round(self.get_throughput(), 2),
            "memory_mb": self.get_memory_usage_mb(),
            "items_processed": self._items_processed,
            "stages": {
                stage: {
                    "count": stats[stage].count if stage in stats else 0,
                    "avg_latency_ms": round(stats[stage].avg_value_ms, 3) if stage in stats else None,
                    "p95_latency_ms": round(stats[stage].p95_ms, 3) if stage in stats else None,
                }
                for stage in stats.keys()
            },
            "thresholds_met": self.check_thresholds(),
        }
    
    def get_alerts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent performance alerts."""
        return self._alerts[-limit:] if self._alerts else []


# ============================================================================
# Utility Functions
# ============================================================================

def measure_latency(
    func: Callable, 
    *args, 
    name: str = "operation",
    **kwargs
) -> float:
    """
    Measure execution time of a function.
    
    Args:
        func: Function to execute
        *args: Arguments to pass to function
        name: Name for the measurement (for tracking)
        **kwargs: Keyword arguments to pass to function
        
    Returns:
        Execution time in milliseconds
        
    Example:
        >>> latency = measure_latency(process_frame, frame, name="frame_extraction")
        >>> print(f"Frame extraction took {latency:.2f}ms")
    """
    start_time = time.perf_counter()
    
    try:
        result = func(*args, **kwargs)
        return (time.perf_counter() - start_time) * 1000
        
    except Exception as e:
        # Still measure even on error
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.error(f"Function {name} failed after {elapsed_ms:.2f}ms: {e}")
        raise


def benchmark(
    func: Callable, 
    iterations: int = 100, 
    name: str = "benchmark",
    *args, 
    **kwargs
) -> Dict[str, Any]:
    """
    Run a performance benchmark on a function.
    
    Args:
        func: Function to benchmark
        iterations: Number of iterations to run
        name: Name for the benchmark
        *args: Arguments to pass to function
        **kwargs: Keyword arguments to pass to function
        
    Returns:
        Dictionary with benchmark results
        
    Example:
        >>> results = benchmark(process_frame, 1000, "frame_processing", frame)
        >>> print(f"Average latency: {results['avg_ms']:.2f}ms")
    """
    latencies = []
    
    for i in range(iterations):
        start_time = time.perf_counter()
        
        try:
            func(*args, **kwargs)
            
        except Exception as e:
            logger.error(f"Iteration {i+1}/{iterations} failed: {e}")
            continue
        
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        latencies.append(elapsed_ms)
    
    if not latencies:
        return {"error": "No successful iterations"}
        
    # Calculate statistics
    avg_latency = sum(latencies) / len(latencies)
    min_latency = min(latencies)
    max_latency = max(latencies)
    
    # Percentiles
    sorted_latencies = sorted(latencies)
    n = len(sorted_latencies)
    
    def percentile(data: List[float], p: float) -> float:
        k = (n - 1) * p / 100.0
        f = int(k)
        c = min(f + 1, n - 1)
        return data[f] + (k - f) * (data[c] - data[f])
    
    p50 = percentile(sorted_latencies, 50)
    p95 = percentile(sorted_latencies, 95)
    p99 = percentile(sorted_latencies, 99)
    
    return {
        "name": name,
        "iterations": iterations,
        "avg_ms": round(avg_latency, 3),
        "min_ms": round(min_latency, 3),
        "max_ms": round(max_latency, 3),
        "p50_ms": round(p50, 3),
        "p95_ms": round(p95, 3),
        "p99_ms": round(p99, 3),
    }
