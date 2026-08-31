from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from pydantic import BaseModel, Field


class MatchStatus(str, Enum):
    CONFIRMED = "confirmed"
    TENTATIVE = "tentative"
    REJECTED_SIMILARITY = "rejected_similarity"
    REJECTED_TOPOLOGY = "rejected_topology"
    REJECTED_TEMPORAL = "rejected_temporal"


@dataclass
class AppearanceEmbedding:
    camera_id: str
    track_id: int
    timestamp: float
    embedding: np.ndarray  # (512,) float32, L2-normalized
    dimension: int = 512
    quality_score: float = 1.0
    crop_dimensions: Tuple[int, int] = (0, 0)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CameraTrackBinding:
    camera_id: str
    track_id: int
    first_seen: float
    last_seen: float
    last_bbox: Tuple[float, float, float, float]  # (x1, y1, x2, y2)
    observations_count: int = 1
    appearance_confidence: float = 1.0


@dataclass
class GlobalEntity:
    global_entity_id: str
    associated_tracks: List[CameraTrackBinding] = field(default_factory=list)
    primary_identity_id: Optional[str] = None  # Attached if verified by civis.identity
    first_seen_timestamp: float = 0.0
    last_seen_timestamp: float = 0.0
    mean_embedding: Optional[np.ndarray] = None
    is_active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def num_associated_cameras(self) -> int:
        return len({t.camera_id for t in self.associated_tracks})

    @property
    def total_observations(self) -> int:
        return sum(t.observations_count for t in self.associated_tracks)


@dataclass
class CrossCameraMatch:
    query_camera_id: str
    query_track_id: int
    matched_camera_id: str
    matched_track_id: int
    global_entity_id: str
    similarity_score: float
    time_delta_seconds: float
    status: MatchStatus = MatchStatus.CONFIRMED
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CrossCameraReIDResult:
    timestamp: float
    global_entities: List[GlobalEntity]
    active_matches: List[CrossCameraMatch]
    processing_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def num_active_entities(self) -> int:
        return sum(1 for e in self.global_entities if e.is_active)

    @property
    def num_matches(self) -> int:
        return len(self.active_matches)


class CameraTopologyConstraint(BaseModel):
    source_camera_id: str = Field(..., description="Source camera ID")
    target_camera_id: str = Field(..., description="Target camera ID")
    min_travel_time_sec: float = Field(default=0.5, ge=0.0, description="Minimum realistic walking time between cameras")
    max_travel_time_sec: float = Field(default=180.0, ge=1.0, description="Maximum transition interval between cameras")
    allow_bidirectional: bool = Field(default=True, description="Whether constraint applies symmetrically")


class ReIDEngineConfig(BaseModel):
    model_name: str = Field(default="osnet_x1_0", description="OSNet backbone architecture name")
    weights_path: Optional[str] = Field(default=None, description="Optional custom weights file path")
    device: str = Field(default="cuda", description="Inference device ('cuda' or 'cpu')")
    similarity_threshold: float = Field(default=0.70, ge=0.0, le=1.0, description="Minimum cosine similarity for cross-camera link")
    ema_alpha: float = Field(default=0.7, ge=0.1, le=1.0, description="Exponential moving average weight for track embedding update")
    gallery_ttl_seconds: float = Field(default=120.0, ge=1.0, description="Memory retention duration for inactive track appearances")
    topology_constraints: List[CameraTopologyConstraint] = Field(default_factory=list, description="Spatial-temporal camera transition limits")
    min_crop_height: int = Field(default=64, ge=16, description="Minimum bounding box height for appearance extraction")
    min_crop_width: int = Field(default=32, ge=16, description="Minimum bounding box width for appearance extraction")
    use_mock: bool = Field(default=False, description="Whether to run in Mock mode")
    metadata: Dict[str, Any] = Field(default_factory=dict)
