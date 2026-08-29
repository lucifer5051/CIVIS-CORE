from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from civis.detection.models import BoundingBox


class TrackState(str, Enum):
    NEW = "new"
    TRACKED = "tracked"
    LOST = "lost"
    REMOVED = "removed"


@dataclass
class TrackedObject:
    track_id: int
    class_id: int
    class_name: str
    confidence: float
    bbox: BoundingBox
    state: TrackState = TrackState.NEW
    age: int = 1
    time_since_update: int = 0
    first_seen_timestamp: float = 0.0
    last_seen_timestamp: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TrackResult:
    camera_id: str
    frame_id: str
    timestamp: float
    frame_number: int
    dimensions: Tuple[int, int]
    tracks: List[TrackedObject]
    active_track_ids: List[int] = field(default_factory=list)
    processing_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def num_active_tracks(self) -> int:
        return len(self.active_track_ids)


class TrackerConfig(BaseModel):
    track_thresh: float = Field(default=0.5, ge=0.0, le=1.0, description="Detection confidence threshold for tracking")
    track_buffer: int = Field(default=30, ge=1, description="Number of frames to keep lost tracks before removal")
    match_thresh: float = Field(default=0.8, ge=0.0, le=1.0, description="Matching threshold for track association")
    frame_rate: int = Field(default=30, ge=1, description="Video frame rate for tracking motion models")
    use_mock: bool = Field(default=False, description="Whether to use MockTracker for unit testing")
