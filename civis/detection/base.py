from abc import ABC, abstractmethod
from typing import List

from civis.detection.models import DetectionResult, DetectorConfig
from civis.ingestion.models import FramePacket


class BaseDetector(ABC):
    """
    Abstract Base Class for all object detectors in CIVIS.
    Directly consumes FramePacket produced by the Ingestion Module.
    """

    def __init__(self, config: DetectorConfig) -> None:
        self._config = config

    @property
    def config(self) -> DetectorConfig:
        return self._config

    @abstractmethod
    def detect(self, packet: FramePacket) -> DetectionResult:
        """Run object detection on a single FramePacket."""
        pass

    def detect_batch(self, packets: List[FramePacket]) -> List[DetectionResult]:
        """Run object detection on a list/batch of FramePackets."""
        return [self.detect(pkt) for pkt in packets]
