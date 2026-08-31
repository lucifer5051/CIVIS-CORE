import unittest
from civis.behavior.models import (
    BehaviorEvent,
    BehaviorObservation,
    BehaviorResult,
    BehaviorState,
)
from civis.detection.models import BoundingBox
from civis.event_intelligence.models import (
    CorrelatedEvent,
    EvidenceItem,
    EventIntelligenceResult,
    EventState,
)
from civis.identity.models import AssociatedIdentity, IdentityResult, IdentityState
from civis.risk import (
    ContextMultiplier,
    RiskAssessment,
    RiskContribution,
    RiskEngineConfig,
    RiskRule,
    RiskSeverity,
    RiskState,
    ThreatCategory,
    create_risk_engine,
)
from civis.risk.calculator import RiskCalculator
from civis.risk.memory import AssessmentMemory
from civis.tracking.models import TrackResult, TrackState, TrackedObject


def _make_track_result(cam_id: str, frame_num: int, ts: float, track_ids: list) -> TrackResult:
    tracks = [
        TrackedObject(
            track_id=t_id,
            class_id=0,
            class_name="person",
            confidence=0.9,
            bbox=BoundingBox(100, 100, 200, 200),
            state=TrackState.TRACKED,
        )
        for t_id in track_ids
    ]
    return TrackResult(
        camera_id=cam_id,
        frame_id=f"{cam_id}_{frame_num}",
        timestamp=ts,
        frame_number=frame_num,
        dimensions=(640, 480),
        tracks=tracks,
        active_track_ids=track_ids,
    )


def _make_identity_result(cam_id: str, frame_num: int, ts: float, identities: list) -> IdentityResult:
    return IdentityResult(
        camera_id=cam_id,
        frame_id=f"{cam_id}_{frame_num}",
        timestamp=ts,
        frame_number=frame_num,
        dimensions=(640, 480),
        identities=identities,
    )


def _make_behavior_result(
    cam_id: str, frame_num: int, ts: float, observations: list, events: list = None
) -> BehaviorResult:
    return BehaviorResult(
        camera_id=cam_id,
        frame_id=f"{cam_id}_{frame_num}",
        timestamp=ts,
        frame_number=frame_num,
        dimensions=(640, 480),
        observations=observations,
        events=events or [],
    )


def _make_event_intelligence_result(
    cam_id: str, frame_num: int, ts: float, events: list
) -> EventIntelligenceResult:
    return EventIntelligenceResult(
        camera_id=cam_id,
        frame_id=f"{cam_id}_{frame_num}",
        timestamp=ts,
        frame_number=frame_num,
        dimensions=(640, 480),
        events=events,
    )


