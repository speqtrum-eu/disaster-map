from abc import ABC, abstractmethod
from dataclasses import dataclass
import numpy as np

@dataclass
class FrameData:
    """Represents a single frame extracted from a stream."""
    timestamp: float
    data: np.ndarray  # Image data (H, W, C)
    stream_id: str

class BaseStreamConsumer(ABC):
    """Abstract base class for all stream consumers."""

    @abstractmethod
    def connect(self) -> bool:
        """Connect to the stream source."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from the stream source."""
        pass

    @abstractmethod
    def get_next_frame(self) -> FrameData | None:
        """Retrieve the next frame from the stream."""
        pass
