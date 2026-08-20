"""
Frame storage for raw and processed frames
"""

import os
import json
import time
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import threading

import numpy as np

from ..core.models import Frame
from ..core.utils import get_logger, ensure_directory, timestamp_now

logger = get_logger("storage.frame_storage")


@dataclass
class FrameStorage:
    """
    Stores raw and processed frames
    
    Supports multiple backends:
    - filesystem: Save frames as images on disk
    - memory: Keep frames in memory (with size limit)
    """
    
    backend: str = "filesystem"  # filesystem, memory
    path: str = "data/frames"
    max_frames: int = 10000  # Maximum frames to store
    quality: int = 85  # JPEG quality (0-100)
    save_raw: bool = True  # Save raw frames
    save_processed: bool = True  # Save processed frames
    
    def __post_init__(self):
        self._path = Path(self.path)
        if self.backend == "filesystem":
            ensure_directory(self.path)
        self._lock = threading.Lock()
        self._memory_store: Dict[str, Frame] = {}
        self._access_order: List[str] = []
    
    def save_frame(self, frame: Frame, processed: bool = False) -> bool:
        """Save a frame"""
        if self.backend == "filesystem":
            return self._save_filesystem(frame, processed)
        elif self.backend == "memory":
            return self._save_memory(frame, processed)
        else:
            logger.warning(f"Unknown backend: {self.backend}")
            return False
    
    def _save_filesystem(self, frame: Frame, processed: bool = False) -> bool:
        """Save frame to filesystem"""
        if frame.data is None:
            logger.warning("Cannot save frame with no data")
            return False
        
        try:
            # Create subdirectory based on stream and timestamp
            date = time.strftime("%Y%m%d", time.localtime(frame.timestamp))
            hour = time.strftime("%H", time.localtime(frame.timestamp))
            
            if processed:
                subdir = self._path / frame.stream_id / "processed" / date / hour
            else:
                subdir = self._path / frame.stream_id / "raw" / date / hour
            
            ensure_directory(subdir)
            
            # Save as PNG
            filename = f"{frame.timestamp}_{frame.frame_number}.png"
            file_path = subdir / filename
            
            success = cv2.imwrite(str(file_path), frame.data, [cv2.IMWRITE_PNG_COMPRESSION, 9])
            
            if success:
                logger.debug(f"Saved frame {frame.id} to {file_path}")
                
                # Save metadata
                meta_path = file_path.with_suffix(".json")
                with open(meta_path, "w") as f:
                    json.dump(frame.to_dict(), f, indent=2)
                
                return True
            else:
                logger.error(f"Failed to save frame {frame.id}")
                return False
                
        except Exception as e:
            logger.error(f"Error saving frame: {e}")
            return False
    
    def _save_memory(self, frame: Frame, processed: bool = False) -> bool:
        """Save frame to memory"""
        with self._lock:
            # Check if we have space
            if len(self._memory_store) >= self.max_frames:
                # Remove oldest frame
                if self._access_order:
                    oldest_id = self._access_order.pop(0)
                    if oldest_id in self._memory_store:
                        del self._memory_store[oldest_id]
            
            # Store frame
            self._memory_store[frame.id] = frame
            self._access_order.append(frame.id)
            
            return True
    
    def get_frame(self, frame_id: str) -> Optional[Frame]:
        """Get a frame by ID"""
        if self.backend == "filesystem":
            return self._get_filesystem(frame_id)
        elif self.backend == "memory":
            return self._get_memory(frame_id)
        else:
            logger.warning(f"Unknown backend: {self.backend}")
            return None
    
    def _get_filesystem(self, frame_id: str) -> Optional[Frame]:
        """Get frame from filesystem"""
        # This would need to search for the frame file
        # For now, not implemented as it requires indexing
        logger.warning("Getting frames from filesystem not implemented")
        return None
    
    def _get_memory(self, frame_id: str) -> Optional[Frame]:
        """Get frame from memory"""
        with self._lock:
            if frame_id in self._memory_store:
                # Move to end of access order
                self._access_order.remove(frame_id)
                self._access_order.append(frame_id)
                return self._memory_store[frame_id]
            return None
    
    def list_frames(
        self,
        stream_id: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: Optional[int] = None
    ) -> List[Frame]:
        """List frames matching criteria"""
        if self.backend == "filesystem":
            return self._list_filesystem(stream_id, start_time, end_time, limit)
        elif self.backend == "memory":
            return self._list_memory(stream_id, start_time, end_time, limit)
        else:
            logger.warning(f"Unknown backend: {self.backend}")
            return []
    
    def _list_filesystem(
        self,
        stream_id: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: Optional[int] = None
    ) -> List[Frame]:
        """List frames from filesystem"""
        # This would need to search the filesystem
        # For now, not implemented
        logger.warning("Listing frames from filesystem not implemented")
        return []
    
    def _list_memory(
        self,
        stream_id: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: Optional[int] = None
    ) -> List[Frame]:
        """List frames from memory"""
        with self._lock:
            frames = []
            for frame in self._memory_store.values():
                if stream_id and frame.stream_id != stream_id:
                    continue
                if start_time and frame.timestamp < start_time:
                    continue
                if end_time and frame.timestamp > end_time:
                    continue
                frames.append(frame)
            
            # Sort by timestamp
            frames.sort(key=lambda f: f.timestamp, reverse=True)
            
            if limit:
                frames = frames[:limit]
            
            return frames
    
    def delete_frame(self, frame_id: str) -> bool:
        """Delete a frame"""
        if self.backend == "filesystem":
            return self._delete_filesystem(frame_id)
        elif self.backend == "memory":
            return self._delete_memory(frame_id)
        else:
            logger.warning(f"Unknown backend: {self.backend}")
            return False
    
    def _delete_filesystem(self, frame_id: str) -> bool:
        """Delete frame from filesystem"""
        # This would need to find and delete the frame file
        logger.warning("Deleting frames from filesystem not implemented")
        return False
    
    def _delete_memory(self, frame_id: str) -> bool:
        """Delete frame from memory"""
        with self._lock:
            if frame_id in self._memory_store:
                del self._memory_store[frame_id]
                if frame_id in self._access_order:
                    self._access_order.remove(frame_id)
                return True
            return False
    
    def clear_all(self) -> None:
        """Clear all stored frames"""
        if self.backend == "filesystem":
            # Would need to delete all frame files
            logger.warning("Clearing all filesystem frames not implemented")
        elif self.backend == "memory":
            with self._lock:
                self._memory_store.clear()
                self._access_order.clear()
        
        logger.info("Cleared all frames")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics"""
        with self._lock:
            if self.backend == "filesystem":
                # Count frames in filesystem
                frame_count = 0
                total_size = 0
                
                for root, dirs, files in os.walk(self._path):
                    for file in files:
                        if file.endswith(".png"):
                            frame_count += 1
                            file_path = Path(root) / file
                            total_size += os.path.getsize(file_path)
                
                return {
                    "backend": self.backend,
                    "frame_count": frame_count,
                    "total_size_bytes": total_size,
                }
            elif self.backend == "memory":
                return {
                    "backend": self.backend,
                    "frame_count": len(self._memory_store),
                    "max_frames": self.max_frames,
                }
            else:
                return {
                    "backend": self.backend,
                    "error": "Unknown backend"
                }


# Import cv2
try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False
    logger.warning("OpenCV not available, frame storage will not work")
