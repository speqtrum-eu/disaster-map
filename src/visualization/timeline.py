"""
Timeline Navigation System for 3D Visualization.

Provides frame-by-frame playback, smooth animations, and interactive
navigation controls for disaster map visualization.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable, Awaitable
from datetime import datetime
import numpy as np


@dataclass
class TimelineConfig:
    """Configuration for timeline navigation."""
    frame_interval_ms: float = 100.0
    fps_target: int = 60
    auto_play: bool = False
    loop_mode: bool = False  # Loop back to start when reaching end
    show_frame_markers: bool = True
    snap_to_keyframes: bool = True


@dataclass
class PlaybackState:
    """Current playback state."""
    is_playing: bool = False
    current_frame_index: int = 0
    total_frames: int = 0
    playback_rate: float = 1.0  # Multiplier (e.g., 2.0 for 2x speed)
    direction: str = "forward"  # "forward" or "backward"
    paused_at_frame: Optional[int] = None


@dataclass
class AnimationState:
    """State for smooth animations."""
    is_animating: bool = False
    animation_type: str = ""  # "fly_through", "zoom", "pan"
    start_time: float = 0.0
    end_time: float = 0.0
    progress: float = 0.0
    current_pose: Optional[Dict[str, Any]] = None


class TimelineNavigator:
    """
    Interactive timeline navigation for frame-by-frame playback.
    
    Features:
    - Frame-by-frame stepping with smooth transitions
    - Playback controls (play/pause/stop/reverse)
    - Speed control and time scrubbing
    - Smooth animations between frames
    - Keyboard shortcuts support
    
    Example usage:
        navigator = TimelineNavigator(frames, config=TimelineConfig())
        
        # Navigate to specific frame
        navigator.go_to_frame(50)
        
        # Start playback
        navigator.play(fps=30)
        
        # Add smooth transition between frames
        navigator.add_smooth_transition(frame1_pose, frame2_pose)
    """
    
    def __init__(
        self,
        frames: List[Dict[str, Any]],
        config: Optional[TimelineConfig] = None,
        on_frame_change: Optional[Callable[[int], Awaitable[None]]] = None,
        on_playback_state_change: Optional[Callable[[PlaybackState], Awaitable[None]]] = None,
    ):
        """
        Initialize the timeline navigator.
        
        Args:
            frames: List of frame data with timestamps and poses
            config: Timeline configuration options
            on_frame_change: Callback when frame changes
            on_playback_state_change: Callback when playback state changes
        """
        self.frames = frames
        self.config = config or TimelineConfig()
        
        # Convert frames to FrameMetadata-like structure
        self._frame_data: List[Dict[str, Any]] = []
        for i, frame in enumerate(frames):
            self._frame_data.append({
                "index": i,
                "timestamp": frame.get("timestamp", i * 0.1),
                "pose": frame.get("pose"),
                "metadata": frame.get("metadata", {}),
            })
        
        # State management
        self.state = PlaybackState(
            total_frames=len(self._frame_data)
        )
        self.animation_state = AnimationState()
        
        # Callbacks
        self._on_frame_change = on_frame_change
        self._on_playback_state_change = on_playback_state_change
        
        # Timing control
        self._playback_timer: Optional[asyncio.Task] = None
        self._last_update_time: float = 0.0
        self._delta_time: float = 1.0 / self.config.fps_target
        
        # Animation queue
        self._animation_queue: List[tuple] = []  # (timestamp, animation_func)
        
    @property
    def current_frame(self) -> Dict[str, Any]:
        """Get the currently displayed frame data."""
        if not self.frames:
            return {}
        return self._frame_data[self.state.current_frame_index]
    
    @property
    def total_frames(self) -> int:
        """Total number of frames in timeline."""
        return len(self._frame_data)
    
    @property
    def is_playing(self) -> bool:
        """Check if playback is active."""
        return self.state.is_playing
    
    async def initialize(self) -> bool:
        """Initialize the navigator with frame data."""
        print(f"[TimelineNavigator] Initialized with {len(self._frame_data)} frames")
        
        # Validate frame data
        for i, frame in enumerate(self._frame_data):
            if "timestamp" not in frame:
                frame["timestamp"] = i * 0.1
        
        return True
    
    def go_to_frame(self, frame_index: int) -> bool:
        """
        Navigate to a specific frame index.
        
        Args:
            frame_index: Index of frame to navigate to
            
        Returns:
            True if successful
        """
        if not self.frames or frame_index < 0 or frame_index >= len(self._frame_data):
            return False
        
        old_index = self.state.current_frame_index
        self.state.current_frame_index = frame_index
        
        # Notify listeners
        if self._on_frame_change:
            asyncio.create_task(self._on_frame_change(frame_index))
        
        print(f"[TimelineNavigator] Navigated to frame {frame_index}")
        return True
    
    def go_to_next_frame(self) -> bool:
        """Move to the next frame."""
        if not self.frames:
            return False
        
        new_index = (self.state.current_frame_index + 1) % len(self._frame_data)
        
        # If loop mode is disabled and we're at the end, stop
        if not self.config.loop_mode and self.state.current_frame_index == len(self._frame_data) - 1:
            return False
        
        return self.go_to_frame(new_index)
    
    def go_to_previous_frame(self) -> bool:
        """Move to the previous frame."""
        if not self.frames:
            return False
        
        new_index = (self.state.current_frame_index - 1) % len(self._frame_data)
        
        # If loop mode is disabled and we're at the start, stop
        if not self.config.loop_mode and self.state.current_frame_index == 0:
            return False
        
        return self.go_to_frame(new_index)
    
    def go_to_first_frame(self) -> bool:
        """Jump to the first frame."""
        return self.go_to_frame(0)
    
    def go_to_last_frame(self) -> bool:
        """Jump to the last frame."""
        if not self.frames:
            return False
        return self.go_to_frame(len(self._frame_data) - 1)
    
    def get_frame_at_time(self, timestamp: float) -> Optional[Dict[str, Any]]:
        """Get the frame closest to a given timestamp."""
        if not self.frames:
            return None
        
        # Binary search for closest frame
        left, right = 0, len(self._frame_data) - 1
        
        while left <= right:
            mid = (left + right) // 2
            diff = abs(self._frame_data[mid]["timestamp"] - timestamp)
            
            if diff < 0.5:  # Within acceptable range
                return self._frame_data[mid]
            
            if self._frame_data[mid]["timestamp"] < timestamp:
                left = mid + 1
            else:
                right = mid - 1
        
        # Return closest frame
        min_diff = float('inf')
        closest = None
        for frame in self._frame_data:
            diff = abs(frame["timestamp"] - timestamp)
            if diff < min_diff:
                min_diff = diff
                closest = frame
        
        return closest
    
    def get_time_range(self) -> tuple:
        """Get the start and end timestamps of all frames."""
        if not self.frames:
            return (0.0, 0.0)
        
        timestamps = [f["timestamp"] for f in self._frame_data]
        return (min(timestamps), max(timestamps))
    
    def get_playback_duration(self) -> float:
        """Get the total playback duration in seconds."""
        start_time, end_time = self.get_time_range()
        return end_time - start_time
    
    async def play(
        self, 
        fps: Optional[float] = None,
        rate: float = 1.0,
    ) -> None:
        """
        Start playback of the timeline.
        
        Args:
            fps: Frames per second for playback speed
            rate: Playback rate multiplier (e.g., 2.0 for double speed)
        """
        if not self.frames:
            print("[TimelineNavigator] No frames to play")
            return
        
        # Update state
        self.state.is_playing = True
        self.state.playback_rate = rate
        self._delta_time = (1.0 / fps or 30) * rate
        
        async def playback_loop():
            """Main playback loop."""
            while self.state.is_playing:
                try:
                    # Calculate next frame index based on direction
                    if self.state.direction == "forward":
                        new_index = min(
                            len(self._frame_data) - 1,
                            self.state.current_frame_index + int(1.0 / self._delta_time)
                        )
                    else:
                        new_index = max(
                            0,
                            self.state.current_frame_index - int(1.0 / self._delta_time)
                        )
                    
                    # Update frame index
                    if new_index != self.state.current_frame_index:
                        self.go_to_frame(new_index)
                    
                    # Small delay to control playback speed
                    await asyncio.sleep(self._delta_time)
                    
                except Exception as e:
                    print(f"[TimelineNavigator] Playback error: {e}")
                    break
        
        # Start async playback loop
        self._playback_timer = asyncio.create_task(playback_loop())
    
    async def pause(self) -> None:
        """Pause playback."""
        if not self.state.is_playing:
            return
        
        self.state.is_playing = False
        
        if self._playback_timer:
            self._playback_timer.cancel()
            self._playback_timer = None
        
        # Store current frame for resuming
        self.state.paused_at_frame = self.state.current_frame_index
        
        print(f"[TimelineNavigator] Paused at frame {self.state.current_frame_index}")
    
    async def stop(self) -> None:
        """Stop playback and reset to first frame."""
        await self.pause()
        
        # Reset state
        self.state.is_playing = False
        self.state.paused_at_frame = None
        
        if not self.frames:
            return
        
        self.go_to_first_frame()
    
    async def toggle_playback(self) -> bool:
        """Toggle playback on/off. Returns True if now playing."""
        if self.state.is_playing:
            await self.pause()
        else:
            await self.play()
        
        return self.state.is_playing
    
    def set_playback_rate(self, rate: float) -> None:
        """
        Set the playback speed multiplier.
        
        Args:
            rate: Multiplier (e.g., 2.0 for 2x speed, 0.5 for slow motion)
        """
        self.state.playback_rate = max(0.1, min(10.0, rate))
    
    def reverse_playback(self) -> None:
        """Reverse playback direction."""
        if not self.state.is_playing:
            return
        
        if self.state.direction == "forward":
            self.state.direction = "backward"
        else:
            self.state.direction = "forward"
    
    async def scrub_to_time(self, timestamp: float) -> bool:
        """
        Jump to a specific timestamp.
        
        Args:
            timestamp: Target timestamp in seconds
            
        Returns:
            True if successful
        """
        frame = self.get_frame_at_time(timestamp)
        if not frame:
            return False
        
        index = frame["index"]
        await self.go_to_frame(index)
        return True
    
    async def add_smooth_transition(
        self,
        start_pose: Dict[str, Any],
        end_pose: Dict[str, Any],
        duration_seconds: float = 2.0,
        animation_type: str = "fly_through",
    ) -> None:
        """
        Add a smooth transition between two poses.
        
        Args:
            start_pose: Starting camera pose (latitude, longitude, altitude)
            end_pose: Ending camera pose
            duration_seconds: Animation duration
            animation_type: Type of animation ("fly_through", "zoom", "pan")
        """
        def interpolate_poses(t: float) -> Dict[str, Any]:
            """Interpolate between start and end poses."""
            progress = min(max(0, t), 1.0)
            
            return {
                "latitude": start_pose.get("latitude", 0) + 
                           (end_pose.get("latitude", 0) - start_pose.get("latitude", 0)) * progress,
                "longitude": start_pose.get("longitude", 0) + 
                            (end_pose.get("longitude", 0) - start_pose.get("longitude", 0)) * progress,
                "altitude": start_pose.get("altitude", 50000) + 
                           (end_pose.get("altitude", 50000) - start_pose.get("altitude", 50000)) * progress,
            }
        
        # Add animation to queue
        self._animation_queue.append((
            datetime.now().timestamp(),
            interpolate_poses,
            duration_seconds,
            animation_type
        ))
    
    async def execute_animations(self) -> None:
        """Execute all queued animations."""
        if not self._animation_queue:
            return
        
        while self._animation_queue:
            timestamp, pose_func, duration, anim_type = self._animation_queue.pop(0)
            
            # Execute animation
            num_steps = int(duration * 60)  # ~60 FPS
            step_time = duration / num_steps
            
            for i in range(num_steps):
                progress = i / num_steps
                current_pose = pose_func(progress)
                
                # Update current pose (would call viewer.set_camera_position in real implementation)
                self.state.current_pose = current_pose
                
                await asyncio.sleep(step_time)
    
    def get_current_state(self) -> Dict[str, Any]:
        """Get the current navigator state."""
        return {
            "current_frame_index": self.state.current_frame_index,
            "total_frames": self.state.total_frames,
            "is_playing": self.state.is_playing,
            "playback_rate": self.state.playback_rate,
            "direction": self.state.direction,
            "paused_at_frame": self.state.paused_at_frame,
            "animation_state": {
                "is_animating": self.animation_state.is_animating,
                "type": self.animation_state.animation_type,
                "progress": self.animation_state.progress,
            },
        }
    
    def export_timeline(self) -> Dict[str, Any]:
        """Export timeline data for serialization."""
        return {
            "frames": [
                {
                    "index": f["index"],
                    "timestamp": f["timestamp"],
                    "pose": f.get("pose"),
                    "metadata": f.get("metadata", {}),
                }
                for f in self._frame_data
            ],
            "config": {
                "frame_interval_ms": self.config.frame_interval_ms,
                "fps_target": self.config.fps_target,
                "loop_mode": self.config.loop_mode,
            },
            "state": self.get_current_state(),
        }
    
    def load_timeline(self, data: Dict[str, Any]) -> bool:
        """Load a previously exported timeline."""
        try:
            # Restore frames
            if "frames" in data:
                for frame_data in data["frames"]:
                    self._frame_data.append({
                        "index": frame_data.get("index", len(self._frame_data)),
                        "timestamp": frame_data.get("timestamp"),
                        "pose": frame_data.get("pose"),
                        "metadata": frame_data.get("metadata", {}),
                    })
            
            # Restore state if provided
            if "state" in data:
                self.state.current_frame_index = data["state"].get(
                    "current_frame_index", 0
                )
            
            return True
            
        except Exception as e:
            print(f"[TimelineNavigator] Error loading timeline: {e}")
            return False


class KeyboardControls:
    """Keyboard shortcut handler for timeline navigation."""
    
    KEYBOARD_SHORTCUTS = {
        "Space": ("toggle_playback", {}),
        "LeftArrow": ("go_to_previous_frame", {}),
        "RightArrow": ("go_to_next_frame", {}),
        "Home": ("go_to_first_frame", {}),
        "End": ("go_to_last_frame", {}),
        "+": ("set_playback_rate", {"rate": 2.0}),
        "-": ("set_playback_rate", {"rate": 0.5}),
        "F": ("reverse_playback", {}),
    }
    
    def __init__(self, navigator: TimelineNavigator):
        self.navigator = navigator
    
    async def on_key_press(self, key: str) -> None:
        """Handle a keyboard press event."""
        if key not in self.KEYBOARD_SHORTCUTS:
            return
        
        action, args = self.KEYBOARD_SHORTCUTS[key]
        
        # Get the method from navigator
        method = getattr(self.navigator, action, None)
        if method and callable(method):
            if asyncio.iscoroutinefunction(method):
                await method(**args)
            else:
                method(**args)


# Convenience functions

def create_timeline(
    frames: List[Dict[str, Any]],
    fps: int = 30,
    loop_mode: bool = False,
) -> TimelineNavigator:
    """Create a configured timeline navigator."""
    config = TimelineConfig(
        fps_target=fps,
        loop_mode=loop_mode,
    )
    
    return TimelineNavigator(frames, config=config)


if __name__ == "__main__":
    import numpy as np
    
    print("=" * 60)
    print("Timeline Navigator Demo")
    print("=" * 60)
    
    # Create sample frames with poses
    frames = []
    for i in range(20):
        pose = {
            "latitude": 35.0 + np.sin(i * 0.5) * 1.0,
            "longitude": -120.0 + np.cos(i * 0.5) * 1.0,
            "altitude": 50000.0 - i * 500,
        }
        
        frame_data = {
            "timestamp": i * 1.0,
            "pose": pose,
            "metadata": {"frame_id": f"frame_{i:03d}"},
        }
        frames.append(frame_data)
    
    # Create navigator
    navigator = create_timeline(frames, fps=30, loop_mode=True)
    
    async def demo():
        await navigator.initialize()
        
        print(f"\nTimeline initialized with {navigator.total_frames} frames")
        print(f"Time range: {navigator.get_time_range()}")
        
        # Show current state
        print(f"\nCurrent state:")
        state = navigator.get_current_state()
        for key, value in state.items():
            if isinstance(value, dict):
                print(f"  {key}: {value}")
            else:
                print(f"  {key}: {value}")
        
        # Test navigation
        print("\nTesting navigation:")
        navigator.go_to_frame(5)
        print(f"  Frame 5: timestamp={navigator.current_frame['timestamp']}")
        
        navigator.go_to_first_frame()
        print(f"  First frame: index={navigator.state.current_frame_index}")
        
        # Test playback controls
        print("\nTesting playback:")
        await navigator.play(rate=1.0)
        await asyncio.sleep(0.5)
        print(f"  Playing: is_playing={navigator.is_playing}")
        
        await navigator.pause()
        print(f"  Paused at frame {navigator.state.current_frame_index}")
        
        await navigator.stop()
        print("  Playback stopped")
    
    # Run demo
    asyncio.run(demo())
    
    print("\nDemo complete!")
