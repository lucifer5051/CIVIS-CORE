from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field


@dataclass
class Point2D:
    x: float
    y: float

    def to_tuple(self) -> Tuple[float, float]:
        return (self.x, self.y)


@dataclass
class PolygonZone:
    zone_id: str
    name: str
    polygon: List[Point2D]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LineTripwire:
    tripwire_id: str
    name: str
    p1: Point2D
    p2: Point2D
    direction: str = "both"  # "both", "p1_to_p2", "p2_to_p1"
    metadata: Dict[str, Any] = field(default_factory=dict)


class BehaviorState(str, Enum):
    MOVING = "moving"
    STATIONARY = "stationary"
    DWELLING = "dwelling"
    LOITERING = "loitering"
    CROSSING_ZONE = "crossing_zone"
    PROXIMITY_NEAR = "proximity_near"


@dataclass
class BehaviorObservation:
    track_id: int
    camera_id: str
    identity_id: str
    state: BehaviorState
    speed_px_sec: float
    dwell_time_sec: float
    current_zones: List[str]
    proximity_track_ids: List[int]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BehaviorEvent:
    event_id: str
    camera_id: str
    frame_id: str
    timestamp: float
    event_type: str
    primary_track_id: int
    secondary_track_ids: List[int] = field(default_factory=list)
    identity_id: str = "UNKNOWN"
    zone_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BehaviorResult:
    camera_id: str
    frame_id: str
    timestamp: float
    frame_number: int
    dimensions: Tuple[int, int]
    observations: List[BehaviorObservation]
    events: List[BehaviorEvent]
    density_map: Dict[str, int] = field(default_factory=dict)
    processing_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def num_events(self) -> int:
        return len(self.events)


class BehaviorConfig(BaseModel):
    max_trajectory_seconds: float = Field(default=30.0, ge=1.0, description="Max history duration for track trajectory")
    stationary_speed_threshold_px_sec: float = Field(
        default=5.0, ge=0.0, description="Camera-dependent pixel speed threshold for motion"
    )
    dwell_threshold_seconds: float = Field(default=10.0, ge=1.0, description="Duration in seconds before loitering event")
    proximity_threshold_pixels: float = Field(
        default=50.0, ge=1.0, description="Geometric pixel closeness threshold for proximity"
    )
    proximity_class_filter: Optional[List[str]] = Field(
        default=None, description="Optional class filter for proximity checks (e.g. ['person', 'car'])"
    )
    crowd_density_threshold: int = Field(default=5, ge=1, description="Count threshold for crowd density event")
    event_cooldown_seconds: float = Field(
        default=5.0, ge=0.0, description="Event deduplication cooldown period in seconds"
    )
    zones: List[PolygonZone] = Field(default_factory=list, description="Configured ROI polygon zones")
    tripwires: List[LineTripwire] = Field(default_factory=list, description="Configured tripwire lines")
    use_mock: bool = Field(default=False, description="Whether to use MockBehaviorEngine for testing")
