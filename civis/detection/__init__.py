"""
Detection Engine Module for CIVIS.
"""

from civis.detection.models import (
    BoundingBox,
    Detection,
    DetectionResult,
    DetectorConfig,
)
from civis.detection.base import BaseDetector
from civis.detection.yolo_detector import YOLO12Detector
from civis.detection.mock_detector import MockDetector
from civis.detection.factory import create_detector

__all__ = [
    "BoundingBox",
    "Detection",
    "DetectionResult",
    "DetectorConfig",
    "BaseDetector",
    "YOLO12Detector",
    "MockDetector",
    "create_detector",
]
