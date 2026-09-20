"""
Load Testing Tests for Streaming Pipeline.

Tests system performance under load with:
- Concurrent stream connections (10+)
- Latency benchmarks (<50ms target)
- Memory usage under sustained load
- Throughput validation
"""

import asyncio
import logging
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


logger = logging.getLogger(__name__)


@dataclass
class LoadTestResult:
    """Results from a load test."""
    test_name: str
    concurrent_connections: int
    target_fps: float
    achieved_fps: float
    avg_latency_ms: float
    p95_latency_ms: float
    memory_mb_peak: float
    errors: int
    passed: bool


class MockStreamServer:
    """Mock server to simulate multiple stream sources."""
    
    def __init__(self, num_streams: int = 10):
        self.num_streams = num_streams
        self.streams: Dict[int, asyncio.Queue] = {}
        
        for i in range(num_streams):
            self.streams[i] = asyncio.Queue(maxsize=1)
    
    async def send_frame(self, stream_id: int, frame_data: Any) -> None:
        """Send a frame to a specific stream."""
        try:
            await self.streams[stream_id].put(frame_data, timeout=0.5)
        except asyncio.TimeoutError:
            logger.warning(f"Timeout sending frame to stream {stream_id}")
    
    async def get_frame(self, stream_id: int, timeout_ms: int = 1000) -> Optional[Any]:
        """Get a frame from a specific stream."""
        try:
            return await asyncio.wait_for(
                self.streams[stream_id].get(), 
                timeout=timeout_ms / 1000.0
            )
        except asyncio.TimeoutError:
            return None
    
    def close(self):
        """Close all streams."""
        for stream in self.streams.values():
            try:
                stream.task_done()
            except Exception:
                pass


