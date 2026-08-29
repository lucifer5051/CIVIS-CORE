from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from pydantic import BaseModel, Field

from civis.detection.models import BoundingBox


class IdentityState(str, Enum):
    KNOWN = "known"
    UNKNOWN = "unknown"
    UNVERIFIED = "unverified"


@dataclass
class FaceCrop:
    face_id: str
    track_id: int
    camera_id: str
    bbox: BoundingBox
    crop_img: Optional[np.ndarray] = None
    quality_score: float = 0.0
    is_valid: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FaceEmbedding:
    face_id: str
    embedding: np.ndarray
    dimension: int
    model_version: str
    norm: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IdentityMatch:
    identity_id: str
    name: str
    similarity_score: float
    is_known: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AssociatedIdentity:
    track_id: int
    camera_id: str
    identity_id: str
    name: str
    state: IdentityState
    similarity_score: float
    recognition_confidence: float
    association_confidence: float
    observations_count: int
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IdentityResult:
    camera_id: str
    frame_id: str
    timestamp: float
    frame_number: int
    dimensions: Tuple[int, int]
    identities: List[AssociatedIdentity]
    processing_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def num_known(self) -> int:
        return sum(1 for i in self.identities if i.state == IdentityState.KNOWN)

    @property
    def num_unknown(self) -> int:
        return sum(1 for i in self.identities if i.state == IdentityState.UNKNOWN)

    @property
    def num_unverified(self) -> int:
        return sum(1 for i in self.identities if i.state == IdentityState.UNVERIFIED)


class IdentityConfig(BaseModel):
    similarity_threshold: float = Field(
        default=0.6, ge=0.0, le=1.0, description="Similarity score threshold for vector match"
    )
    min_quality_score: float = Field(
        default=0.4, ge=0.0, le=1.0, description="Minimum face quality score required for embedding"
    )
    min_observations: int = Field(
        default=3, ge=1, description="Minimum observations required to transition from UNVERIFIED to KNOWN"
    )
    track_memory_buffer: int = Field(
        default=30, ge=1, description="Number of frames to retain identity memory for lost tracks"
    )
    store_face_crops: bool = Field(
        default=False, description="Whether to store raw face crop image matrices in memory/output"
    )
    store_embeddings: bool = Field(
        default=False, description="Whether to store raw feature vectors in memory/output"
    )
    retention_ttl_seconds: Optional[int] = Field(
        default=None, description="Optional retention lifecycle limit (TTL) for biometric references"
    )
    use_mock: bool = Field(default=False, description="Whether to use MockIdentityEngine for testing")
