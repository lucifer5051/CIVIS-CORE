from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import numpy as np

from civis.identity.models import IdentityResult
from civis.ingestion.models import FramePacket
from civis.reid.models import (
    AppearanceEmbedding,
    CrossCameraReIDResult,
    ReIDEngineConfig,
)
from civis.tracking.models import TrackResult


class BaseAppearanceEmbedder(ABC):
    """
    Abstract interface for Person Appearance Feature Extractor.
    Extracts L2-normalized 512-d feature vectors from full-body person crops.
    """

    @abstractmethod
    def extract_embedding(
        self,
        crop_image: np.ndarray,
        camera_id: str,
        track_id: int,
        timestamp: float,
    ) -> Optional[AppearanceEmbedding]:
        """Extract a 512-dimensional appearance embedding from an RGB person crop."""
        pass

    @abstractmethod
    def extract_batch(
        self,
        crops: List[np.ndarray],
        camera_ids: List[str],
        track_ids: List[int],
        timestamp: float,
    ) -> List[Optional[AppearanceEmbedding]]:
        """Extract embeddings for a batch of person crops."""
        pass


class BaseCrossCameraEngine(ABC):
    """
    Abstract Base Class for CIVIS Cross-Camera Re-ID and Global Entity Tracking.
    """

    def __init__(self, config: ReIDEngineConfig) -> None:
        self._config = config

    @property
    def config(self) -> ReIDEngineConfig:
        return self._config

    @abstractmethod
    def process(
        self,
        frame_packets: Dict[str, FramePacket],
        track_results: Dict[str, TrackResult],
        identity_results: Optional[Dict[str, IdentityResult]] = None,
    ) -> CrossCameraReIDResult:
        """
        Process multi-camera frame and track streams to perform cross-camera appearance matching
        and global entity lifecycle management.
        """
        pass

    @abstractmethod
    def reset(self, camera_id: Optional[str] = None) -> None:
        """Reset appearance galleries and global entity memory."""
        pass
