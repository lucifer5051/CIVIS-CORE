import logging
import os
import time
from typing import Dict, List, Optional, Tuple

from civis.behavior.models import BehaviorResult
from civis.detection.models import DetectionResult
from civis.evidence.base import BaseEvidenceEngine
from civis.evidence.custody import ChainOfCustodyManager
from civis.evidence.ledger import EvidenceLedger
from civis.evidence.models import (
    CustodyAction,
    EvidenceEngineConfig,
    EvidenceRecord,
    EvidenceStage,
    ForensicPackageManifest,
    InvestigationTimeline,
)
from civis.evidence.packager import ForensicPackager
from civis.evidence.retention import RetentionManager
from civis.evidence.timeline import TimelineBuilder
from civis.event_intelligence.models import EventIntelligenceResult
from civis.identity.models import IdentityResult
from civis.reid.models import CrossCameraReIDResult
from civis.risk.models import RiskAssessmentResult
from civis.tracking.models import TrackResult

logger = logging.getLogger(__name__)


class EvidenceEngine(BaseEvidenceEngine):
    """
    Forensic Evidence & Audit Subsystem for CIVIS.
    Maintains an immutable, cryptographically hash-chained ledger connecting:
    Detection -> Track -> Identity -> Re-ID -> Behavior -> Event -> Risk.
    """

    def __init__(self, config: Optional[EvidenceEngineConfig] = None) -> None:
        cfg = config if config is not None else EvidenceEngineConfig()
        super().__init__(cfg)
        self._ledger = EvidenceLedger(
            enable_hash_chain=cfg.enable_hash_chain,
            max_records=cfg.max_ledger_records,
        )
        self._retention = RetentionManager(cfg.retention_policy)

    def reset(self) -> None:
        self._ledger.reset()

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
        new_records: List[EvidenceRecord] = []
        track_ev_map: Dict[int, str] = {}
        event_ev_map: Dict[str, str] = {}

        # 1. Ingest Detections
        if detection_result is not None:
            cam = detection_result.camera_id
            for d_idx, det in enumerate(detection_result.detections):
                ev_id = f"ev_det_{cam}_{detection_result.frame_number}_{d_idx}"
                rec = self._ledger.append(
                    evidence_id=ev_id,
                    stage=EvidenceStage.DETECTION,
                    camera_id=cam,
                    frame_id=detection_result.frame_id,
                    frame_number=detection_result.frame_number,
                    timestamp=detection_result.timestamp,
                    payload={
                        "class_id": det.class_id,
                        "class_name": det.class_name,
                        "confidence": round(det.confidence, 4),
                        "bbox": det.bbox.to_dict(),
                    },
                )
                new_records.append(rec)

        # 2. Ingest Tracks
        if track_result is not None:
            cam = track_result.camera_id
            for trk in track_result.tracks:
                ev_id = f"ev_trk_{cam}_{track_result.frame_number}_{trk.track_id}"
                rec = self._ledger.append(
                    evidence_id=ev_id,
                    stage=EvidenceStage.TRACKING,
                    camera_id=cam,
                    frame_id=track_result.frame_id,
                    frame_number=track_result.frame_number,
                    timestamp=track_result.timestamp,
                    track_id=trk.track_id,
                    payload={
                        "class_id": trk.class_id,
                        "class_name": trk.class_name,
                        "confidence": round(trk.confidence, 4),
                        "state": trk.state.value,
                        "bbox": trk.bbox.to_dict(),
                    },
                )
                track_ev_map[trk.track_id] = ev_id
                new_records.append(rec)

        # 3. Ingest Identity
        if identity_result is not None:
            cam = identity_result.camera_id
            for ident in identity_result.identities:
                ev_id = f"ev_idt_{cam}_{identity_result.frame_number}_{ident.track_id}"
                parent = [track_ev_map[ident.track_id]] if ident.track_id in track_ev_map else []
                rec = self._ledger.append(
                    evidence_id=ev_id,
                    stage=EvidenceStage.IDENTITY,
                    camera_id=cam,
                    frame_id=identity_result.frame_id,
                    frame_number=identity_result.frame_number,
                    timestamp=identity_result.timestamp,
                    track_id=ident.track_id,
                    identity_id=ident.identity_id,
                    parent_evidence_ids=parent,
                    payload={
                        "identity_id": ident.identity_id,
                        "name": ident.name,
                        "state": ident.state.value,
                        "similarity_score": round(ident.similarity_score, 4),
                    },
                )
                new_records.append(rec)

        # 4. Ingest Cross-Camera Re-ID
        if reid_result is not None:
            for match in reid_result.active_matches:
                ev_id = f"ev_reid_{match.query_camera_id}_{match.query_track_id}_{match.matched_camera_id}_{match.matched_track_id}"
                rec = self._ledger.append(
                    evidence_id=ev_id,
                    stage=EvidenceStage.REID,
                    camera_id=match.query_camera_id,
                    frame_id=f"{match.query_camera_id}_match",
                    frame_number=0,
                    timestamp=reid_result.timestamp,
                    track_id=match.query_track_id,
                    global_entity_id=match.global_entity_id,
                    payload={
                        "matched_camera_id": match.matched_camera_id,
                        "matched_track_id": match.matched_track_id,
                        "similarity_score": match.similarity_score,
                        "time_delta_seconds": match.time_delta_seconds,
                    },
                )
                new_records.append(rec)

        # 5. Ingest Behavior
        if behavior_result is not None:
            cam = behavior_result.camera_id
            for b_ev in behavior_result.events:
                ev_id = f"ev_beh_{b_ev.event_id}"
                parent = [track_ev_map[b_ev.primary_track_id]] if b_ev.primary_track_id in track_ev_map else []
                rec = self._ledger.append(
                    evidence_id=ev_id,
                    stage=EvidenceStage.BEHAVIOR,
                    camera_id=cam,
                    frame_id=behavior_result.frame_id,
                    frame_number=behavior_result.frame_number,
                    timestamp=behavior_result.timestamp,
                    track_id=b_ev.primary_track_id,
                    identity_id=b_ev.identity_id,
                    parent_evidence_ids=parent,
                    payload={
                        "event_type": b_ev.event_type,
                        "zone_id": b_ev.zone_id,
                        "secondary_tracks": b_ev.secondary_track_ids,
                    },
                )
                new_records.append(rec)

        # 6. Ingest Event Intelligence
        if event_result is not None:
            cam = event_result.camera_id
            for c_evt in event_result.events:
                ev_id = f"ev_evt_{c_evt.event_id}"
                rec = self._ledger.append(
                    evidence_id=ev_id,
                    stage=EvidenceStage.EVENT_INTELLIGENCE,
                    camera_id=cam,
                    frame_id=event_result.frame_id,
                    frame_number=event_result.frame_number,
                    timestamp=event_result.timestamp,
                    track_id=c_evt.primary_track_id,
                    identity_id=c_evt.primary_identity_id,
                    payload={
                        "rule_id": c_evt.rule_id,
                        "name": c_evt.name,
                        "confidence": round(c_evt.overall_confidence, 4),
                        "explanation": c_evt.explanation,
                    },
                )
                event_ev_map[c_evt.rule_id] = ev_id
                new_records.append(rec)

        # 7. Ingest Risk Assessments & Alerts
        if risk_result is not None:
            cam = risk_result.camera_id
            for ass in risk_result.assessments:
                ev_id = f"ev_rsk_{ass.assessment_id}"
                rec = self._ledger.append(
                    evidence_id=ev_id,
                    stage=EvidenceStage.RISK_ASSESSMENT,
                    camera_id=cam,
                    frame_id=risk_result.frame_id,
                    frame_number=risk_result.frame_number,
                    timestamp=risk_result.timestamp,
                    track_id=ass.track_id,
                    identity_id=ass.identity_id,
                    risk_score=ass.severity_score,
                    severity=ass.severity.value,
                    payload={
                        "category": ass.category.value,
                        "severity": ass.severity.value,
                        "severity_score": ass.severity_score,
                        "confidence": ass.confidence,
                        "explanation": ass.explanation,
                        "contributions": [c.name for c in ass.contributions],
                    },
                )
                new_records.append(rec)

            for alt in risk_result.alerts:
                ev_id = f"ev_alt_{alt.alert_id}"
                rec = self._ledger.append(
                    evidence_id=ev_id,
                    stage=EvidenceStage.RISK_ASSESSMENT,
                    camera_id=cam,
                    frame_id=risk_result.frame_id,
                    frame_number=risk_result.frame_number,
                    timestamp=risk_result.timestamp,
                    risk_score=alt.severity_score,
                    severity=alt.severity.value,
                    payload={
                        "headline": alt.headline,
                        "explanation": alt.explanation,
                        "contributing_events": alt.contributing_event_names,
                    },
                )
                if self._config.auto_seal_alerts:
                    ChainOfCustodyManager.record_action(
                        record=rec,
                        action=CustodyAction.SEALED,
                        actor="CIVIS_AUTO_SEAL",
                        notes="Auto-sealed upon actionable security risk alert dispatch",
                    )
                new_records.append(rec)

        return new_records

    def record_custody_action(
        self,
        evidence_id: str,
        action: CustodyAction,
        actor: str,
        notes: str = "",
    ) -> bool:
        rec = self._ledger.get_record_by_id(evidence_id)
        if rec is None:
            return False
        ChainOfCustodyManager.record_action(rec, action, actor, notes)
        return True

    def build_timeline(
        self,
        camera_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        min_severity: Optional[str] = None,
    ) -> InvestigationTimeline:
        records = self._ledger.query(
            camera_id=camera_id,
            entity_id=entity_id,
            start_time=start_time,
            end_time=end_time,
            min_severity=min_severity,
        )
        return TimelineBuilder.build_timeline(records)

    def export_forensic_package(
        self,
        timeline: InvestigationTimeline,
        export_directory: str,
    ) -> ForensicPackageManifest:
        root_hash = self._ledger._last_hash
        return ForensicPackager.export_package(
            timeline=timeline,
            target_directory=export_directory,
            root_ledger_hash=root_hash,
        )

    def verify_ledger_integrity(self) -> Tuple[bool, Optional[str]]:
        return self._ledger.verify_integrity()


class MockEvidenceEngine(EvidenceEngine):
    """
    Mock Evidence Engine for testing.
    """

    def __init__(self, config: Optional[EvidenceEngineConfig] = None) -> None:
        cfg = config if config is not None else EvidenceEngineConfig(use_mock=True)
        super().__init__(cfg)
