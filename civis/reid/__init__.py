"""
Cross-Camera Person Re-Identification & Global Entity Tracking Subsystem for CIVIS.
"""

from civis.reid.base import BaseAppearanceEmbedder, BaseCrossCameraEngine
from civis.reid.embedder import MockAppearanceEmbedder, OSNetEmbedder
from civis.reid.engine import CrossCameraReIDEngine, MockCrossCameraEngine
from civis.reid.factory import create_cross_camera_reid_engine
from civis.reid.gallery import CrossCameraGallery
from civis.reid.matcher import CrossCameraMatcher
from civis.reid.models import (
    AppearanceEmbedding,
    CameraTopologyConstraint,
    CameraTrackBinding,
    CrossCameraMatch,
    CrossCameraReIDResult,
    GlobalEntity,
    MatchStatus,
    ReIDEngineConfig,
)

__all__ = [
    "AppearanceEmbedding",
    "CameraTopologyConstraint",
    "CameraTrackBinding",
    "CrossCameraMatch",
    "CrossCameraReIDResult",
    "GlobalEntity",
    "MatchStatus",
    "ReIDEngineConfig",
    "BaseAppearanceEmbedder",
    "BaseCrossCameraEngine",
    "OSNetEmbedder",
    "MockAppearanceEmbedder",
    "CrossCameraGallery",
    "CrossCameraMatcher",
    "CrossCameraReIDEngine",
    "MockCrossCameraEngine",
    "create_cross_camera_reid_engine",
]
