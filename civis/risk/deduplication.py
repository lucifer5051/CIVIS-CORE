import uuid
from typing import List, Optional
from civis.risk.memory import AssessmentMemory
from civis.risk.models import (
    RiskAlert,
    RiskAssessment,
    RiskSeverity,
    RiskState,
)


class AlertDeduplicator:
    """
    Prevents alert fatigue and alert storms on continuous high-FPS streams.
    Enforces a strict 4-criteria emission policy:
    1. First appearance of threat on entity.
    2. Discrete severity band escalation (e.g. LOW -> MEDIUM -> HIGH).
    3. Significant score spike (Delta >= threshold).
    4. Periodic cooldown expiration if threat persists.
    """

    SEVERITY_ORDER = {
        RiskSeverity.INFO: 0,
        RiskSeverity.LOW: 1,
        RiskSeverity.MEDIUM: 2,
        RiskSeverity.HIGH: 3,
        RiskSeverity.CRITICAL: 4,
    }

    @classmethod
    def should_emit_alert(
        cls,
        assessment: RiskAssessment,
        memory: AssessmentMemory,
        current_time: float,
        score_delta_threshold: float = 15.0,
        cooldown_seconds: float = 15.0,
        min_severity: RiskSeverity = RiskSeverity.LOW,
    ) -> bool:
        """
        Determines whether a RiskAlert should be emitted for the given RiskAssessment.
        """
        if not assessment.is_active or assessment.state == RiskState.RESOLVED:
            return False

        if cls.SEVERITY_ORDER[assessment.severity] < cls.SEVERITY_ORDER[min_severity]:
            return False

        last_alert = memory.get_last_alert(assessment.entity_key)

        # Criterion 1: First time alert for this entity
        if last_alert is None:
            return True

        last_sev = last_alert["severity"]
        last_score = last_alert["score"]
        last_time = last_alert["timestamp"]

        # Criterion 2: Severity band escalated
        if cls.SEVERITY_ORDER[assessment.severity] > cls.SEVERITY_ORDER[last_sev]:
            return True

        # Criterion 3: Significant score increase delta
        if (assessment.severity_score - last_score) >= score_delta_threshold:
            return True

        # Criterion 4: Cooldown period expired while threat remains active
        if (current_time - last_time) >= cooldown_seconds:
            return True

        # Otherwise suppress duplicate alert
        return False

    @classmethod
    def create_alert(
        cls,
        assessment: RiskAssessment,
        current_time: float,
        memory: AssessmentMemory,
    ) -> RiskAlert:
        """
        Constructs a RiskAlert and updates the throttle history in AssessmentMemory.
        """
        alert_id = f"alt_{assessment.camera_id}_{assessment.track_id}_{uuid.uuid4().hex[:8]}"
        contributing_names = [c.name for c in assessment.contributions]

        headline = f"[{assessment.severity.value.upper()} RISK] {assessment.category.value.replace('_', ' ').title()} on {assessment.camera_id}"

        alert = RiskAlert(
            alert_id=alert_id,
            assessment_id=assessment.assessment_id,
            timestamp=current_time,
            camera_id=assessment.camera_id,
            entity_key=assessment.entity_key,
            severity=assessment.severity,
            severity_score=assessment.severity_score,
            confidence=assessment.confidence,
            headline=headline,
            explanation=assessment.explanation,
            contributing_event_names=contributing_names,
            metadata={"state": assessment.state.value},
        )

        memory.record_alert(
            entity_key=assessment.entity_key,
            timestamp=current_time,
            severity=assessment.severity,
            score=assessment.severity_score,
        )

        return alert
