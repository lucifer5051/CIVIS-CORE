from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field


class EventState(str, Enum):
    ACTIVE = "active"
    RESOLVED = "resolved"
    EXPIRED = "expired"


class LogicOperator(str, Enum):
    AND = "AND"
    OR = "OR"
    SEQUENCE = "SEQUENCE"


class ConfidenceAggregation(str, Enum):
    AVERAGE = "average"
    MIN = "min"
    MAX = "max"
    WEIGHTED = "weighted"


@dataclass
class EvidenceItem:
    evidence_type: str
    source_module: str
    timestamp: float
    camera_id: str
    track_id: Optional[int] = None
    identity_id: Optional[str] = None
    description: str = ""
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Condition:
    condition_type: str  # e.g., "BEHAVIOR_TYPE", "IDENTITY_STATE", "ZONE_ID", "EVENT_TYPE", "MIN_SPEED"
    target_value: Any
    operator: str = "=="  # "==", ">=", "<=", "IN", "!="
    weight: float = 1.0


@dataclass
class EventRule:
    rule_id: str
    name: str
    description: str
    logic_operator: LogicOperator = LogicOperator.AND
    conditions: List[Condition] = field(default_factory=list)
    temporal_window_seconds: float = 30.0
    cooldown_seconds: float = 5.0
    confidence_aggregation: ConfidenceAggregation = ConfidenceAggregation.AVERAGE
    min_confidence: float = 0.5
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CorrelatedEvent:
    event_id: str
    rule_id: str
    name: str
    state: EventState
    camera_id: str
    primary_track_id: int
    secondary_track_ids: List[int] = field(default_factory=list)
    primary_identity_id: str = "UNKNOWN"
    start_timestamp: float = 0.0
    last_updated_timestamp: float = 0.0
    overall_confidence: float = 0.0
    evidence_chain: List[EvidenceItem] = field(default_factory=list)
    explanation: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EventIntelligenceResult:
    camera_id: str
    frame_id: str
    timestamp: float
    frame_number: int
    dimensions: Tuple[int, int]
    events: List[CorrelatedEvent]
    processing_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def num_active_events(self) -> int:
        return sum(1 for e in self.events if e.state == EventState.ACTIVE)


class EventIntelligenceConfig(BaseModel):
    temporal_window_seconds: float = Field(default=60.0, ge=1.0, description="Max history sliding window for event correlation")
    expiry_timeout_seconds: float = Field(default=10.0, ge=1.0, description="Inactivity duration before active event expires")
    rules: List[EventRule] = Field(default_factory=list, description="Configured data-driven event rules")
    use_mock: bool = Field(default=False, description="Whether to use MockEventIntelligenceEngine for testing")
