import unittest

from civis.behavior.models import (
    BehaviorConfig,
    BehaviorEvent,
    BehaviorObservation,
    BehaviorResult,
    BehaviorState,
    Point2D,
    PolygonZone,
)
from civis.event_intelligence.correlation import ConfidenceAggregator
from civis.event_intelligence.engine import MockEventIntelligenceEngine
from civis.event_intelligence.explainability import ExplainabilityEngine
from civis.event_intelligence.factory import create_event_intelligence_engine
from civis.event_intelligence.models import (
    Condition,
    CorrelatedEvent,
    EvidenceItem,
    EventIntelligenceConfig,
    EventRule,
    EventState,
    LogicOperator,
    ConfidenceAggregation,
)
from civis.identity.models import AssociatedIdentity, IdentityResult, IdentityState


def _make_behavior_result(
    cam_id: str,
    frame_num: int,
    timestamp: float,
    observations: list,
    events: list = None,
) -> BehaviorResult:
    return BehaviorResult(
        camera_id=cam_id,
        frame_id=f"{cam_id}_{frame_num}",
        timestamp=timestamp,
        frame_number=frame_num,
        dimensions=(640, 480),
        observations=observations,
        events=events or [],
    )


def _make_obs(
    cam_id: str,
    track_id: int,
    state: BehaviorState,
    dwell_sec: float = 0.0,
    zones: list = None,
    identity_id: str = "UNKNOWN",
) -> BehaviorObservation:
    return BehaviorObservation(
        track_id=track_id,
        camera_id=cam_id,
        identity_id=identity_id,
        state=state,
        speed_px_sec=0.0,
        dwell_time_sec=dwell_sec,
        current_zones=zones or [],
        proximity_track_ids=[],
    )


def _make_identity_result(cam_id: str, frame_num: int, timestamp: float, identities: list) -> IdentityResult:
    return IdentityResult(
        camera_id=cam_id,
        frame_id=f"{cam_id}_{frame_num}",
        timestamp=timestamp,
        frame_number=frame_num,
        dimensions=(640, 480),
        identities=identities,
    )


def _make_assoc_ident(track_id: int, cam_id: str, state: IdentityState) -> AssociatedIdentity:
    return AssociatedIdentity(
        track_id=track_id,
        camera_id=cam_id,
        identity_id="UNKNOWN" if state != IdentityState.KNOWN else "person_42",
        name="Unknown" if state != IdentityState.KNOWN else "John Doe",
        state=state,
        similarity_score=0.4,
        recognition_confidence=0.5,
        association_confidence=0.7,
        observations_count=2,
    )