class TestRiskAssessmentEngine(unittest.TestCase):

    def setUp(self):
        self.rule_loiter_risk = RiskRule(
            rule_id="RULE_LOITER_RISK",
            name="Restricted Zone Loitering Threat",
            category=ThreatCategory.LOITERING_PROWLING,
            priority=10,
            base_severity_score=45.0,
            required_events=["RULE_LOITERING"],
            context_multipliers=[
                ContextMultiplier(
                    condition_type="ZONE_RESTRICTED",
                    target_value="RESTRICTED_VAULT",
                    multiplier=1.4,
                    description="Subject is inside secure vault zone",
                ),
                ContextMultiplier(
                    condition_type="UNKNOWN_IDENTITY",
                    target_value=True,
                    multiplier=1.2,
                    description="Subject has unrecognized biometric identity",
                ),
            ],
            escalation_rate_per_sec=2.0,
            max_escalated_score=95.0,
            de_escalation_half_life_sec=4.0,
            cooldown_seconds=5.0,
            min_confidence=0.4,
            weight=1.0,
        )

        self.rule_tripwire_breach = RiskRule(
            rule_id="RULE_TRIPWIRE_BREACH",
            name="Perimeter Breach Threat",
            category=ThreatCategory.SECURITY_INTRUSION,
            priority=20,
            base_severity_score=60.0,
            required_behaviors=["crossing_zone", "tripwire_cross"],
            escalation_rate_per_sec=3.0,
            cooldown_seconds=5.0,
            min_confidence=0.4,
            weight=1.0,
        )

    def test_rule_matching_and_context_multipliers(self):
        """Test rule triggering and compounding multipliers."""
        config = RiskEngineConfig(rules=[self.rule_loiter_risk], use_mock=True)
        engine = create_risk_engine(config)

        ev_item = EvidenceItem(
            evidence_type="BEHAVIOR_OBSERVATION",
            source_module="civis.behavior",
            timestamp=100.0,
            camera_id="CAM_01",
            track_id=1,
            description="Loitering detected in vault",
        )
        c_evt = CorrelatedEvent(
            event_id="cevt_01",
            rule_id="RULE_LOITERING",
            name="Loitering Event",
            state=EventState.ACTIVE,
            camera_id="CAM_01",
            primary_track_id=1,
            start_timestamp=100.0,
            last_updated_timestamp=100.0,
            overall_confidence=0.85,
            evidence_chain=[ev_item],
        )
        ei_res = _make_event_intelligence_result("CAM_01", 1, 100.0, [c_evt])

        obs = BehaviorObservation(
            track_id=1,
            camera_id="CAM_01",
            identity_id="UNKNOWN",
            state=BehaviorState.LOITERING,
            speed_px_sec=1.0,
            dwell_time_sec=15.0,
            current_zones=["RESTRICTED_VAULT"],
            proximity_track_ids=[],
        )
        beh_res = _make_behavior_result("CAM_01", 1, 100.0, [obs])

        ident = AssociatedIdentity(
            track_id=1,
            camera_id="CAM_01",
            identity_id="UNKNOWN",
            name="Unknown",
            state=IdentityState.UNKNOWN,
            similarity_score=0.2,
            recognition_confidence=0.1,
            association_confidence=0.8,
            observations_count=5,
        )
        ident_res = _make_identity_result("CAM_01", 1, 100.0, [ident])
        track_res = _make_track_result("CAM_01", 1, 100.0, [1])

        res = engine.assess(ei_res, beh_res, ident_res, track_res)
        self.assertEqual(len(res.assessments), 1)
        assessment = res.assessments[0]

        # Base score 45.0 * 1.4 (zone) * 1.2 (unknown) = 75.6
        self.assertAlmostEqual(assessment.severity_score, 75.6, places=1)
        self.assertEqual(assessment.severity, RiskSeverity.HIGH)
        self.assertEqual(len(assessment.contributions), 1)
        self.assertEqual(len(assessment.contributions[0].applied_multipliers), 2)
        self.assertIn("RESTRICTED_VAULT", assessment.explanation)
        self.assertIn("HIGH RISK", assessment.explanation)

    def test_multi_signal_score_compounding(self):
        """Test sublinear asymptotic compounding when multiple risks fire simultaneously."""
        contrib1 = RiskContribution(
            source_type="rule_trigger",
            source_id="R1",
            name="Threat 1",
            base_score=60.0,
            confidence=0.8,
            effective_score=60.0,
        )
        contrib2 = RiskContribution(
            source_type="rule_trigger",
            source_id="R2",
            name="Threat 2",
            base_score=40.0,
            confidence=0.7,
            effective_score=40.0,
        )

        score, conf = RiskCalculator.calculate_compounded_risk([contrib1, contrib2])
        # S_comb = 60 + (100 - 60) * (1 - (1 - 0.4)) = 60 + 40 * 0.4 = 76.0
        self.assertEqual(score, 76.0)
        # Conf_comb = 1 - (1 - 0.8)*(1 - 0.7) = 1 - (0.2 * 0.3) = 0.94
        self.assertEqual(conf, 0.94)

    def test_score_and_confidence_bounds(self):
        """Test strict bounding of scores in [0, 100] and confidence in [0, 1]."""
        contribs = [
            RiskContribution("rule", f"R{i}", f"T{i}", 95.0, 0.9, effective_score=95.0)
            for i in range(10)
        ]
        score, conf = RiskCalculator.calculate_compounded_risk(contribs)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 100.0)
        self.assertGreaterEqual(conf, 0.0)
        self.assertLessEqual(conf, 1.0)

    def test_severity_hysteresis(self):
        """Test that de-escalation uses hysteresis band to avoid flapping."""
        # Initial score 72.0 -> HIGH
        sev1 = RiskSeverity.from_score(72.0, None)
        self.assertEqual(sev1, RiskSeverity.HIGH)

        # Fluctuation to 68.5 (above 70 - 3.0 = 67.0) -> Stays HIGH due to hysteresis
        sev2 = RiskSeverity.from_score(68.5, current_severity=RiskSeverity.HIGH, hysteresis=3.0)
        self.assertEqual(sev2, RiskSeverity.HIGH)

        # Drops to 66.0 (below 67.0) -> De-escalates to MEDIUM
        sev3 = RiskSeverity.from_score(66.0, current_severity=RiskSeverity.HIGH, hysteresis=3.0)
        self.assertEqual(sev3, RiskSeverity.MEDIUM)

    def test_temporal_escalation(self):
        """Test linear score accumulation during sustained threats."""
        config = RiskEngineConfig(rules=[self.rule_loiter_risk], use_mock=True)
        engine = create_risk_engine(config)

        c_evt = CorrelatedEvent(
            event_id="cevt_01",
            rule_id="RULE_LOITERING",
            name="Loitering Event",
            state=EventState.ACTIVE,
            camera_id="CAM_01",
            primary_track_id=1,
            start_timestamp=10.0,
            last_updated_timestamp=10.0,
            overall_confidence=0.8,
            evidence_chain=[],
        )

        # Frame 1 at t=10s
        ei1 = _make_event_intelligence_result("CAM_01", 1, 10.0, [c_evt])
        tr1 = _make_track_result("CAM_01", 1, 10.0, [1])
        res1 = engine.assess(ei1, track_result=tr1)
        score1 = res1.assessments[0].severity_score

        # Frame 2 at t=15s (5 seconds sustained persistence at rate 2.0/s -> +10 pts)
        c_evt.last_updated_timestamp = 15.0
        ei2 = _make_event_intelligence_result("CAM_01", 2, 15.0, [c_evt])
        tr2 = _make_track_result("CAM_01", 2, 15.0, [1])
        res2 = engine.assess(ei2, track_result=tr2)
        score2 = res2.assessments[0].severity_score

        self.assertAlmostEqual(score2, score1 + 10.0, delta=0.5)
        self.assertEqual(res2.assessments[0].state, RiskState.ESCALATED)

    def test_exponential_decay_and_resolution(self):
        """Test exponential decay when threat subsides and transition to RESOLVED."""
        config = RiskEngineConfig(rules=[self.rule_loiter_risk], resolution_timeout_seconds=8.0, use_mock=True)
        engine = create_risk_engine(config)

        c_evt = CorrelatedEvent(
            event_id="cevt_01",
            rule_id="RULE_LOITERING",
            name="Loitering Event",
            state=EventState.ACTIVE,
            camera_id="CAM_01",
            primary_track_id=1,
            start_timestamp=0.0,
            last_updated_timestamp=0.0,
            overall_confidence=0.8,
            evidence_chain=[],
        )

        # Frame 1: Active threat
        ei1 = _make_event_intelligence_result("CAM_01", 1, 0.0, [c_evt])
        tr1 = _make_track_result("CAM_01", 1, 0.0, [1])
        res1 = engine.assess(ei1, track_result=tr1)
        init_score = res1.assessments[0].severity_score
        self.assertGreater(init_score, 0.0)

        # Frame 2: Threat subsides, after 4s (half-life = 4.0s)
        ei2 = _make_event_intelligence_result("CAM_01", 2, 4.0, [])
        tr2 = _make_track_result("CAM_01", 2, 4.0, [1])
        res2 = engine.assess(ei2, track_result=tr2)
        self.assertEqual(len(res2.assessments), 1)
        decayed_score = res2.assessments[0].severity_score
        self.assertAlmostEqual(decayed_score, init_score / 2.0, delta=1.5)
        self.assertEqual(res2.assessments[0].state, RiskState.DE_ESCALATING)

        # Frame 3: After resolution timeout (>8.0s)
        ei3 = _make_event_intelligence_result("CAM_01", 3, 12.0, [])
        tr3 = _make_track_result("CAM_01", 3, 12.0, [1])
        res3 = engine.assess(ei3, track_result=tr3)
        # Should be expired/resolved and removed from active list
        self.assertEqual(len(res3.assessments), 0)

    def test_alert_deduplication_and_storm_prevention(self):
        """Test that identical threats across continuous frames do not trigger alert storms."""
        config = RiskEngineConfig(
            rules=[self.rule_loiter_risk],
            alert_score_delta_threshold=15.0,
            alert_cooldown_seconds=10.0,
            use_mock=True,
        )
        engine = create_risk_engine(config)

        c_evt = CorrelatedEvent(
            event_id="cevt_01",
            rule_id="RULE_LOITERING",
            name="Loitering Event",
            state=EventState.ACTIVE,
            camera_id="CAM_01",
            primary_track_id=1,
            start_timestamp=0.0,
            last_updated_timestamp=0.0,
            overall_confidence=0.8,
            evidence_chain=[],
        )

        # Frame 1 at t=0s -> Initial Alert Emitted
        ei1 = _make_event_intelligence_result("CAM_01", 1, 0.0, [c_evt])
        tr1 = _make_track_result("CAM_01", 1, 0.0, [1])
        res1 = engine.assess(ei1, track_result=tr1)
        self.assertEqual(len(res1.alerts), 1)

        # Frames 2 to 10 within 5 seconds without significant delta -> Alert Suppressed
        total_alerts_middle = 0
        for i in range(2, 10):
            t = float(i) * 0.5
            c_evt.last_updated_timestamp = t
            ei = _make_event_intelligence_result("CAM_01", i, t, [c_evt])
            tr = _make_track_result("CAM_01", i, t, [1])
            res = engine.assess(ei, track_result=tr)
            total_alerts_middle += len(res.alerts)

        self.assertEqual(total_alerts_middle, 0, "Alert storm occurred! Alerts were not suppressed.")

        # Frame 11 at t=12.0s (> 10s cooldown expired) -> Refresh alert emitted
        ei11 = _make_event_intelligence_result("CAM_01", 11, 12.0, [c_evt])
        tr11 = _make_track_result("CAM_01", 11, 12.0, [1])
        res11 = engine.assess(ei11, track_result=tr11)
        self.assertEqual(len(res11.alerts), 1)

    def test_evidence_lineage_preservation(self):
        """Test that original upstream evidence items are preserved in RiskAssessment."""
        config = RiskEngineConfig(rules=[self.rule_loiter_risk], use_mock=True)
        engine = create_risk_engine(config)

        ev_upstream = EvidenceItem(
            evidence_type="BBOX_DETECTION",
            source_module="civis.detection",
            timestamp=5.0,
            camera_id="CAM_01",
            track_id=1,
            description="Person bounding box",
        )
        c_evt = CorrelatedEvent(
            event_id="cevt_01",
            rule_id="RULE_LOITERING",
            name="Loitering Event",
            state=EventState.ACTIVE,
            camera_id="CAM_01",
            primary_track_id=1,
            start_timestamp=5.0,
            last_updated_timestamp=5.0,
            overall_confidence=0.85,
            evidence_chain=[ev_upstream],
        )

        ei = _make_event_intelligence_result("CAM_01", 1, 5.0, [c_evt])
        tr = _make_track_result("CAM_01", 1, 5.0, [1])
        res = engine.assess(ei, track_result=tr)

        self.assertIn(ev_upstream, res.assessments[0].evidence_chain)

    def test_entity_resolution_and_multi_camera_isolation(self):
        """Test camera isolation and entity key resolution."""
        memory = AssessmentMemory()
        k1 = memory.resolve_entity_key("CAM_01", 1, identity_id=None)
        k2 = memory.resolve_entity_key("CAM_02", 1, identity_id=None)
        self.assertEqual(k1, "cam_CAM_01_trk_1")
        self.assertEqual(k2, "cam_CAM_02_trk_1")
        self.assertNotEqual(k1, k2, "Multi-camera isolation failed!")

        # Known identity resolution
        k3 = memory.resolve_entity_key("CAM_01", 1, identity_id="PERSON_ALICE", identity_state=IdentityState.KNOWN)
        self.assertEqual(k3, "ident_PERSON_ALICE")

    def test_identity_rebinding(self):
        """Test that verifying an identity dynamically rebinds the assessment entity key."""
        config = RiskEngineConfig(rules=[self.rule_loiter_risk], use_mock=True)
        engine = create_risk_engine(config)

        c_evt = CorrelatedEvent(
            event_id="cevt_01",
            rule_id="RULE_LOITERING",
            name="Loitering Event",
            state=EventState.ACTIVE,
            camera_id="CAM_01",
            primary_track_id=1,
            start_timestamp=1.0,
            last_updated_timestamp=1.0,
            overall_confidence=0.8,
            evidence_chain=[],
        )

        # Step 1: Anonymous track
        ei1 = _make_event_intelligence_result("CAM_01", 1, 1.0, [c_evt])
        tr1 = _make_track_result("CAM_01", 1, 1.0, [1])
        res1 = engine.assess(ei1, track_result=tr1)
        self.assertEqual(res1.assessments[0].entity_key, "cam_CAM_01_trk_1")

        # Step 2: Identity recognized as Bob in step 2
        ident_bob = AssociatedIdentity(
            track_id=1,
            camera_id="CAM_01",
            identity_id="USER_BOB",
            name="Bob",
            state=IdentityState.KNOWN,
            similarity_score=0.92,
            recognition_confidence=0.9,
            association_confidence=0.95,
            observations_count=3,
        )
        ident_res = _make_identity_result("CAM_01", 2, 2.0, [ident_bob])
        ei2 = _make_event_intelligence_result("CAM_01", 2, 2.0, [c_evt])
        tr2 = _make_track_result("CAM_01", 2, 2.0, [1])

        res2 = engine.assess(ei2, identity_result=ident_res, track_result=tr2)
        self.assertEqual(res2.assessments[0].entity_key, "ident_USER_BOB")
        self.assertEqual(res2.assessments[0].identity_id, "USER_BOB")


if __name__ == "__main__":
    unittest.main()