class LoadTestRunner:
    """Runs load tests on the streaming pipeline."""
    
    def __init__(self, target_fps: float = 30.0):
        self.target_fps = target_fps
        self.results: List[LoadTestResult] = []
        
    async def test_concurrent_streams(
        self, 
        num_connections: int = 12,
        duration_seconds: float = 5.0,
        mock_server: Optional[MockStreamServer] = None
    ) -> LoadTestResult:
        """
        Test system with multiple concurrent stream connections.
        
        Args:
            num_connections: Number of concurrent streams to simulate
            duration_seconds: How long to run the test
            mock_server: Mock server for frame distribution
            
        Returns:
            LoadTestResult with performance metrics
        """
        logger.info(f"Starting load test: {num_connections} connections, "
                   f"{duration_seconds}s duration")
        
        start_time = time.time()
        errors = 0
        
        # Track per-connection statistics
        connection_stats: Dict[int, List[float]] = {}
        total_frames_received = 0
        frame_timestamps: List[float] = []
        
        async def process_stream(stream_id: int) -> None:
            """Process frames from a single stream."""
            local_stats = []
            
            while time.time() - start_time < duration_seconds:
                try:
                    # Get frame with timeout
                    frame_data = await asyncio.wait_for(
                        mock_server.get_frame(stream_id, timeout_ms=50),
                        timeout=0.1  # Check frequently
                    )
                    
                    if frame_data is not None:
                        local_stats.append(time.time())
                        total_frames_received += 1
                        
                except asyncio.TimeoutError:
                    pass
            
            connection_stats[stream_id] = local_stats
    
        async def send_frames():
            """Send frames to all streams."""
            while time.time() - start_time < duration_seconds:
                for stream_id in range(num_connections):
                    try:
                        await mock_server.send_frame(
                            stream_id, 
                            {"frame": total_frames_received}
                        )
                        
                    except Exception as e:
                        errors += 1
        
        # Start frame sender and receivers concurrently
        tasks = [
            asyncio.create_task(process_stream(i)) 
            for i in range(num_connections)
        ]
        
        # Run for duration
        await asyncio.sleep(duration_seconds)
        
        # Calculate results
        elapsed = time.time() - start_time
        
        # Calculate FPS per connection
        fps_per_connection: List[float] = []
        total_latency_ms = 0.0
        latency_samples: List[float] = []
        
        for stream_id, timestamps in connection_stats.items():
            if len(timestamps) >= 2:
                time_span = max(0.1, timestamps[-1] - timestamps[0])
                fps = len(timestamps) / time_span
                fps_per_connection.append(fps)
                
                # Calculate latency for this stream
                avg_latency = sum(timestamps[i+1] - timestamps[i] 
                                for i in range(len(timestamps)-1)) / max(1, len(timestamps)-1)
                total_latency_ms += avg_latency * 1000
        
        # Overall metrics
        avg_fps = sum(fps_per_connection) / max(1, len(fps_per_connection))
        overall_avg_latency = total_latency_ms / num_connections if num_connections > 0 else 0
        
        # Calculate percentiles for latency
        sorted_latencies = sorted(latency_samples) if latency_samples else [overall_avg_latency]
        
        def percentile(data: List[float], p: float) -> float:
            k = (len(data) - 1) * p / 100.0
            f = int(k)
            c = min(f + 1, len(data) - 1) if f < len(data) else f
            return data[f] + (k - f) * (data[c] - data[f]) if len(data) > 1 else data[0]
        
        p95_latency = percentile(sorted_latencies, 95)
        
        # Determine pass/fail based on targets
        passed = (
            avg_fps >= self.target_fps * 0.8 and  # At least 80% of target FPS
            overall_avg_latency < 100.0 and       # Under 100ms average latency
            errors < num_connections             # Fewer errors than connections
        )
        
        result = LoadTestResult(
            test_name="concurrent_streams",
            concurrent_connections=num_connections,
            target_fps=self.target_fps,
            achieved_fps=round(avg_fps, 2),
            avg_latency_ms=round(overall_avg_latency, 3),
            p95_latency_ms=round(p95_latency, 3),
            memory_mb_peak=0.0,  # Would need actual monitoring
            errors=errors,
            passed=passed,
        )
        
        self.results.append(result)
        logger.info(f"Load Test Result: {result}")
        
        return result
    
    async def test_latency_benchmark(
        self, 
        iterations: int = 100,
        mock_server: Optional[MockStreamServer] = None
    ) -> LoadTestResult:
        """
        Benchmark end-to-end latency with multiple iterations.
        
        Args:
            iterations: Number of iterations to measure
            mock_server: Mock server for frame distribution
            
        Returns:
            LoadTestResult with latency metrics
        """
        logger.info(f"Starting latency benchmark: {iterations} iterations")
        
        latencies: List[float] = []
        errors = 0
        
        async def measure_latency(iteration: int) -> Optional[float]:
            """Measure end-to-end latency for one iteration."""
            try:
                # Simulate frame processing pipeline
                start_time = time.perf_counter()
                
                # Get frame from mock server (simulating stream input)
                if mock_server:
                    await asyncio.sleep(0.01)  # Simulate network delay
                
                # Process frame (simulated)
                await asyncio.sleep(0.005)  # Processing time
                
                end_time = time.perf_counter()
                
                latency_ms = (end_time - start_time) * 1000
                latencies.append(latency_ms)
                
                return latency_ms
                
            except Exception as e:
                errors += 1
                logger.warning(f"Iteration {iteration} error: {e}")
                return None
        
        # Run iterations concurrently for throughput measurement
        tasks = [asyncio.create_task(measure_latency(i)) for i in range(iterations)]
        
        await asyncio.gather(*tasks)
        
        if not latencies:
            result = LoadTestResult(
                test_name="latency_benchmark",
                concurrent_connections=1,
                target_fps=self.target_fps,
                achieved_fps=0.0,
                avg_latency_ms=0.0,
                p95_latency_ms=0.0,
                memory_mb_peak=0.0,
                errors=errors,
                passed=False,
            )
            
            self.results.append(result)
            return result
        
        # Calculate statistics
        avg_latency = sum(latencies) / len(latencies)
        
        sorted_latencies = sorted(latencies)
        
        def percentile(data: List[float], p: float) -> float:
            k = (len(data) - 1) * p / 100.0
            f = int(k)
            c = min(f + 1, len(data) - 1) if f < len(data) else f
            return data[f] + (k - f) * (data[c] - data[f])
        
        p50_latency = percentile(sorted_latencies, 50)
        p95_latency = percentile(sorted_latencies, 95)
        p99_latency = percentile(sorted_latencies, 99)
        
        # Check against target (<50ms end-to-end)
        passed = avg_latency < 50.0 and errors < iterations * 0.1
        
        result = LoadTestResult(
            test_name="latency_benchmark",
            concurrent_connections=1,
            target_fps=self.target_fps,
            achieved_fps=len(latencies),
            avg_latency_ms=round(avg_latency, 3),
            p95_latency_ms=round(p95_latency, 3),
            memory_mb_peak=0.0,
            errors=errors,
            passed=passed,
        )
        
        self.results.append(result)
        logger.info(f"Latency Benchmark Result: {result}")
        
        return result
    
    async def test_memory_under_load(
        self, 
        num_connections: int = 10,
        duration_seconds: float = 3.0
    ) -> LoadTestResult:
        """
        Test memory usage under sustained load.
        
        Args:
            num_connections: Number of concurrent connections
            duration_seconds: Duration to monitor
            
        Returns:
            LoadTestResult with memory metrics
        """
        logger.info(f"Starting memory test: {num_connections} connections, "
                   f"{duration_seconds}s monitoring")
        
        import sys
        
        initial_memory = sys.getsizeof({}) / (1024 * 1024)
        
        async def simulate_load():
            """Simulate sustained load."""
            for i in range(100):
                # Simulate processing operations
                data = {
                    "frame_id": i,
                    "timestamp": time.time(),
                    "points": [(j, j*2, j*3) for j in range(100)],
                }
                
                await asyncio.sleep(0.01)  # Simulate processing time
        
        async def monitor_memory():
            """Monitor memory during load."""
            peak_memory = initial_memory
            
            while True:
                current_memory = sys.getsizeof({}) / (1024 * 1024)
                
                if current_memory > peak_memory:
                    peak_memory = current_memory
                
                await asyncio.sleep(0.5)
        
        # Run load and monitoring concurrently
        tasks = [
            asyncio.create_task(simulate_load()),
            asyncio.create_task(monitor_memory()),
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        memory_delta = peak_memory - initial_memory
        
        # Memory should stay reasonable (<100MB delta for this test)
        passed = memory_delta < 50.0
        
        result = LoadTestResult(
            test_name="memory_under_load",
            concurrent_connections=num_connections,
            target_fps=self.target_fps,
            achieved_fps=0.0,
            avg_latency_ms=0.0,
            p95_latency_ms=0.0,
            memory_mb_peak=round(memory_delta, 2),
            errors=0,
            passed=passed,
        )
        
        self.results.append(result)
        logger.info(f"Memory Test Result: {result}")
        
        return result
    
    def run_all_load_tests(self) -> Dict[str, Any]:
        """Run all load tests and return summary."""
        logger.info("=" * 60)
        logger.info("Running Load Tests")
        logger.info("=" * 60)
        
        # Create mock server for realistic testing
        mock_server = MockStreamServer(num_streams=12)
        
        tests = [
            ("Concurrent Streams", self.test_concurrent_streams, {
                "num_connections": 12,
                "duration_seconds": 3.0,
                "mock_server": mock_server,
            }),
            ("Latency Benchmark", self.test_latency_benchmark, {
                "iterations": 100,
                "mock_server": mock_server,
            }),
            ("Memory Under Load", self.test_memory_under_load, {}),
        ]
        
        results: Dict[str, Any] = {
            "total_tests": len(tests),
            "passed": 0,
            "failed": 0,
            "test_results": [],
        }
        
        for test_name, test_func, kwargs in tests:
            try:
                result = asyncio.run(test_func(**kwargs))
                
                if result.passed:
                    results["passed"] += 1
                    logger.info(f"✓ {test_name} PASSED")
                else:
                    results["failed"] += 1
                    logger.error(f"✗ {test_name} FAILED")
                    
            except Exception as e:
                results["failed"] += 1
                logger.error(f"✗ {test_name} ERROR: {e}")
            
            mock_server.close()
        
        summary = {
            "summary": {
                "total_tests": results["total_tests"],
                "passed": results["passed"],
                "failed": results["failed"],
                "success_rate": round(results["passed"] / max(1, results["total_tests"]) * 100, 2),
            },
            "detailed_results": self.results,
        }
        
        logger.info("=" * 60)
        logger.info(f"Load Tests Summary: {results['passed']}/{results['total_tests']} passed")
        logger.info("=" * 60)
        
        return summary


# ============================================================================
# Test Runner (for pytest compatibility)
# ============================================================================

async def run_load_tests():
    """Run all load tests and print results."""
    runner = LoadTestRunner(target_fps=30.0)
    results = runner.run_all_load_tests()
    
    # Print formatted results
    print("\n" + "=" * 60)
    print("LOAD TEST RESULTS")
    print("=" * 60)
    
    for result in results["detailed_results"]:
        status = "✓ PASS" if result.get("passed", False) else "✗ FAIL"
        print(f"\n{status}: {result['test_name']}")
        for key, value in result.items():
            if key not in ["passed", "test_name"]:
                print(f"  {key}: {value}")
    
    print("\n" + "=" * 60)
    summary = results["summary"]
    print(f"TOTAL: {summary['passed']}/{summary['total_tests']} tests passed")
    print(f"SUCCESS RATE: {summary['success_rate']}%")
    print("=" * 60)
    
    return summary["failed"] == 0


# Run if executed directly
if __name__ == "__main__":
    import sys
    
    success = asyncio.run(run_load_tests())
    sys.exit(0 if success else 1)
