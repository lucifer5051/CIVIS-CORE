from abc import ABC, abstractmethod
from typing import Optional

from civis.detection.models import DetectionResult
from civis.tracking.models import TrackResult, TrackerConfig


class BaseTracker(ABC):
    """
    Abstract Base Class for all multi-object trackers in CIVIS.
    Consumes standardized DetectionResult payloads directly.
    Maintains camera-scoped isolated tracking state.
    """

    def __init__(self, config: TrackerConfig) -> None:
        self._config = config

    @property
    def config(self) -> TrackerConfig:
        return self._config

    @abstractmethod
    def update(self, detection_result: DetectionResult) -> TrackResult:
        """Update tracker state with incoming DetectionResult for a camera."""
        pass

    @abstractmethod
    def reset(self, camera_id: Optional[str] = None) -> None:
        """Reset tracker state for a specific camera or all cameras."""
        pass
