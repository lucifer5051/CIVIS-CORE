from civis.detection.base import BaseDetector
from civis.detection.mock_detector import MockDetector
from civis.detection.models import DetectorConfig
from civis.detection.yolo_detector import YOLO12Detector


def create_detector(config: DetectorConfig) -> BaseDetector:
    """
    Factory function to create appropriate detector instance based on configuration.
    Returns MockDetector if config.use_mock is True, else YOLO12Detector.
    """
    if config.use_mock:
        return MockDetector(config)
    return YOLO12Detector(config)
