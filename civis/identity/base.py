from abc import ABC, abstractmethod
from typing import List, Optional
import numpy as np

from civis.identity.models import (
    FaceCrop,
    FaceEmbedding,
    IdentityMatch,
    IdentityResult,
)
from civis.ingestion.models import FramePacket
from civis.tracking.models import TrackResult


class BaseFaceDetector(ABC):
    @abstractmethod
    def detect_faces(self, packet: FramePacket, track_result: TrackResult) -> List[FaceCrop]:
        """Extract face bounding box crops from tracked person objects."""
        pass


class BaseFaceQuality(ABC):
    @abstractmethod
    def assess_quality(self, crop: FaceCrop) -> float:
        """Calculate quality score for a face crop (0.0 to 1.0)."""
        pass


class BaseFaceAligner(ABC):
    @abstractmethod
    def align_face(self, crop: FaceCrop) -> FaceCrop:
        """Align face crop to canonical landmark pose."""
        pass


class BaseFaceEmbedder(ABC):
    @property
    @abstractmethod
    def dimension(self) -> int:
        """Vector embedding dimension (e.g. 512, 128, 256)."""
        pass

    @property
    @abstractmethod
    def model_version(self) -> str:
        """Version identifier of the underlying embedding model."""
        pass

    @abstractmethod
    def embed(self, crop: FaceCrop) -> Optional[FaceEmbedding]:
        """Extract normalized feature vector embedding from face crop."""
        pass


class BaseIdentityGallery(ABC):
    @abstractmethod
    def add_identity(self, identity_id: str, name: str, embedding: np.ndarray, model_version: str) -> None:
        """Register a reference identity vector in gallery memory."""
        pass

    @abstractmethod
    def search(self, embedding: FaceEmbedding, threshold: float) -> Optional[IdentityMatch]:
        """Search gallery for closest vector match above similarity threshold."""
        pass
