from dataclasses import dataclass, field
import time
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from civis.behavior.models import BehaviorConfig
from civis.detection.models import DetectorConfig
from civis.event_intelligence.models import EventIntelligenceConfig
from civis.evidence.models import EvidenceEngineConfig
from civis.identity.models import IdentityConfig
from civis.ingestion.models import CameraConfig
from civis.observability.models import ObservabilityConfig
from civis.reid.models import ReIDEngineConfig
from civis.risk.models import RiskEngineConfig
from civis.runtime.models import PipelineRuntimeConfig
from civis.tracking.models import TrackerConfig


class PolicyRule(BaseModel):
    policy_id: str = Field(..., description="Unique policy identifier")
    name: str = Field(..., description="Human-readable policy name")
    enabled: bool = Field(default=True)
    priority: int = Field(default=10, ge=1, le=100, description="Priority ordering: 1 (highest) to 100")
    category: str = Field(default="operational", description="Category: operational, security, retention")
    conditions: Dict[str, Any] = Field(default_factory=dict)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CIVISConfig(BaseModel):
    """
    Centralized, fully-composed configuration schema for the complete CIVIS-CORE pipeline.
    """
    project_name: str = Field(default="CIVIS-CORE", description="Project namespace")
    version: str = Field(default="1.0.0", description="Configuration version")
    environment: str = Field(default="development", description="Environment: development, staging, production")
    device: str = Field(default="cpu", description="Global default device: 'cpu' or 'cuda:0'")

    # Subsystem Configurations
    cameras: List[CameraConfig] = Field(default_factory=list)
    detection: DetectorConfig = Field(default_factory=DetectorConfig)
    tracking: TrackerConfig = Field(default_factory=TrackerConfig)
    identity: IdentityConfig = Field(default_factory=IdentityConfig)
    reid: ReIDEngineConfig = Field(default_factory=ReIDEngineConfig)
    behavior: BehaviorConfig = Field(default_factory=BehaviorConfig)
    event_intelligence: EventIntelligenceConfig = Field(default_factory=EventIntelligenceConfig)
    risk: RiskEngineConfig = Field(default_factory=RiskEngineConfig)
    evidence: EvidenceEngineConfig = Field(default_factory=EvidenceEngineConfig)
    runtime: PipelineRuntimeConfig = Field(default_factory=PipelineRuntimeConfig)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)
    policies: List[PolicyRule] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


@dataclass
class ConfigDiff:
    added: Dict[str, Any] = field(default_factory=dict)
    removed: Dict[str, Any] = field(default_factory=dict)
    changed: Dict[str, Tuple[Any, Any]] = field(default_factory=dict)  # key -> (old_val, new_val)

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.removed or self.changed)


@dataclass
class ConfigSnapshot:
    snapshot_id: str
    timestamp: float
    version: str
    checksum: str  # SHA-256 of canonical JSON
    config_data: Dict[str, Any]
    is_sanitized: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConfigUpdateResult:
    success: bool
    applied_changes: Dict[str, Any] = field(default_factory=dict)
    requires_restart: bool = False
    validation_errors: List[str] = field(default_factory=list)
    snapshot: Optional[ConfigSnapshot] = None
