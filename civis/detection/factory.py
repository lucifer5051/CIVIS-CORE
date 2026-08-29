from civis.detection.base import BaseDetector
from civis.detection.mock_detector import MockDetector
from civis.detection.models import DetectorConfig
from civis.detection.sahi_detector import SAHIDetector
from civis.detection.yolo_detector import YOLO12Detector


def create_detector(config: DetectorConfig) -> BaseDetector:
    """
    Factory function to create appropriate detector instance based on configuration.
    Wraps base detector with SAHIDetector if config.sahi_config is specified.
    """
    if config.use_mock:
        base_detector = MockDetector(config)
    else:
        base_detector = YOLO12Detector(config)

    if config.sahi_config is not None:
        return SAHIDetector(base_detector, config.sahi_config)

    return base_detector
