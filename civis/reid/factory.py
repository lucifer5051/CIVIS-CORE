from typing import Optional

from civis.reid.base import BaseCrossCameraEngine
from civis.reid.engine import CrossCameraReIDEngine, MockCrossCameraEngine
from civis.reid.models import ReIDEngineConfig


def create_cross_camera_reid_engine(config: Optional[ReIDEngineConfig] = None) -> BaseCrossCameraEngine:
    """
    Factory method to instantiate a CIVIS Cross-Camera Re-ID Engine.
    """
    cfg = config if config is not None else ReIDEngineConfig()
    if cfg.use_mock:
        return MockCrossCameraEngine(cfg)
    return CrossCameraReIDEngine(cfg)
