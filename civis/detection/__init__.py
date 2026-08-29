"""
Detection Engine Module for CIVIS (including SAHI Small-Object Inference).
"""

from civis.detection.models import (
    BoundingBox,
    Detection,
    DetectionMode,
    DetectionResult,
    DetectorConfig,
    SAHIConfig,
)
from civis.detection.base import BaseDetector
from civis.detection.yolo_detector import YOLO12Detector
from civis.detection.mock_detector import MockDetector
from civis.detection.sahi_detector import SAHIDetector
from civis.detection.factory import create_detector

__all__ = [
    "BoundingBox",
    "Detection",
    "DetectionMode",
    "DetectionResult",
    "DetectorConfig",
    "SAHIConfig",
    "BaseDetector",
    "YOLO12Detector",
    "MockDetector",
    "SAHIDetector",
    "create_detector",
]
