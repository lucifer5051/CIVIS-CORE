from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field


class EvidenceStage(str, Enum):
    DETECTION = "detection"
    TRACKING = "tracking"
    IDENTITY = "identity"
    REID = "reid"
    BEHAVIOR = "behavior"
    EVENT_INTELLIGENCE = "event_intelligence"
    RISK_ASSESSMENT = "risk_assessment"


class CustodyAction(str, Enum):
    CAPTURED = "captured"
    ENRICHED = "enriched"
    SEALED = "sealed"
    VERIFIED = "verified"
    EXPORTED = "exported"
    ARCHIVED = "archived"
    PURGED = "purged"


@dataclass
class CustodyEntry:
    custody_id: str
    evidence_id: str
    timestamp: float
    action: CustodyAction
    actor: str  # Subsystem name, officer, or user ID
    prior_hash: str
    current_hash: str
    notes: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvidenceRecord:
    evidence_id: str
    sequence_number: int  # 0, 1, 2, ... in append-only ledger
    stage: EvidenceStage
    camera_id: str
    frame_id: str
    frame_number: int
    timestamp: float
    track_id: Optional[int] = None
    global_entity_id: Optional[str] = None
    identity_id: Optional[str] = None
    risk_score: Optional[float] = None
    severity: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    media_references: List[Dict[str, Any]] = field(default_factory=list)  # File paths, crop coords, timestamps
    parent_evidence_ids: List[str] = field(default_factory=list)  # Upstream evidence lineage
    previous_record_hash: str = ""  # Hash of record n-1 for block-chaining
    record_hash: str = ""  # SHA-256 of canonical payload + prev_hash
    custody_trail: List[CustodyEntry] = field(default_factory=list)
    is_sealed: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_high_risk(self) -> bool:
        if self.severity in ("high", "critical"):
            return True
        if self.risk_score is not None and self.risk_score >= 70.0:
            return True
        return False


@dataclass
class InvestigationTimeline:
    timeline_id: str
    title: str
    start_timestamp: float
    end_timestamp: float
    involved_cameras: List[str]
    involved_entities: List[str]
    total_records: int
    records: List[EvidenceRecord]
    integrity_verified: bool = True
    summary: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ForensicPackageManifest:
    package_id: str
    creation_timestamp: float
    total_files: int
    total_evidence_records: int
    root_ledger_hash: str
    file_checksums: Dict[str, str] = field(default_factory=dict)  # relative_filepath -> SHA-256
    is_valid: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


class RetentionPolicy(BaseModel):
    max_retention_days: float = Field(default=30.0, ge=0.01, description="Days before standard records expire")
    retain_high_risk_indefinitely: bool = Field(default=True, description="Always preserve HIGH/CRITICAL risk records")
    purge_interval_seconds: float = Field(default=3600.0, ge=1.0, description="Interval between retention evaluations")


class EvidenceEngineConfig(BaseModel):
    storage_directory: str = Field(default="./evidence_store", description="Root storage directory for ledger and exports")
    enable_hash_chain: bool = Field(default=True, description="Enable cryptographic hash chaining across records")
    max_ledger_records: Optional[int] = Field(default=None, description="Max active in-memory ledger records before archiving")
    retention_policy: RetentionPolicy = Field(default_factory=RetentionPolicy)
    auto_seal_alerts: bool = Field(default=True, description="Automatically seal evidence records associated with risk alerts")
    use_mock: bool = Field(default=False, description="Whether to run in mock mode")
    metadata: Dict[str, Any] = Field(default_factory=dict)
