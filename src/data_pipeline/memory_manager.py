"""
Memory Management Utilities for Large-Scale Maps.

Provides:
- Memory usage monitoring and alerts
- Automatic memory cleanup strategies
- Efficient data structure management
- Memory profiling tools

Example:
    >>> manager = MemoryManager(max_memory_mb=2048)
    >>> async for frame in stream_frames():
    ...     if not manager.has_memory():
    ...         logger.warning("Memory limit reached!")
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Callable, Deque
from enum import Enum


logger = logging.getLogger(__name__)


@dataclass
class MemoryStats:
    """Current memory statistics."""
    # Process memory
    process_rss_mb: float = 0.0      # Resident Set Size (actual used)
    process_vms_mb: float = 0.0      # Virtual Memory Size (committed)
    
    # Application memory
    application_memory_mb: float = 0.0
    point_cloud_memory_mb: float = 0.0
    buffer_memory_mb: float = 0.0
    
    # Limits and thresholds
    max_memory_mb: float = 2048.0
    warning_threshold_percent: float = 80.0
    critical_threshold_percent: float = 95.0
    
    # History for trend analysis
    history: List[float] = field(default_factory=list)
    
    @property
    def usage_percent(self) -> float:
        """Get memory usage as percentage of limit."""
        if self.max_memory_mb <= 0:
            return 0.0
        return (self.application_memory_mb / self.max_memory_mb) * 100
    
    @property
    def is_warning_level(self) -> bool:
        """Check if at warning level."""
        return self.usage_percent >= self.warning_threshold_percent
    
    @property
    def is_critical_level(self) -> bool:
        """Check if at critical level."""
        return self.usage_percent >= self.critical_threshold_percent


@dataclass
class MemoryAlert:
    """Memory alert notification."""
    timestamp: float
    severity: str  # warning, critical, recovery
    message: str
    memory_mb: float
    action_taken: Optional[str] = None


class CleanupStrategy(Enum):
    """Strategies for memory cleanup."""
    AGGRESSIVE = "aggressive"   # Remove oldest data immediately
    CONSERVATIVE = "conservative"  # Keep recent data, remove old gradually
    SMART = "smart"           # Analyze usage patterns and optimize


class MemoryManager:
    """
    Manages application memory with automatic cleanup.
    
    Features:
    - Real-time memory monitoring
    - Automatic cleanup when limits reached
    - Configurable cleanup strategies
    - Memory profiling and alerts
    
    Example:
        >>> manager = MemoryManager(
        ...     max_memory_mb=2048,
        ...     strategy=CleanupStrategy.SMART,
        ... )
        >>> async for frame in stream_frames():
    ...     if not manager.has_memory():
    ...         logger.warning("Memory limit reached!")
    """
    
    def __init__(
        self, 
        max_memory_mb: float = 2048.0,
        strategy: CleanupStrategy = CleanupStrategy.SMART,
        cleanup_interval_seconds: float = 5.0,
        on_cleanup: Optional[Callable[[str], None]] = None,
    ):
        self.max_memory_mb = max_memory_mb
        self.strategy = strategy
        self.cleanup_interval = cleanup_interval_seconds
        
        # Memory tracking
        self._stats = MemoryStats(max_memory_mb=max_memory_mb)
        self._alerts: Deque[MemoryAlert] = deque(maxlen=100)
        
        # Cleanup state
        self._running = False
        self._cleanup_task: Optional[asyncio.Task] = None
        self._last_cleanup_time: float = time.time()
        
        # Callbacks
        self.on_cleanup = on_cleanup
        
    async def start(self) -> bool:
        """Start memory monitoring."""
        logger.info(f"Starting MemoryManager (max={self.max_memory_mb:.0f}MB)")
        
        self._running = True
        
        try:
            # Start cleanup loop
            asyncio.create_task(self._cleanup_loop())
            
            # Start monitoring loop
            asyncio.create_task(self._monitor_loop())
            
            logger.info("MemoryManager started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start MemoryManager: {e}")
            self._running = False
            return False
    
    async def stop(self) -> None:
        """Stop memory monitoring."""
        logger.info("Stopping MemoryManager...")
        
        self._running = False
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            
        logger.info("MemoryManager stopped")
    
    async def _monitor_loop(self) -> None:
        """Background loop for continuous monitoring."""
        while self._running:
            try:
                # Update statistics periodically
                await asyncio.sleep(1.0)  # Check every second
                
                # Get current memory usage
                if hasattr(self, '_get_memory_usage'):
                    self._update_stats()
                
                # Check thresholds and trigger alerts
                self._check_thresholds()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
    
    async def _cleanup_loop(self) -> None:
        """Background loop for automatic cleanup."""
        while self._running:
            try:
                await asyncio.sleep(self.cleanup_interval)
                
                if self._stats.is_critical_level or self._stats.is_warning_level:
                    await self._perform_cleanup()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")
    
    def _update_stats(self) -> None:
        """Update current memory statistics."""
        try:
            # Get process memory (requires psutil)
            import psutil
            
            process = psutil.Process()
            
            mem_info = process.memory_info()
            self._stats.process_rss_mb = round(mem_info.rss / (1024 * 1024), 2)
            self._stats.process_vms_mb = round(mem_info.vms / (1024 * 1024), 2)
            
        except ImportError:
            # Fallback to estimated values if psutil not available
            logger.debug("psutil not available, using estimated memory")
        
        # Estimate application memory components
        self._stats.application_memory_mb = self._estimate_app_memory()
    
    def _estimate_app_memory(self) -> float:
        """Estimate application-specific memory usage."""
        # This is a rough estimate - override in subclasses for accuracy
        
        # Example estimation based on point cloud size
        try:
            from .incremental_mapper import IncrementalMapper
            
            if hasattr(IncrementalMapper, '_instance'):
                mapper = IncrementalMapper._instance
                points_count = len(mapper._points) if hasattr(mapper, '_points') else 0
                
                # Each point: 12 bytes (3x float64 position + 3x float32 color)
                point_memory = points_count * 12 / (1024 * 1024)
                
                return max(point_memory, self._stats.point_cloud_memory_mb)
                
        except Exception:
            pass
        
        # Default estimate based on recent activity
        return self._stats.application_memory_mb
    
    def _check_thresholds(self) -> None:
        """Check memory thresholds and trigger alerts."""
        usage_percent = self._stats.usage_percent
        
        if usage_percent >= self._stats.critical_threshold_percent:
            severity = "critical"
            message = f"Memory critical: {usage_percent:.1f}% used ({self._stats.application_memory_mb:.0f}MB / {self.max_memory_mb:.0f}MB)"
            
            # Trigger cleanup immediately
            asyncio.create_task(self._perform_cleanup())
            
        elif usage_percent >= self._stats.warning_threshold_percent:
            severity = "warning"
            message = f"Memory warning: {usage_percent:.1f}% used ({self._stats.application_memory_mb:.0f}MB / {self.max_memory_mb:.0f}MB)"
        
        if message:
            alert = MemoryAlert(
                timestamp=time.time(),
                severity=severity,
                message=message,
                memory_mb=self._stats.application_memory_mb,
            )
            
            self._alerts.append(alert)
            
            # Log at appropriate level
            if severity == "critical":
                logger.critical(message)
            else:
                logger.warning(message)
    
    async def _perform_cleanup(self) -> bool:
        """Perform memory cleanup based on strategy."""
        start_time = time.time()
        
        try:
            cleaned_mb = 0.0
            
            if self.strategy == CleanupStrategy.AGGRESSIVE:
                # Remove oldest data immediately
                cleaned_mb = await self._aggressive_cleanup()
                
            elif self.strategy == CleanupStrategy.CONSERVATIVE:
                # Keep recent data, remove old gradually
                cleaned_mb = await self._conservative_cleanup()
                
            else:  # SMART
                # Analyze and optimize based on usage patterns
                cleaned_mb = await self._smart_cleanup()
            
            if cleaned_mb > 0:
                logger.info(f"Cleanup completed: freed {cleaned_mb:.1f}MB in {(time.time() - start_time) * 1000:.0f}ms")
                
                # Notify callback
                if self.on_cleanup:
                    try:
                        self.on_cleanup(f"Freed {cleaned_mb:.1f}MB")
                    except Exception as e:
                        logger.error(f"Cleanup callback error: {e}")
            
            return cleaned_mb > 0
            
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            return False
    
    async def _aggressive_cleanup(self) -> float:
        """Aggressively remove oldest data."""
        try:
            from .incremental_mapper import IncrementalMapper
            
            if hasattr(IncrementalMapper, '_instance'):
                mapper = IncrementalMapper._instance
                
                # Remove 50% of oldest points
                num_to_remove = max(1, len(mapper._points) // 2)
                
                removed_points = mapper._points[:num_to_remove]
                mapper._points = mapper._points[num_to_remove:]
                mapper._colors = mapper._colors[num_to_remove:]
                mapper._timestamps = mapper._timestamps[num_to_remove:]
                
                if mapper._grid:
                    mapper._grid.cleanup_empty_cells(30.0)
                
                # Estimate freed memory
                point_size = 12  # bytes per point
                freed_mb = num_to_remove * point_size / (1024 * 1024)
                
                return freed_mb
                
        except Exception as e:
            logger.error(f"Aggressive cleanup error: {e}")
        
        return 0.0
    
    async def _conservative_cleanup(self) -> float:
        """Conservatively remove old data while preserving recent."""
        try:
            from .incremental_mapper import IncrementalMapper
            
            if hasattr(IncrementalMapper, '_instance'):
                mapper = IncrementalMapper._instance
                
                # Keep last 75% of points, remove oldest 25%
                num_to_keep = max(1000, int(len(mapper._points) * 0.75))
                
                if len(mapper._points) > num_to_keep:
                    removed_count = len(mapper._points) - num_to_keep
                    
                    mapper._points = mapper._points[-num_to_keep:]
                    mapper._colors = mapper._colors[-num_to_keep:]
                    mapper._timestamps = mapper._timestamps[-num_to_keep:]
                    
                    if mapper._grid:
                        mapper._grid.cleanup_empty_cells(60.0)
                    
                    point_size = 12
                    freed_mb = removed_count * point_size / (1024 * 1024)
                    
                    return freed_mb
                    
        except Exception as e:
            logger.error(f"Conservative cleanup error: {e}")
        
        return 0.0
    
    async def _smart_cleanup(self) -> float:
        """Intelligently clean up based on usage patterns."""
        try:
            from .incremental_mapper import IncrementalMapper
            
            if hasattr(IncrementalMapper, '_instance'):
                mapper = IncrementalMapper._instance
                
                # Analyze point distribution and remove sparse areas
                if len(mapper._points) > 100000:
                    # Sample points to find empty regions
                    import random
                    
                    sample_size = min(1000, len(mapper._points))
                    indices = list(range(len(mapper._points)))
                    
                    # Find and remove isolated clusters
                    removed_count = 0
                    
                    for _ in range(5):  # Try to find 5 clusters to remove
                        if removed_count >= len(mapper._points) * 0.1:
                            break
                        
                        # Randomly select a region to check
                        start_idx = random.randint(0, max(1, len(indices) - 100))
                        end_idx = min(start_idx + 100, len(indices))
                        
                        cluster_points = mapper._points[start_idx:end_idx]
                        
                        # Check if this is a sparse region
                        if len(cluster_points) < 50:
                            # Remove this sparse cluster
                            for i in range(len(mapper._points)):
                                if start_idx <= i < end_idx:
                                    removed_count += 1
                    
                    point_size = 12
                    freed_mb = removed_count * point_size / (1024 * 1024)
                    
                    return freed_mb
                    
        except Exception as e:
            logger.error(f"Smart cleanup error: {e}")
        
        return 0.0
    
    def has_memory(self, required_mb: float = 100.0) -> bool:
        """
        Check if there's enough memory for a new operation.
        
        Args:
            required_mb: Required free memory in megabytes
            
        Returns:
            True if sufficient memory available
            
        Example:
            >>> if not manager.has_memory(500):
            ...     logger.error("Cannot proceed - insufficient memory")
        """
        current_usage = self._stats.application_memory_mb
        
        # Add safety margin (10%)
        required_with_margin = required_mb * 1.1
        
        return (current_usage + required_with_margin) < self.max_memory_mb
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current memory statistics."""
        return {
            "usage_percent": round(self._stats.usage_percent, 2),
            "application_memory_mb": round(self._stats.application_memory_mb, 2),
            "process_rss_mb": round(self._stats.process_rss_mb, 2),
            "max_memory_mb": self.max_memory_mb,
            "warning_threshold_percent": self._stats.warning_threshold_percent,
            "critical_threshold_percent": self._stats.critical_threshold_percent,
            "is_warning_level": self._stats.is_warning_level,
            "is_critical_level": self._stats.is_critical_level,
        }
    
    def get_alerts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent memory alerts."""
        return [
            {
                "timestamp": alert.timestamp,
                "severity": alert.severity,
                "message": alert.message,
                "memory_mb": round(alert.memory_mb, 2),
            }
            for alert in list(self._alerts)[-limit:]
        ]
    
    def reset_stats(self) -> None:
        """Reset memory statistics."""
        self._stats = MemoryStats(max_memory_mb=self.max_memory_mb)


# ============================================================================
# Global Instance (Optional Convenience)
# ============================================================================

_instance: Optional[MemoryManager] = None


def get_global_manager() -> Optional[MemoryManager]:
    """Get the global memory manager instance."""
    return _instance


def set_global_manager(manager: MemoryManager) -> None:
    """Set the global memory manager instance."""
    global _instance
    _instance = manager
