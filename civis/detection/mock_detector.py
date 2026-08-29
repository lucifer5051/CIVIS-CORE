import time
from typing import List, Optional
from civis.detection.base import BaseDetector
from civis.detection.models import BoundingBox, Detection, DetectionResult, DetectorConfig
from civis.ingestion.models import FramePacket


class MockDetector(BaseDetector):
    """
    Mock detector for unit testing and offline development without weight downloads.
    """

    def __init__(self, config: Optional[DetectorConfig] = None) -> None:
        cfg = config if config is not None else DetectorConfig(use_mock=True)
        super().__init__(cfg)

    def detect(self, packet: FramePacket) -> DetectionResult:
        start_time = time.perf_counter()

        width, height = packet.dimensions

        # Generate mock detections (e.g. 2 objects: person, car)
        detections: List[Detection] = [
            Detection(
                class_id=0,
                class_name="person",
                confidence=0.92,
                bbox=BoundingBox(
                    x1=float(width * 0.1),
                    y1=float(height * 0.2),
                    x2=float(width * 0.4),
                    y2=float(height * 0.8),
                ),
            ),
            Detection(
                class_id=2,
                class_name="car",
                confidence=0.88,
                bbox=BoundingBox(
                    x1=float(width * 0.5),
                    y1=float(height * 0.4),
                    x2=float(width * 0.9),
                    y2=float(height * 0.85),
                ),
            ),
        ]

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        return DetectionResult(
            camera_id=packet.camera_id,
            frame_id=packet.frame_id,
            timestamp=packet.timestamp,
            frame_number=packet.frame_number,
            dimensions=packet.dimensions,
            detections=detections,
            inference_time_ms=elapsed_ms,
            metadata={"engine": "MockDetector"},
        )