class TestEventIntelligenceModule(unittest.TestCase):

    def _make_loitering_rule(self) -> EventRule:
        return EventRule(
            rule_id="RULE_LOITERING",
            name="Prolonged Stationary Presence",
            description="Track has been dwelling/loitering for an extended period.",
            logic_operator=LogicOperator.AND,
            conditions=[
                Condition(condition_type="BEHAVIOR_TYPE", target_value="loitering", operator="=="),
                Condition(condition_type="DWELL_TIME", target_value=2.0, operator=">="),
            ],
            temporal_window_seconds=30.0,
            cooldown_seconds=5.0,
            confidence_aggregation=ConfidenceAggregation.AVERAGE,
            min_confidence=0.5,
        )

    def _make_zone_loitering_rule(self) -> EventRule:
        return EventRule(
            rule_id="RULE_ZONE_LOITERING",
            name="Zone Dwell Detected",
            description="Track is loitering inside a configured zone.",
            logic_operator=LogicOperator.AND,
            conditions=[
                Condition(condition_type="BEHAVIOR_TYPE", target_value="loitering", operator="=="),
                Condition(condition_type="ZONE_ID", target_value="ZONE_A", operator="=="),
            ],
            temporal_window_seconds=30.0,
            cooldown_seconds=5.0,
            confidence_aggregation=ConfidenceAggregation.AVERAGE,
            min_confidence=0.5,
        )

    def test_loitering_rule_triggers(self):
        """Loitering rule fires when behavior state is loitering and dwell time exceeds threshold."""
        rule = self._make_loitering_rule()
        config = EventIntelligenceConfig(use_mock=True, rules=[rule], expiry_timeout_seconds=60.0)
        engine = MockEventIntelligenceEngine(config)

        obs = _make_obs("cam_01", 1, BehaviorState.LOITERING, dwell_sec=15.0)
        br = _make_behavior_result("cam_01", 1, timestamp=1.0, observations=[obs])

        result = engine.process(br)
        self.assertGreater(len(result.events), 0)
        active_event = result.events[0]
        self.assertEqual(active_event.rule_id, "RULE_LOITERING")
        self.assertEqual(active_event.state, EventState.ACTIVE)

    def test_zone_loitering_rule_triggers(self):
        """Zone dwell rule fires only when track is loitering inside the configured zone."""
        rule = self._make_zone_loitering_rule()
        config = EventIntelligenceConfig(use_mock=True, rules=[rule], expiry_timeout_seconds=60.0)
        engine = MockEventIntelligenceEngine(config)

        obs = _make_obs("cam_01", 2, BehaviorState.LOITERING, dwell_sec=12.0, zones=["ZONE_A"])
        br = _make_behavior_result("cam_01", 2, timestamp=1.0, observations=[obs])

        result = engine.process(br)
        self.assertGreater(len(result.events), 0)
        self.assertEqual(result.events[0].rule_id, "RULE_ZONE_LOITERING")

    def test_event_cooldown_suppression(self):
        """Event does not re-fire within cooldown window (separate from lifecycle state)."""
        rule = self._make_loitering_rule()
        config = EventIntelligenceConfig(use_mock=True, rules=[rule], expiry_timeout_seconds=60.0)
        engine = MockEventIntelligenceEngine(config)

        obs = _make_obs("cam_01", 1, BehaviorState.LOITERING, dwell_sec=15.0)

        # First frame at t=1.0 — triggers event
        br1 = _make_behavior_result("cam_01", 1, timestamp=1.0, observations=[obs])
        result1 = engine.process(br1)
        self.assertEqual(len(result1.events), 1)

        # Second frame at t=2.0 — inside 5.0s cooldown window, suppressed
        br2 = _make_behavior_result("cam_01", 2, timestamp=2.0, observations=[obs])
        result2 = engine.process(br2)
        self.assertEqual(len(result2.events), 0)

        # Third frame at t=8.0 — outside 5.0s cooldown window, fires again
        br3 = _make_behavior_result("cam_01", 3, timestamp=8.0, observations=[obs])
        result3 = engine.process(br3)
        self.assertEqual(len(result3.events), 1)

    def test_evidence_confidence_individually_visible(self):
        """Evidence items carry individual confidence values; overall_confidence is aggregated separately."""
        rule = self._make_loitering_rule()
        config = EventIntelligenceConfig(use_mock=True, rules=[rule], expiry_timeout_seconds=60.0)
        engine = MockEventIntelligenceEngine(config)

        obs = _make_obs("cam_01", 1, BehaviorState.LOITERING, dwell_sec=15.0)
        br = _make_behavior_result("cam_01", 1, timestamp=1.0, observations=[obs])
        result = engine.process(br)

        self.assertGreater(len(result.events), 0)
        event = result.events[0]
        # Each evidence item must have its own confidence value
        for ev_item in event.evidence_chain:
            self.assertIsInstance(ev_item.confidence, float)
            self.assertGreaterEqual(ev_item.confidence, 0.0)
        # Overall confidence is a separately aggregated value
        self.assertIsInstance(event.overall_confidence, float)

    def test_explainability_explanation_contains_rule_name(self):
        """Explanation string is non-empty and references the rule name."""
        items = [
            EvidenceItem(
                evidence_type="BEHAVIOR_TYPE",
                source_module="behavior",
                timestamp=5.0,
                camera_id="cam_01",
                track_id=1,
                description="Behavior state is 'loitering'",
                confidence=0.9,
            )
        ]
        explanation = ExplainabilityEngine.build_explanation(
            rule_name="My Test Rule",
            camera_id="cam_01",
            primary_track_id=1,
            primary_identity_id="UNKNOWN",
            evidence_chain=items,
            overall_confidence=0.9,
        )
        self.assertIn("My Test Rule", explanation)
        self.assertIn("cam_01", explanation)
        self.assertIn("Behavior state is 'loitering'", explanation)

    def test_confidence_aggregation_modes(self):
        """Confidence aggregation respects selected mode independently."""
        items = [
            EvidenceItem("T", "b", 1.0, "c", confidence=0.6),
            EvidenceItem("T", "b", 2.0, "c", confidence=0.9),
        ]
        avg = ConfidenceAggregator.aggregate(items, ConfidenceAggregation.AVERAGE)
        self.assertAlmostEqual(avg, 0.75, places=2)

        mn = ConfidenceAggregator.aggregate(items, ConfidenceAggregation.MIN)
        self.assertAlmostEqual(mn, 0.6, places=2)

        mx = ConfidenceAggregator.aggregate(items, ConfidenceAggregation.MAX)
        self.assertAlmostEqual(mx, 0.9, places=2)

    def test_factory_returns_mock_engine(self):
        config = EventIntelligenceConfig(use_mock=True)
        engine = create_event_intelligence_engine(config)
        self.assertIsInstance(engine, MockEventIntelligenceEngine)


if __name__ == "__main__":
    unittest.main()
