import logging
import time
from typing import Dict, List, Optional, Set

from civis.behavior.models import BehaviorEvent, BehaviorObservation, BehaviorResult
from civis.event_intelligence.models import CorrelatedEvent, EventIntelligenceResult
from civis.identity.models import AssociatedIdentity, IdentityResult, IdentityState
from civis.risk.base import BaseRiskEngine
from civis.risk.deduplication import AlertDeduplicator
from civis.risk.explainability import RiskExplainabilityEngine
from civis.risk.memory import AssessmentMemory
from civis.risk.models import (
    RiskAlert,
    RiskAssessment,
    RiskAssessmentResult,
    RiskEngineConfig,
    RiskRule,
)
from civis.risk.rules import RuleMatcher
from civis.risk.temporal import TemporalRiskManager
from civis.tracking.models import TrackResult, TrackedObject

logger = logging.getLogger(__name__)


class RiskEngine(BaseRiskEngine):
    """
    Cognitive Risk Assessment Engine for CIVIS-CORE.
    Evaluates multi-signal risk policies over events, behaviors, identities, and tracks.
    Computes compounded severity scores, manages temporal risk lifecycles,
    synthesizes explanations, and enforces alert deduplication.
    """

    def __init__(self, config: Optional[RiskEngineConfig] = None) -> None:
        cfg = config if config is not None else RiskEngineConfig()
        super().__init__(cfg)
        self._memory = AssessmentMemory(resolution_timeout_seconds=self._config.resolution_timeout_seconds)

    def reset(self, camera_id: Optional[str] = None) -> None:
        """Reset memory and active assessments."""
        self._memory.reset(camera_id)

    def assess(
        self,
        event_intelligence_result: EventIntelligenceResult,
        behavior_result: Optional[BehaviorResult] = None,
        identity_result: Optional[IdentityResult] = None,
        track_result: Optional[TrackResult] = None,
    ) -> RiskAssessmentResult:
        start_time = time.perf_counter()
        camera_id = event_intelligence_result.camera_id
        current_time = event_intelligence_result.timestamp

        # 1. Index upstream inputs by track_id
        events_by_track: Dict[int, List[CorrelatedEvent]] = {}
        for evt in event_intelligence_result.events:
            events_by_track.setdefault(evt.primary_track_id, []).append(evt)
            for s_id in evt.secondary_track_ids:
                events_by_track.setdefault(s_id, []).append(evt)

        beh_events_by_track: Dict[int, List[BehaviorEvent]] = {}
        beh_obs_by_track: Dict[int, BehaviorObservation] = {}
        if behavior_result is not None:
            for b_ev in behavior_result.events:
                beh_events_by_track.setdefault(b_ev.primary_track_id, []).append(b_ev)
            for obs in behavior_result.observations:
                beh_obs_by_track[obs.track_id] = obs

        ident_by_track: Dict[int, AssociatedIdentity] = {}
        if identity_result is not None:
            for ident in identity_result.identities:
                ident_by_track[ident.track_id] = ident

        tracks_by_id: Dict[int, TrackedObject] = {}
        if track_result is not None:
            for trk in track_result.tracks:
                tracks_by_id[trk.track_id] = trk

        # 2. Gather all active track IDs across all inputs
        active_track_ids: Set[int] = set()
        active_track_ids.update(events_by_track.keys())
        active_track_ids.update(beh_events_by_track.keys())
        active_track_ids.update(beh_obs_by_track.keys())
        active_track_ids.update(ident_by_track.keys())
        active_track_ids.update(tracks_by_id.keys())

        # 3. Process each entity
        current_alerts: List[RiskAlert] = []

        for track_id in active_track_ids:
            ident = ident_by_track.get(track_id)
            ident_id = ident.identity_id if ident else "UNKNOWN"
            ident_state = ident.state if ident else None

            # Explicit entity resolution & rebinding
            entity_key = self._memory.update_track_entity_binding(
                camera_id=camera_id,
                track_id=track_id,
                identity_id=ident_id,
                identity_state=ident_state,
            )

            c_events = events_by_track.get(track_id, [])
            b_events = beh_events_by_track.get(track_id, [])
            b_obs = beh_obs_by_track.get(track_id)
            trk = tracks_by_id.get(track_id)

            # Evaluate rules
            contributions = RuleMatcher.evaluate_rules(
                rules=self._config.rules,
                correlated_events=c_events,
                behavior_events=b_events,
                behavior_obs=b_obs,
                identity=ident,
                track=trk,
            )

            existing_assessment = self._memory.get_assessment(entity_key)

            # If there are active contributions or an existing ongoing assessment to decay
            if contributions or existing_assessment is not None:
                # Find matching active rules for temporal parameters
                active_rule_ids = {c.source_id for c in contributions}
                active_rules = [r for r in self._config.rules if r.rule_id in active_rule_ids]
                if not active_rules and self._config.rules:
                    active_rules = self._config.rules

                assessment = TemporalRiskManager.update_assessment(
                    existing=existing_assessment,
                    entity_key=entity_key,
                    camera_id=camera_id,
                    track_id=track_id,
                    identity_id=ident_id,
                    contributions=contributions,
                    active_rules=active_rules,
                    current_time=current_time,
                    hysteresis=self._config.hysteresis,
                    resolution_timeout_seconds=self._config.resolution_timeout_seconds,
                )

                # Generate explainable narrative
                assessment.explanation = RiskExplainabilityEngine.generate_explanation(assessment)
                self._memory.set_assessment(entity_key, assessment)

                # Evaluate alert deduplication & throttling
                if AlertDeduplicator.should_emit_alert(
                    assessment=assessment,
                    memory=self._memory,
                    current_time=current_time,
                    score_delta_threshold=self._config.alert_score_delta_threshold,
                    cooldown_seconds=self._config.alert_cooldown_seconds,
                    min_severity=self._config.min_alert_severity,
                ):
                    alert = AlertDeduplicator.create_alert(
                        assessment=assessment,
                        current_time=current_time,
                        memory=self._memory,
                    )
                    current_alerts.append(alert)

        # 4. Handle expired inactive assessments
        self._memory.expire_inactive(current_time)

        # 5. Collect all active assessments for this camera
        camera_assessments = self._memory.get_all_assessments(camera_id)

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        return RiskAssessmentResult(
            camera_id=camera_id,
            frame_id=event_intelligence_result.frame_id,
            timestamp=current_time,
            frame_number=event_intelligence_result.frame_number,
            dimensions=event_intelligence_result.dimensions,
            assessments=camera_assessments,
            alerts=current_alerts,
            processing_time_ms=elapsed_ms,
            metadata={"engine": "RiskEngine"},
        )


class MockRiskEngine(RiskEngine):
    """
    Mock Risk Engine for unit testing and deterministic simulation.
    """

    def __init__(self, config: Optional[RiskEngineConfig] = None) -> None:
        cfg = config if config is not None else RiskEngineConfig(use_mock=True)
        super().__init__(cfg)
