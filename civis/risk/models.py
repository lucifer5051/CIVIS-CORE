import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
from pydantic import BaseModel, Field


class RiskSeverity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @classmethod
    def from_score(
        cls,
        score: float,
        current_severity: Optional["RiskSeverity"] = None,
        hysteresis: float = 3.0,
    ) -> "RiskSeverity":
        """
        Maps continuous score [0.0, 100.0] to discrete RiskSeverity with hysteresis
        to prevent fluttering across threshold boundaries.
        """
        score = max(0.0, min(100.0, score))
        
        # Base threshold intervals:
        # INFO: [0, 20)
        # LOW: [20, 40)
        # MEDIUM: [40, 70)
        # HIGH: [70, 90)
        # CRITICAL: [90, 100]

        if current_severity is None:
            if score >= 90.0:
                return cls.CRITICAL
            elif score >= 70.0:
                return cls.HIGH
            elif score >= 40.0:
                return cls.MEDIUM
            elif score >= 20.0:
                return cls.LOW
            else:
                return cls.INFO

        # With hysteresis:
        # Escalation uses strict thresholds.
        # De-escalation requires dropping below threshold - hysteresis.
        if current_severity == cls.CRITICAL:
            if score < (90.0 - hysteresis):
                return cls.from_score(score, None)
            return cls.CRITICAL

        elif current_severity == cls.HIGH:
            if score >= 90.0:
                return cls.CRITICAL
            if score < (70.0 - hysteresis):
                return cls.from_score(score, None)
            return cls.HIGH

        elif current_severity == cls.MEDIUM:
            if score >= 90.0:
                return cls.CRITICAL
            elif score >= 70.0:
                return cls.HIGH
            elif score < (40.0 - hysteresis):
                return cls.from_score(score, None)
            return cls.MEDIUM

        elif current_severity == cls.LOW:
            if score >= 90.0:
                return cls.CRITICAL
            elif score >= 70.0:
                return cls.HIGH
            elif score >= 40.0:
                return cls.MEDIUM
            elif score < (20.0 - hysteresis):
                return cls.INFO
            return cls.LOW

        else:  # INFO
            if score >= 90.0:
                return cls.CRITICAL
            elif score >= 70.0:
                return cls.HIGH
            elif score >= 40.0:
                return cls.MEDIUM
            elif score >= 20.0:
                return cls.LOW
            return cls.INFO


class RiskState(str, Enum):
    NEW = "new"
    ACTIVE = "active"
    ESCALATED = "escalated"
    DE_ESCALATING = "de_escalating"
    RESOLVED = "resolved"


class ThreatCategory(str, Enum):
    SECURITY_INTRUSION = "security_intrusion"
    LOITERING_PROWLING = "loitering_prowling"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    CROWD_ANOMALY = "crowd_anomaly"
    PROXIMITY_HAZARD = "proximity_hazard"
    GENERAL_SUSPICIOUS = "general_suspicious"


class ContextMultiplier(BaseModel):
    condition_type: str  # e.g., "ZONE_RESTRICTED", "UNKNOWN_IDENTITY", "UNVERIFIED_IDENTITY", "PROXIMITY_ALERT"
    target_value: Any
    multiplier: float = Field(default=1.25, ge=1.0, description="Risk score amplification factor")
    description: str = Field(default="", description="Reason for the multiplier")


class RiskRule(BaseModel):
    rule_id: str = Field(..., description="Unique rule identifier")
    name: str = Field(..., description="Human-readable rule name")
    category: ThreatCategory = Field(default=ThreatCategory.GENERAL_SUSPICIOUS)
    priority: int = Field(default=1, ge=0, description="Rule priority for deterministic evaluation (higher = higher priority)")
    base_severity_score: float = Field(..., ge=0.0, le=100.0, description="Base impact magnitude (0-100)")
    required_events: List[str] = Field(default_factory=list, description="Matching CorrelatedEvent rule_ids or names")
    required_behaviors: List[str] = Field(default_factory=list, description="Matching BehaviorEvent event_types or states")
    required_identity_states: List[str] = Field(default_factory=list, description="e.g. ['unknown', 'unverified']")
    context_multipliers: List[ContextMultiplier] = Field(default_factory=list)
    escalation_rate_per_sec: float = Field(default=2.0, ge=0.0, description="Score growth per second of persistence")
    max_escalated_score: float = Field(default=100.0, ge=0.0, le=100.0, description="Cap for temporal escalation")
    de_escalation_half_life_sec: float = Field(default=8.0, ge=0.5, description="Exponential decay half-life in seconds")
    cooldown_seconds: float = Field(default=10.0, ge=0.0, description="Cooldown between identical alerts")
    min_confidence: float = Field(default=0.3, ge=0.0, le=1.0, description="Minimum confidence threshold to trigger")
    weight: float = Field(default=1.0, ge=0.0, description="Configurable rule weight in multi-signal calculations")
    metadata: Dict[str, Any] = Field(default_factory=dict)


@dataclass
class RiskContribution:
    source_type: str  # "correlated_event", "behavior_event", "identity_anomaly", "spatial_context"
    source_id: str
    name: str
    base_score: float
    confidence: float
    weight: float = 1.0
    applied_multipliers: List[Dict[str, Any]] = field(default_factory=list)
    effective_score: float = 0.0
    evidence_references: List[Any] = field(default_factory=list)


@dataclass
class RiskAssessment:
    assessment_id: str
    entity_key: str  # "ident_{identity_id}" or "cam_{camera_id}_trk_{track_id}"
    camera_id: str
    track_id: int
    identity_id: str
    state: RiskState
    category: ThreatCategory
    severity: RiskSeverity
    severity_score: float  # 0.0 - 100.0
    confidence: float  # 0.0 - 1.0
    start_timestamp: float
    last_updated_timestamp: float
    peak_severity_score: float
    contributions: List[RiskContribution] = field(default_factory=list)
    evidence_chain: List[Any] = field(default_factory=list)
    explanation: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        return self.state in (RiskState.NEW, RiskState.ACTIVE, RiskState.ESCALATED, RiskState.DE_ESCALATING)


@dataclass
class RiskAlert:
    alert_id: str
    assessment_id: str
    timestamp: float
    camera_id: str
    entity_key: str
    severity: RiskSeverity
    severity_score: float
    confidence: float
    headline: str
    explanation: str
    contributing_event_names: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskAssessmentResult:
    camera_id: str
    frame_id: str
    timestamp: float
    frame_number: int
    dimensions: Tuple[int, int]
    assessments: List[RiskAssessment]
    alerts: List[RiskAlert]
    processing_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def num_active_assessments(self) -> int:
        return sum(1 for a in self.assessments if a.is_active)

    @property
    def num_alerts(self) -> int:
        return len(self.alerts)


class RiskEngineConfig(BaseModel):
    rules: List[RiskRule] = Field(default_factory=list, description="Configured risk assessment rules")
    hysteresis: float = Field(default=3.0, ge=0.0, le=10.0, description="Hysteresis margin for severity band de-escalation")
    alert_score_delta_threshold: float = Field(default=15.0, ge=1.0, description="Score delta required to trigger alert update")
    alert_cooldown_seconds: float = Field(default=15.0, ge=1.0, description="Alert throttle interval for active risks")
    resolution_timeout_seconds: float = Field(default=10.0, ge=1.0, description="Inactivity timeout before resolving an assessment")
    min_alert_severity: RiskSeverity = Field(default=RiskSeverity.LOW, description="Minimum severity level that generates an alert")
    use_mock: bool = Field(default=False, description="Whether to run in Mock mode")
    metadata: Dict[str, Any] = Field(default_factory=dict)
