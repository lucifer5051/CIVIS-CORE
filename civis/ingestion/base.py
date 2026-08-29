from abc import ABC, abstractmethod
from typing import Optional
from civis.ingestion.models import CameraConfig, CameraStatus, FramePacket


class VideoSource(ABC):
    """
    Abstract base class for all video sources in CIVIS.
    Provides a standardized interface for stream start, stop, frame reading, and status monitoring.
    """

    def __init__(self, config: CameraConfig) -> None:
        self._config = config

    @property
    def camera_id(self) -> str:
        return self._config.camera_id

    @property
    def config(self) -> CameraConfig:
        return self._config

    @abstractmethod
    def start(self) -> None:
        """Start capturing from the video source."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop capturing and release resources cleanly."""
        pass

    @abstractmethod
    def read(self, timeout: float = 1.0) -> Optional[FramePacket]:
        """Read the next FramePacket from the source queue."""
        pass

    @abstractmethod
    def get_status(self) -> CameraStatus:
        """Get current operational status of the video source."""
        pass

    def __enter__(self) -> "VideoSource":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()
