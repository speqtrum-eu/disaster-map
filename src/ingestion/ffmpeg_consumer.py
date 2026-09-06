import ffmpeg
import numpy as np
import cv2
from .base import BaseStreamConsumer, FrameData

class FFmpegStreamConsumer(BaseStreamConsumer):
    """Consumes video streams using FFmpeg."""

    def __init__(self, stream_url: str, stream_id: str):
        self.stream_url = stream_url
        self.stream_id = stream_id
        self._process = None
        self._is_running = False

    def connect(self) -> bool:
        """Initializes the FFmpeg process."""
        try:
            # We use pipe to read raw video frames from ffmpeg
            self._process = (
                ffmpeg
                .input(self.stream_url)
                .output('pipe:', format='rawvideo', pix_fmt='bgr24')
                .run_async(capture_stdout=True, capture_stderr=True)
            )
            self._is_running = True
            return True
        except Exception as e:
            print(f"Error connecting to stream {self.stream_url}: {e}")
            return False

    def disconnect(self) -> None:
        """Stops the FFmpeg process."""
        self._is_running = False
        if self._process:
            self._process.terminate()
            self._process.wait()
            self._process = None

    def get_next_frame(self, width: int, height: int) -> FrameData | None:
        """Reads the next frame from the pipe."""
        if not self._is_running or self._process is None:
            return None

        try:
            # Read raw bytes from stdout
            in_bytes = self._process.stdout.read(width * height * 3)
            if not in_bytes:
                return None

            # Convert to numpy array
            frame = np.frombuffer(in_bytes, np.uint8).reshape((height, width, 3))
            
            # In a real implementation, we'd get the actual timestamp from ffmpeg metadata
            # For now, using current time as placeholder
            import time
            return FrameData(
                timestamp=time.time(),
                data=frame,
                stream_id=self.stream_id
            )
        except Exception as e:
            print(f"Error reading frame from {self.stream_url}: {e}")
            return None

    def __del__(self):
        self.disconnect()
