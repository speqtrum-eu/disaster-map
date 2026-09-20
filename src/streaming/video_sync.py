"""
Video Timestamp Synchronization Module.

Provides precise timestamp synchronization for:
- GPS PPS (Pulse Per Second) signals
- External time sources (NTP, hardware clocks)
- Frame-to-timeline alignment
- Clock drift compensation
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional, Callable, Dict, Any, List
from enum import Enum


logger = logging.getLogger(__name__)


class SyncSource(Enum):
    """Available synchronization sources."""
    SYSTEM = "system"  # System clock (default)
    GPS_PPS = "gps_pps"  # GPS Pulse Per Second signal
    NTP = "ntp"  # Network Time Protocol
    HARDWARE = "hardware"  # Hardware timestamp (e.g., PCIe card)
    EXTERNAL = "external"  # Custom external source


@dataclass
class SyncConfig:
    """Configuration for timestamp synchronization."""
    source: SyncSource = SyncSource.SYSTEM
    sync_interval_ms: float = 100.0  # How often to check sync
    tolerance_ms: float = 5.0  # Maximum acceptable drift
    enable_drift_compensation: bool = True
    
    # GPS PPS specific settings
    pps_pin: Optional[int] = None  # GPIO pin for PPS signal (Raspberry Pi)
    
    # NTP specific settings
    ntp_server: Optional[str] = None  # NTP server address
    
    # Callbacks
    on_sync_update: Optional[Callable[[float], None]] = None  # Called with new offset


@dataclass
class SyncState:
    """Current synchronization state."""
    is_synchronized: bool = False
    last_sync_time_ms: float = 0.0
    current_offset_ms: float = 0.0
    drift_rate_ms_per_sec: float = 0.0
    sync_source: str = "system"
    
    # Statistics
    total_syncs: int = 0
    avg_drift_ms: float = 0.0
    max_drift_ms: float = 0.0
    
    @property
    def is_stable(self) -> bool:
        """Check if synchronization is stable."""
        return abs(self.drift_rate_ms_per_sec) < 1.0 and self.total_syncs > 5


class VideoSyncManager:
    """
    Manages video timestamp synchronization with multiple sources.
    
    Features:
    - Automatic source selection based on availability
    - Drift compensation for long-term accuracy
    - Multiple sync sources (GPS PPS, NTP, hardware)
    - Real-time offset tracking
    
    Example:
        >>> config = SyncConfig(
        ...     source=SyncSource.GPS_PPS,
        ...     tolerance_ms=2.0,
        ...     enable_drift_compensation=True
        ... )
        >>> sync_manager = VideoSyncManager(config)
        >>> async for frame in stream:
        ...     corrected_time = sync_manager.correct(frame.timestamp)
    """
    
    def __init__(self, config: Optional[SyncConfig] = None):
        self.config = config or SyncConfig()
        self._running = False
        self._state = SyncState()
        
        # Timing tracking
        self._last_check_time_ms: float = 0.0
        self._offset_history: List[float] = []
        self._max_history_size = 100
        
        # GPS PPS handling (Raspberry Pi GPIO)
        self._pps_callback: Optional[Callable[[float], None]] = None
        self._last_pps_time_ms: float = 0.0
        
        # NTP client placeholder
        self._ntp_client: Optional[Any] = None
        
    async def start(self) -> bool:
        """Start synchronization monitoring."""
        logger.info(f"Starting video sync with source: {self.config.source.value}")
        
        self._running = True
        
        try:
            # Initialize based on sync source
            if self.config.source == SyncSource.GPS_PPS:
                await self._setup_gps_pps()
            elif self.config.source == SyncSource.NTP:
                await self._setup_ntp()
            elif self.config.source == SyncSource.HARDWARE:
                await self._setup_hardware_sync()
                
            # Start sync monitoring loop
            asyncio.create_task(self._sync_monitor_loop())
            
            logger.info("Video sync manager started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start video sync: {e}", exc_info=True)
            self._running = False
            return False
    
    async def stop(self) -> None:
        """Stop synchronization monitoring."""
        logger.info("Stopping video sync manager...")
        
        self._running = False
        
        # Cleanup sources
        if hasattr(self, '_pps_callback') and self._pps_callback:
            try:
                import RPi.GPIO as GPIO  # type: ignore
                if self.config.pps_pin is not None:
                    GPIO.remove_event_detect(self.config.pps_pin)
            except ImportError:
                pass
                
        logger.info("Video sync manager stopped")
    
    async def _sync_monitor_loop(self) -> None:
        """Background loop for continuous synchronization."""
        while self._running:
            try:
                await asyncio.sleep(self.config.sync_interval_ms / 1000.0)
                
                # Check current offset and drift
                current_offset = await self._get_current_offset()
                
                if current_offset is not None:
                    # Update state
                    self._state.current_offset_ms = current_offset
                    
                    # Calculate drift rate
                    time_delta = (time.time() * 1000) - self._last_check_time_ms
                    if time_delta > 0:
                        offset_change = current_offset - self._offset_history[-1] if self._offset_history else 0
                        self._state.drift_rate_ms_per_sec = (offset_change / time_delta) * 1000
                    
                    # Update history
                    self._offset_history.append(current_offset)
                    
                    if len(self._offset_history) > self._max_history_size:
                        self._offset_history.pop(0)
                    
                    # Check stability and notify
                    if not self._state.is_stable:
                        logger.debug(f"Sync unstable: drift={self._state.drift_rate_ms_per_sec:.2f}ms/s")
                        
                    # Call callback if provided
                    if self.config.on_sync_update:
                        try:
                            self.config.on_sync_update(current_offset)
                        except Exception as e:
                            logger.error(f"Sync update callback error: {e}")
                            
                self._last_check_time_ms = time.time() * 1000
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Sync monitor loop error: {e}")
    
    async def _get_current_offset(self) -> Optional[float]:
        """Get current timestamp offset from sync source."""
        
        if self.config.source == SyncSource.SYSTEM:
            return await self._get_system_offset()
            
        elif self.config.source == SyncSource.GPS_PPS:
            return await self._get_gps_pps_offset()
            
        elif self.config.source == SyncSource.NTP:
            return await self._get_ntp_offset()
            
        elif self.config.source == SyncSource.HARDWARE:
            return await self._get_hardware_offset()
            
        else:
            logger.warning(f"Unknown sync source: {self.config.source}")
            return None
    
    async def _get_system_offset(self) -> Optional[float]:
        """Get offset from system clock (baseline)."""
        # System clock is our reference - no offset needed
        # This method exists for API consistency
        
        return 0.0
    
    async def _get_gps_pps_offset(self) -> Optional[float]:
        """
        Get offset from GPS PPS signal.
        
        The PPS pulse marks the exact start of a second. We measure
        the time difference between our system clock and the PPS edge.
        """
        try:
            import RPi.GPIO as GPIO  # type: ignore
            
            if self.config.pps_pin is None:
                logger.warning("No PPS pin configured")
                return None
                
            # Check if we have a callback for PPS events
            if not hasattr(self, '_pps_callback') or not self._pps_callback:
                logger.warning("No PPS callback registered")
                return None
            
            # Get current system time in milliseconds
            system_time_ms = time.time() * 1000
            
            # The PPS callback should have been called with the exact second start
            if hasattr(self, '_last_pps_time_ms'):
                pps_time_ms = self._last_pps_time_ms
                
                # Calculate offset: expected - actual
                # If system time is ahead, offset is negative
                offset_ms = (pps_time_ms * 1000) - system_time_ms
                
                return offset_ms
                
            logger.warning("No PPS timestamp available")
            return None
            
        except ImportError:
            logger.error("RPi.GPIO not available for GPS PPS sync")
            return None
        except Exception as e:
            logger.error(f"GPS PPS sync error: {e}")
            return None
    
    async def _setup_gps_pps(self) -> None:
        """Setup GPS PPS synchronization."""
        try:
            import RPi.GPIO as GPIO  # type: ignore
            
            if self.config.pps_pin is not None:
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(self.config.pps_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                
                def on_pps_edge(channel):
                    """Callback for PPS pulse edge."""
                    # Store timestamp in instance variable
                    self._last_pps_time_ms = time.time() * 1000
                
                # Register callback
                GPIO.add_event_detect(
                    self.config.pps_pin, 
                    GPIO.RISING, 
                    callback=on_pps_edge,
                    bouncetime=50
                )
                
                logger.info(f"GPS PPS configured on pin {self.config.pps_pin}")
                
        except ImportError:
            logger.error("RPi.GPIO not available for GPS PPS sync")
                
        except ImportError:
            logger.error("RPi.GPIO not available - GPS PPS sync disabled")
    
    async def _get_ntp_offset(self) -> Optional[float]:
        """Get offset from NTP server."""
        try:
            import ntplib  # type: ignore
            
            if self.config.ntp_server is None:
                logger.warning("No NTP server configured")
                return None
                
            client = ntplib.NTPClient(
                server=self.config.ntp_server,
                timeout=2.0,
                version=3
            )
            
            response = client.request()
            
            # Calculate offset in milliseconds
            offset_ms = (response.offset * 1000)
            
            return offset_ms
            
        except ImportError:
            logger.error("ntplib not available for NTP sync")
            return None
        except Exception as e:
            logger.error(f"NTP sync error: {e}")
            return None
    
    async def _setup_ntp(self) -> None:
        """Setup NTP synchronization."""
        try:
            import ntplib  # type: ignore
            
            if self.config.ntp_server is not None:
                self._ntp_client = ntplib.NTPClient(
                    server=self.config.ntp_server,
                    timeout=2.0
                )
                
                logger.info(f"NTP configured with server {self.config.ntp_server}")
                
        except ImportError:
            logger.error("ntplib not available for NTP sync")
    
    async def _get_hardware_offset(self) -> Optional[float]:
        """Get offset from hardware timestamp source."""
        # Hardware timestamps (e.g., PCIe cards, FPGA) require specialized drivers
        # This is a placeholder for future implementation
        
        logger.debug("Hardware timestamp not available - using system clock")
        return 0.0
    
    async def _setup_hardware_sync(self) -> None:
        """Setup hardware synchronization."""
        logger.info("Hardware sync configured (no additional setup required)")
    
    def correct_timestamp(
        self, 
        original_timestamp_ms: float,
        apply_drift_compensation: bool = True
    ) -> float:
        """
        Correct a timestamp using current offset.
        
        Args:
            original_timestamp_ms: Original timestamp in milliseconds
            apply_drift_compensation: Whether to compensate for drift
            
        Returns:
            Corrected timestamp in milliseconds
            
        Example:
            >>> # Get corrected frame time
            >>> corrected = sync_manager.correct_timestamp(frame.timestamp * 1000)
        """
        if not self._running:
            return original_timestamp_ms
        
        offset = self._state.current_offset_ms
        
        # Apply correction
        corrected = original_timestamp_ms - offset
        
        # Apply drift compensation if enabled and stable
        if apply_drift_compensation and self._state.is_stable:
            time_since_sync = (time.time() * 1000) - self._state.last_sync_time_ms
            
            # Predict future drift based on rate
            predicted_drift = self._state.drift_rate_ms_per_sec * (time_since_sync / 1000.0)
            
            corrected -= predicted_drift
        
        return corrected
    
    def get_corrected_timestamp(
        self, 
        frame: Any,
        timestamp_field: str = "timestamp"
    ) -> float:
        """Get corrected timestamp from a frame object."""
        if not hasattr(frame, timestamp_field):
            logger.warning(f"Frame missing {timestamp_field} field")
            return 0.0
            
        original_timestamp = getattr(frame, timestamp_field)
        
        # Ensure we're working with milliseconds for consistency
        if isinstance(original_timestamp, float) and abs(original_timestamp) < 1e9:
            # Assume it's already in seconds, convert to ms
            original_timestamp_ms = original_timestamp * 1000.0
        else:
            original_timestamp_ms = original_timestamp
        
        return self.correct_timestamp(original_timestamp_ms)
    
    @property
    def state(self) -> SyncState:
        """Get current synchronization state."""
        return self._state
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive sync statistics."""
        return {
            "is_synchronized": self._state.is_synchronized,
            "is_stable": self._state.is_stable,
            "current_offset_ms": round(self._state.current_offset_ms, 2),
            "drift_rate_ms_per_sec": round(self._state.drift_rate_ms_per_sec, 4),
            "sync_source": self.config.source.value,
            "total_syncs": self._state.total_syncs,
            "avg_drift_ms": round(self._state.avg_drift_ms, 2),
        }


# ============================================================================
# Utility Functions
# ============================================================================

def get_system_time_ms() -> float:
    """Get current system time in milliseconds."""
    return time.time() * 1000.0


def calculate_frame_interval(target_fps: float) -> float:
    """Calculate ideal frame interval for target FPS."""
    return 1000.0 / target_fps


def smooth_offset(
    new_offset_ms: float, 
    history: List[float], 
    alpha: float = 0.3
) -> float:
    """Apply exponential smoothing to offset values."""
    if not history:
        return new_offset_ms
        
    # Calculate weighted average with recent values having higher weight
    weights = [alpha ** i for i in range(len(history))]
    total_weight = sum(weights)
    
    smoothed = sum(o * w for o, w in zip(history, weights)) / total_weight
    
    return smoothed
