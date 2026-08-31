import math
import time
from typing import Any, List, Optional
from civis.risk.calculator import RiskCalculator
from civis.risk.models import (
    RiskAssessment,
    RiskContribution,
    RiskRule,
    RiskSeverity,
    RiskState,
    ThreatCategory,
)


class TemporalRiskManager:
    """
    Manages temporal dynamics of RiskAssessments:
    - Linear/capped escalation during sustained threats
    - Exponential half-life decay when threat conditions subside
    - State transitions (NEW -> ACTIVE -> ESCALATED -> DE_ESCALATING -> RESOLVED)
    - Severity calculation with anti-fluttering hysteresis
    """

    @classmethod
    def update_assessment(
        cls,
        existing: Optional[RiskAssessment],
        entity_key: str,
        camera_id: str,
        track_id: int,
        identity_id: str,
        contributions: List[RiskContribution],
        active_rules: List[RiskRule],
        current_time: float,
        hysteresis: float = 3.0,
        resolution_timeout_seconds: float = 10.0,
    ) -> RiskAssessment:
        """
        Updates or creates a RiskAssessment incorporating instantaneous scores,
        temporal escalation, decay, and state transitions.
        """
        instantaneous_score, instant_conf = RiskCalculator.calculate_compounded_risk(contributions)

        # Primary threat category from highest scoring contribution or default
        category = ThreatCategory.GENERAL_SUSPICIOUS
        if active_rules:
            category = active_rules[0].category

        # Determine escalation rate & decay half-life from active rules
        escalation_rate = max((r.escalation_rate_per_sec for r in active_rules), default=2.0)
        max_escalated_score = max((r.max_escalated_score for r in active_rules), default=100.0)
        half_life = min((r.de_escalation_half_life_sec for r in active_rules), default=8.0)

        if existing is None:
            # 1. New Risk Assessment
            severity = RiskSeverity.from_score(instantaneous_score, current_severity=None, hysteresis=hysteresis)
            assessment = RiskAssessment(
                assessment_id=f"risk_{camera_id}_{track_id}_{int(current_time)}",
                entity_key=entity_key,
                camera_id=camera_id,
                track_id=track_id,
                identity_id=identity_id,
                state=RiskState.NEW if instantaneous_score > 0 else RiskState.RESOLVED,
                category=category,
                severity=severity,
                severity_score=instantaneous_score,
                confidence=instant_conf,
                start_timestamp=current_time,
                last_updated_timestamp=current_time,
                peak_severity_score=instantaneous_score,
                contributions=contributions,
                evidence_chain=cls._aggregate_evidence(contributions),
            )
            return assessment

        # 2. Existing Assessment Updating
        dt = max(0.0, current_time - existing.last_updated_timestamp)
        prev_score = existing.severity_score
        prev_severity = existing.severity

        if contributions:
            # Threat is actively occurring / reinforced
            # Apply temporal escalation
            escalated_score = min(max_escalated_score, prev_score + escalation_rate * dt)
            new_score = max(instantaneous_score, escalated_score)
            new_score = max(0.0, min(100.0, new_score))

            if new_score > prev_score + 1.0:
                new_state = RiskState.ESCALATED
            else:
                new_state = RiskState.ACTIVE

            new_confidence = max(existing.confidence, instant_conf)
            new_peak = max(existing.peak_severity_score, new_score)

            new_severity = RiskSeverity.from_score(new_score, current_severity=prev_severity, hysteresis=hysteresis)

            existing.category = category
            existing.severity_score = round(new_score, 2)
            existing.confidence = round(new_confidence, 4)
            existing.severity = new_severity
            existing.state = new_state
            existing.peak_severity_score = round(new_peak, 2)
            existing.last_updated_timestamp = current_time
            existing.contributions = contributions
            existing.evidence_chain = cls._aggregate_evidence(contributions)
            existing.identity_id = identity_id or existing.identity_id

        else:
            # Threat subsided -> Exponential Decay
            decay_lambda = math.log(2.0) / max(0.5, half_life)
            decayed_score = prev_score * math.exp(-decay_lambda * dt)
            decayed_score = max(0.0, min(100.0, decayed_score))

            if decayed_score < 5.0 or dt >= resolution_timeout_seconds:
                new_state = RiskState.RESOLVED
                decayed_score = 0.0
            else:
                new_state = RiskState.DE_ESCALATING

            new_severity = RiskSeverity.from_score(decayed_score, current_severity=prev_severity, hysteresis=hysteresis)

            existing.severity_score = round(decayed_score, 2)
            existing.severity = new_severity
            existing.state = new_state
            existing.last_updated_timestamp = current_time
            existing.contributions = []

        return existing

    @staticmethod
    def _aggregate_evidence(contributions: List[RiskContribution]) -> List[Any]:
        chain = []
        for c in contributions:
            chain.extend(c.evidence_references)
        return chain
