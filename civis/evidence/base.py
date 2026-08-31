from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple

from civis.behavior.models import BehaviorResult
from civis.detection.models import DetectionResult
from civis.evidence.models import (
    CustodyAction,
    EvidenceEngineConfig,
    EvidenceRecord,
    ForensicPackageManifest,
    InvestigationTimeline,
)
from civis.event_intelligence.models import EventIntelligenceResult
from civis.identity.models import IdentityResult
from civis.reid.models import CrossCameraReIDResult
from civis.risk.models import RiskAssessmentResult
from civis.tracking.models import TrackResult


class BaseEvidenceEngine(ABC):
    """
    Abstract Base Class for CIVIS Forensic Evidence & Audit Subsystem.
    Consumes outputs from all upstream modules to record tamper-evident hash-chained logs,
    manage chain-of-custody, synthesize timelines, and export forensic packages.
    """

    def __init__(self, config: EvidenceEngineConfig) -> None:
        self._config = config

    @property
    def config(self) -> EvidenceEngineConfig:
        return self._config

    @abstractmethod
    def ingest_pipeline_frame(
        self,
        detection_result: Optional[DetectionResult] = None,
        track_result: Optional[TrackResult] = None,
        identity_result: Optional[IdentityResult] = None,
        reid_result: Optional[CrossCameraReIDResult] = None,
        behavior_result: Optional[BehaviorResult] = None,
        event_result: Optional[EventIntelligenceResult] = None,
        risk_result: Optional[RiskAssessmentResult] = None,
    ) -> List[EvidenceRecord]:
        """Ingest frame outputs from any or all upstream pipeline stages into the evidence ledger."""
        pass

    @abstractmethod
    def record_custody_action(
        self,
        evidence_id: str,
        action: CustodyAction,
        actor: str,
        notes: str = "",
    ) -> bool:
        """Record an immutable chain-of-custody action for a specific evidence item."""
        pass

    @abstractmethod
    def build_timeline(
        self,
        camera_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        min_severity: Optional[str] = None,
    ) -> InvestigationTimeline:
        """Query and reconstruct a chronological forensic investigation timeline."""
        pass

    @abstractmethod
    def export_forensic_package(
        self,
        timeline: InvestigationTimeline,
        export_directory: str,
    ) -> ForensicPackageManifest:
        """Export an RFC 8493 BagIt-style forensic bundle with SHA-256 integrity checksums."""
        pass

    @abstractmethod
    def verify_ledger_integrity(self) -> Tuple[bool, Optional[str]]:
        """Cryptographically verify the hash-chain integrity of the entire evidence ledger."""
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset ledger memory and active state."""
        pass
