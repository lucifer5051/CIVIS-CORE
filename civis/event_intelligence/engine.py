import logging
import time
from typing import Dict, List, Optional

from civis.behavior.models import BehaviorResult
from civis.event_intelligence.base import BaseEventIntelligenceEngine
from civis.event_intelligence.correlation import (
    ConfidenceAggregator,
    TrackTemporalObservationBuffer,
)
from civis.event_intelligence.explainability import ExplainabilityEngine
from civis.event_intelligence.models import (
    CorrelatedEvent,
    EventIntelligenceConfig,
    EventIntelligenceResult,
    EventRule,
    EventState,
)
from civis.event_intelligence.rules import RuleEvaluator
from civis.identity.models import IdentityResult
from civis.tracking.models import TrackResult

logger = logging.getLogger(__name__)


class EventIntelligenceEngine(BaseEventIntelligenceEngine):
    """
    Event Intelligence Engine for CIVIS.
    Evaluates data-driven rules over temporal observation buffers and emits correlated events
    with complete evidence chains, individual evidence confidences, and explainable summaries.
    """

    def __init__(self, config: Optional[EventIntelligenceConfig] = None) -> None:
        cfg = config if config is not None else EventIntelligenceConfig()
        super().__init__(cfg)
        self._buffers: Dict[tuple[str, int], TrackTemporalObservationBuffer] = {}
        self._active_events: Dict[str, CorrelatedEvent] = {}  # event_key -> CorrelatedEvent
        self._cooldowns: Dict[str, float] = {}  # rule_cam_track_key -> last_event_time

    def reset(self, camera_id: Optional[str] = None) -> None:
        if camera_id is None:
            self._buffers.clear()
            self._active_events.clear()
            self._cooldowns.clear()
        else:
            to_del_b = [k for k in self._buffers.keys() if k[0] == camera_id]
            for k in to_del_b:
                del self._buffers[k]
            to_del_e = [k for k, v in self._active_events.items() if v.camera_id == camera_id]
            for k in to_del_e:
                del self._active_events[k]

    def process(
        self,
        behavior_result: BehaviorResult,
        identity_result: Optional[IdentityResult] = None,
        track_result: Optional[TrackResult] = None,
    ) -> EventIntelligenceResult:
        start_time = time.perf_counter()
        cam_id = behavior_result.camera_id
        current_time = behavior_result.timestamp

        # 1. Update temporal observation buffers
        for obs in behavior_result.observations:
            buf_key = (cam_id, obs.track_id)
            if buf_key not in self._buffers:
                self._buffers[buf_key] = TrackTemporalObservationBuffer(
                    cam_id, obs.track_id, window_seconds=self._config.temporal_window_seconds
                )
            buf = self._buffers[buf_key]
            buf.add_behavior_obs(current_time, obs)

        for evt in behavior_result.events:
            buf_key = (cam_id, evt.primary_track_id)
            if buf_key in self._buffers:
                self._buffers[buf_key].add_behavior_event(current_time, evt)

        if identity_result is not None:
            for ident in identity_result.identities:
                buf_key = (cam_id, ident.track_id)
                if buf_key in self._buffers:
                    self._buffers[buf_key].add_identity(current_time, ident)

        # 2. Evaluate data-driven rules for active tracks
        current_events: List[CorrelatedEvent] = []
        event_seq = 0

        for buf_key, buffer in self._buffers.items():
            track_cam_id, track_id = buf_key

            for rule in self._config.rules:
                rule_key = f"{rule.rule_id}_{track_cam_id}_{track_id}"
                
                # Check cooldown deduplication (separate from lifecycle state)
                last_time = self._cooldowns.get(rule_key, float("-inf"))
                if current_time - last_time < rule.cooldown_seconds:
                    continue

                is_triggered, evidence_chain = RuleEvaluator.evaluate_rule(rule, buffer, current_time)

                if is_triggered:
                    self._cooldowns[rule_key] = current_time
                    event_seq += 1

                    overall_conf = ConfidenceAggregator.aggregate(
                        evidence_chain=evidence_chain,
                        mode=rule.confidence_aggregation,
                    )

                    if overall_conf < rule.min_confidence:
                        continue

                    # Extract primary identity
                    primary_ident = "UNKNOWN"
                    for ev in evidence_chain:
                        if ev.identity_id:
                            primary_ident = ev.identity_id
                            break

                    explanation = ExplainabilityEngine.build_explanation(
                        rule_name=rule.name,
                        camera_id=track_cam_id,
                        primary_track_id=track_id,
                        primary_identity_id=primary_ident,
                        evidence_chain=evidence_chain,
                        overall_confidence=overall_conf,
                    )

                    event_id = f"cevt_{track_cam_id}_{track_id}_{event_seq}_{int(current_time)}"

                    event = CorrelatedEvent(
                        event_id=event_id,
                        rule_id=rule.rule_id,
                        name=rule.name,
                        state=EventState.ACTIVE,
                        camera_id=track_cam_id,
                        primary_track_id=track_id,
                        primary_identity_id=primary_ident,
                        start_timestamp=current_time,
                        last_updated_timestamp=current_time,
                        overall_confidence=overall_conf,
                        evidence_chain=evidence_chain,
                        explanation=explanation,
                    )

                    self._active_events[rule_key] = event
                    current_events.append(event)

        # 3. Lifecycle Maintenance (ACTIVE -> RESOLVED / EXPIRED)
        to_expire = []
        for rule_key, event in self._active_events.items():
            if current_time - event.last_updated_timestamp > self._config.expiry_timeout_seconds:
                event.state = EventState.EXPIRED
                to_expire.append(rule_key)

        for k in to_expire:
            del self._active_events[k]

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        return EventIntelligenceResult(
            camera_id=cam_id,
            frame_id=behavior_result.frame_id,
            timestamp=current_time,
            frame_number=behavior_result.frame_number,
            dimensions=behavior_result.dimensions,
            events=current_events,
            processing_time_ms=elapsed_ms,
            metadata={"engine": "EventIntelligenceEngine"},
        )


class MockEventIntelligenceEngine(EventIntelligenceEngine):
    """
    Mock Event Intelligence Engine for unit testing.
    """

    def __init__(self, config: Optional[EventIntelligenceConfig] = None) -> None:
        cfg = config if config is not None else EventIntelligenceConfig(use_mock=True)
        super().__init__(cfg)
