import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from civis.identity.models import IdentityResult, IdentityState
from civis.risk.models import (
    RiskAssessment,
    RiskSeverity,
    RiskState,
)

logger = logging.getLogger(__name__)


class AssessmentMemory:
    """
    Manages state persistence, entity resolution, identity rebinding,
    temporal lifecycle history, and alert throttling metadata.
    """

    def __init__(self, resolution_timeout_seconds: float = 10.0) -> None:
        self.resolution_timeout_seconds = resolution_timeout_seconds
        # Active assessments keyed by entity_key
        self._assessments: Dict[str, RiskAssessment] = {}
        # Track-to-Entity mapping: (camera_id, track_id) -> entity_key
        self._track_to_entity: Dict[Tuple[str, int], str] = {}
        # Alert throttling records: entity_key -> { 'timestamp': float, 'severity': RiskSeverity, 'score': float }
        self._alert_history: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def resolve_entity_key(
        camera_id: str,
        track_id: int,
        identity_id: Optional[str] = None,
        identity_state: Optional[IdentityState] = None,
    ) -> str:
        """
        Explicit Entity Resolution:
        - If identity is verified and known: "ident_{identity_id}"
        - Otherwise fallback to camera and track bound: "cam_{camera_id}_trk_{track_id}"
        """
        if identity_id and identity_id not in ("UNKNOWN", "", "None"):
            if identity_state is None or identity_state == IdentityState.KNOWN:
                return f"ident_{identity_id}"
        return f"cam_{camera_id}_trk_{track_id}"

    def update_track_entity_binding(
        self,
        camera_id: str,
        track_id: int,
        identity_id: Optional[str] = None,
        identity_state: Optional[IdentityState] = None,
    ) -> str:
        """
        Resolves entity key and rebinds existing track assessments if identity becomes verified.
        """
        track_key = (camera_id, track_id)
        new_entity_key = self.resolve_entity_key(camera_id, track_id, identity_id, identity_state)
        old_entity_key = self._track_to_entity.get(track_key)

        if old_entity_key and old_entity_key != new_entity_key:
            # Identity rebinding: rebind existing assessment from track to verified identity
            if old_entity_key in self._assessments:
                old_assessment = self._assessments.pop(old_entity_key)
                old_assessment.entity_key = new_entity_key
                old_assessment.identity_id = identity_id or old_assessment.identity_id
                
                # If an assessment for this identity already exists, merge peak scores & history
                if new_entity_key in self._assessments:
                    existing = self._assessments[new_entity_key]
                    existing.severity_score = max(existing.severity_score, old_assessment.severity_score)
                    existing.peak_severity_score = max(existing.peak_severity_score, old_assessment.peak_severity_score)
                    existing.confidence = max(existing.confidence, old_assessment.confidence)
                    existing.evidence_chain.extend(old_assessment.evidence_chain)
                else:
                    self._assessments[new_entity_key] = old_assessment

            # Also transfer alert history if needed
            if old_entity_key in self._alert_history and new_entity_key not in self._alert_history:
                self._alert_history[new_entity_key] = self._alert_history.pop(old_entity_key)

        self._track_to_entity[track_key] = new_entity_key
        return new_entity_key

    def get_assessment(self, entity_key: str) -> Optional[RiskAssessment]:
        return self._assessments.get(entity_key)

    def set_assessment(self, entity_key: str, assessment: RiskAssessment) -> None:
        self._assessments[entity_key] = assessment

    def remove_assessment(self, entity_key: str) -> Optional[RiskAssessment]:
        return self._assessments.pop(entity_key, None)

    def get_all_assessments(self, camera_id: Optional[str] = None, active_only: bool = True) -> List[RiskAssessment]:
        assessments = list(self._assessments.values())
        if active_only:
            assessments = [a for a in assessments if a.is_active and a.state != RiskState.RESOLVED]
        if camera_id is not None:
            assessments = [a for a in assessments if a.camera_id == camera_id]
        return assessments

    def record_alert(
        self,
        entity_key: str,
        timestamp: float,
        severity: RiskSeverity,
        score: float,
    ) -> None:
        self._alert_history[entity_key] = {
            "timestamp": timestamp,
            "severity": severity,
            "score": score,
        }

    def get_last_alert(self, entity_key: str) -> Optional[Dict[str, Any]]:
        return self._alert_history.get(entity_key)

    def expire_inactive(self, current_time: float) -> List[RiskAssessment]:
        """
        Transitions assessments inactive beyond resolution_timeout_seconds or in RESOLVED state.
        """
        resolved: List[RiskAssessment] = []
        to_remove = []

        for entity_key, assessment in self._assessments.items():
            if assessment.state == RiskState.RESOLVED or (
                current_time - assessment.last_updated_timestamp > self.resolution_timeout_seconds
            ):
                assessment.state = RiskState.RESOLVED
                resolved.append(assessment)
                to_remove.append(entity_key)

        for k in to_remove:
            del self._assessments[k]

        return resolved

    def reset(self, camera_id: Optional[str] = None) -> None:
        if camera_id is None:
            self._assessments.clear()
            self._track_to_entity.clear()
            self._alert_history.clear()
        else:
            to_del_entities = {
                ent_k for (cam, _), ent_k in self._track_to_entity.items() if cam == camera_id
            }
            self._track_to_entity = {
                k: v for k, v in self._track_to_entity.items() if k[0] != camera_id
            }
            for ent_k in to_del_entities:
                self._assessments.pop(ent_k, None)
                self._alert_history.pop(ent_k, None)
