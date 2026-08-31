import os
import tempfile
import unittest

from civis.behavior.models import BehaviorEvent, BehaviorObservation, BehaviorResult, BehaviorState
from civis.detection.models import BoundingBox, Detection, DetectionResult
from civis.event_intelligence.models import CorrelatedEvent, EventIntelligenceResult, EventState
from civis.evidence import (
    CustodyAction,
    EvidenceEngineConfig,
    EvidenceLedger,
    EvidenceStage,
    ForensicPackager,
    RetentionManager,
    RetentionPolicy,
    TimelineBuilder,
    compute_record_hash,
    compute_sha256,
    create_evidence_engine,
)
from civis.identity.models import AssociatedIdentity, IdentityResult, IdentityState
from civis.risk.models import (
    RiskAlert,
    RiskAssessment,
    RiskAssessmentResult,
    RiskSeverity,
    RiskState,
    ThreatCategory,
)
from civis.tracking.models import TrackResult, TrackState, TrackedObject


class TestEvidenceEngine(unittest.TestCase):

    def test_sha256_canonical_hashing_determinism(self):
        """Test that canonical JSON hashing is strictly deterministic regardless of dict key ordering."""
        d1 = {"b": 2, "a": 1, "nested": {"y": 20, "x": 10}}
        d2 = {"nested": {"x": 10, "y": 20}, "a": 1, "b": 2}

        h1 = compute_record_hash(0, "detection", "CAM_01", "CAM_01_1", 10.0, d1, "GENESIS")
        h2 = compute_record_hash(0, "detection", "CAM_01", "CAM_01_1", 10.0, d2, "GENESIS")

        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)

    def test_hash_chain_linking_and_integrity_verification(self):
        """Test append-only ledger cryptographic hash-chaining and verification."""
        ledger = EvidenceLedger(enable_hash_chain=True)

        r1 = ledger.append("ev_1", EvidenceStage.DETECTION, "CAM_01", "f_1", 1, 0.0, {"class": "person"})
        r2 = ledger.append("ev_2", EvidenceStage.TRACKING, "CAM_01", "f_1", 1, 0.0, {"track_id": 1})
        r3 = ledger.append("ev_3", EvidenceStage.RISK_ASSESSMENT, "CAM_01", "f_1", 1, 0.0, {"score": 85.0})

        self.assertEqual(r2.previous_record_hash, r1.record_hash)
        self.assertEqual(r3.previous_record_hash, r2.record_hash)

        is_valid, err = ledger.verify_integrity()
        self.assertTrue(is_valid)
        self.assertIsNone(err)

    def test_tamper_detection(self):
        """Test that modifying a single byte in the ledger causes cryptographic verification failure."""
        ledger = EvidenceLedger(enable_hash_chain=True)

        ledger.append("ev_1", EvidenceStage.DETECTION, "CAM_01", "f_1", 1, 0.0, {"class": "person"})
        r2 = ledger.append("ev_2", EvidenceStage.RISK_ASSESSMENT, "CAM_01", "f_1", 1, 0.0, {"score": 40.0})
        ledger.append("ev_3", EvidenceStage.RISK_ASSESSMENT, "CAM_01", "f_1", 1, 0.0, {"score": 50.0})

        # Illicitly tamper with record #2 payload (e.g. lowering risk score from 40.0 to 10.0)
        r2.payload["score"] = 10.0

        is_valid, err = ledger.verify_integrity()
        self.assertFalse(is_valid)
        self.assertIn("Tampered record content at index 1", err)

    def test_complete_pipeline_lineage_ingestion(self):
        """Test ingesting complete Detection -> Track -> Identity -> Behavior -> Event -> Risk pipeline."""
        engine = create_evidence_engine(EvidenceEngineConfig(use_mock=True, auto_seal_alerts=True))

        # 1. Detection
        det = DetectionResult(
            camera_id="CAM_01",
            frame_id="CAM_01_1",
            timestamp=10.0,
            frame_number=1,
            dimensions=(640, 480),
            detections=[Detection(0, "person", 0.95, BoundingBox(50, 50, 150, 250))],
        )

        # 2. Track
        trk = TrackResult(
            camera_id="CAM_01",
            frame_id="CAM_01_1",
            timestamp=10.0,
            frame_number=1,
            dimensions=(640, 480),
            tracks=[TrackedObject(1, 0, "person", 0.95, BoundingBox(50, 50, 150, 250), TrackState.TRACKED)],
            active_track_ids=[1],
        )

        # 3. Identity
        ident = IdentityResult(
            camera_id="CAM_01",
            frame_id="CAM_01_1",
            timestamp=10.0,
            frame_number=1,
            dimensions=(640, 480),
            identities=[AssociatedIdentity(1, "CAM_01", "USER_ALICE", "Alice", IdentityState.KNOWN, 0.95, 0.9, 0.95, 3)],
        )

        # 4. Behavior
        beh = BehaviorResult(
            camera_id="CAM_01",
            frame_id="CAM_01_1",
            timestamp=10.0,
            frame_number=1,
            dimensions=(640, 480),
            observations=[BehaviorObservation(1, "CAM_01", "USER_ALICE", BehaviorState.LOITERING, 0.5, 12.0, ["VAULT"], [])],
            events=[BehaviorEvent("beh_ev_1", "CAM_01", "CAM_01_1", 10.0, "loitering", 1, [], "USER_ALICE", "VAULT")],
        )

        # 5. Event Intelligence
        ei = EventIntelligenceResult(
            camera_id="CAM_01",
            frame_id="CAM_01_1",
            timestamp=10.0,
            frame_number=1,
            dimensions=(640, 480),
            events=[CorrelatedEvent("cevt_1", "RULE_VAULT", "Vault Breach", EventState.ACTIVE, "CAM_01", 1, [], "USER_ALICE", 10.0, 10.0, 0.9, [], "Explanation")],
        )

        # 6. Risk Assessment
        risk = RiskAssessmentResult(
            camera_id="CAM_01",
            frame_id="CAM_01_1",
            timestamp=10.0,
            frame_number=1,
            dimensions=(640, 480),
            assessments=[RiskAssessment("rsk_1", "ident_USER_ALICE", "CAM_01", 1, "USER_ALICE", RiskState.ACTIVE, ThreatCategory.SECURITY_INTRUSION, RiskSeverity.HIGH, 85.0, 0.9, 10.0, 10.0, 85.0)],
            alerts=[RiskAlert("alt_1", "rsk_1", 10.0, "CAM_01", "ident_USER_ALICE", RiskSeverity.HIGH, 85.0, 0.9, "High Risk Intrusion", "Explanation", ["Vault Breach"])],
        )

        records = engine.ingest_pipeline_frame(
            detection_result=det,
            track_result=trk,
            identity_result=ident,
            behavior_result=beh,
            event_result=ei,
            risk_result=risk,
        )

        self.assertGreater(len(records), 5)
        is_valid, err = engine.verify_ledger_integrity()
        self.assertTrue(is_valid)

        # Check that alert was auto-sealed
        alert_rec = [r for r in records if "alt_1" in r.evidence_id][0]
        self.assertTrue(alert_rec.is_sealed)
        self.assertEqual(alert_rec.custody_trail[-1].action, CustodyAction.SEALED)

    def test_chain_of_custody_lifecycle(self):
        """Test logging chain-of-custody actions."""
        engine = create_evidence_engine()
        ledger = engine._ledger
        r = ledger.append("ev_100", EvidenceStage.RISK_ASSESSMENT, "CAM_01", "f_1", 1, 0.0, {"data": "test"})

        self.assertEqual(len(r.custody_trail), 1)
        self.assertEqual(r.custody_trail[0].action, CustodyAction.CAPTURED)

        engine.record_custody_action("ev_100", CustodyAction.REVIEWED if hasattr(CustodyAction, "REVIEWED") else CustodyAction.ENRICHED, "OFFICER_JONES", "Reviewed video playback")
        engine.record_custody_action("ev_100", CustodyAction.SEALED, "SUPERVISOR_SMITH", "Sealed for legal hold")

        self.assertEqual(len(r.custody_trail), 3)
        self.assertTrue(r.is_sealed)

    def test_investigation_timeline_synthesis_and_queries(self):
        """Test building filtered investigation timelines."""
        ledger = EvidenceLedger()
        ledger.append("ev_1", EvidenceStage.DETECTION, "CAM_01", "f_1", 1, 0.0, {"class": "person"}, track_id=1, global_entity_id="ENT_A")
        ledger.append("ev_2", EvidenceStage.BEHAVIOR, "CAM_01", "f_2", 2, 5.0, {"event": "dwell"}, track_id=1, global_entity_id="ENT_A")
        ledger.append("ev_3", EvidenceStage.RISK_ASSESSMENT, "CAM_02", "f_3", 3, 15.0, {"score": 90.0}, severity="critical", track_id=5, global_entity_id="ENT_B")

        # Query all for ENT_A
        records_a = ledger.query(entity_id="ENT_A")
        self.assertEqual(len(records_a), 2)

        timeline_a = TimelineBuilder.build_timeline(records_a, title="Entity A Movement")
        self.assertEqual(timeline_a.total_records, 2)
        self.assertEqual(timeline_a.start_timestamp, 0.0)
        self.assertEqual(timeline_a.end_timestamp, 5.0)
        self.assertIn("CAM_01", timeline_a.involved_cameras)

        # Query critical severity
        records_crit = ledger.query(min_severity="critical")
        self.assertEqual(len(records_crit), 1)
        self.assertEqual(records_crit[0].evidence_id, "ev_3")

    def test_forensic_package_export_and_manifest_verification(self):
        """Test exporting an RFC 8493 BagIt forensic package and verifying checksums."""
        ledger = EvidenceLedger()
        ledger.append("ev_1", EvidenceStage.DETECTION, "CAM_01", "f_1", 1, 0.0, {"class": "person"})
        ledger.append("ev_2", EvidenceStage.RISK_ASSESSMENT, "CAM_01", "f_2", 2, 5.0, {"score": 95.0}, severity="critical")

        timeline = TimelineBuilder.build_timeline(ledger.get_all_records(), title="Export Test")

        with tempfile.TemporaryDirectory() as tmp_dir:
            pkg_dir = os.path.join(tmp_dir, "incident_package_01")
            manifest = ForensicPackager.export_package(timeline, pkg_dir, root_ledger_hash="ROOT_HASH_TEST")

            self.assertTrue(manifest.is_valid)
            self.assertEqual(manifest.total_files, 2)
            self.assertTrue(os.path.isfile(os.path.join(pkg_dir, "manifest-sha256.txt")))
            self.assertTrue(os.path.isfile(os.path.join(pkg_dir, "data", "timeline.json")))

            # Verify package
            is_valid, err = ForensicPackager.verify_package(pkg_dir)
            self.assertTrue(is_valid)
            self.assertIsNone(err)

    def test_retention_policy_and_high_risk_preservation(self):
        """Test retention evaluation preserving high-risk records indefinitely while expiring old low-risk records."""
        ledger = EvidenceLedger()
        policy = RetentionPolicy(max_retention_days=1.0, retain_high_risk_indefinitely=True)
        retention = RetentionManager(policy)

        # Old low-risk record (timestamp = 0, current = 200,000s > 1 day)
        ledger.append("ev_old_low", EvidenceStage.DETECTION, "CAM_01", "f_1", 1, 0.0, {"class": "car"}, severity="low", risk_score=20.0)

        # Old HIGH-risk record (timestamp = 0)
        ledger.append("ev_old_high", EvidenceStage.RISK_ASSESSMENT, "CAM_01", "f_1", 1, 0.0, {"desc": "breach"}, severity="high", risk_score=85.0)

        # Fresh low-risk record (timestamp = 190,000s)
        ledger.append("ev_fresh_low", EvidenceStage.DETECTION, "CAM_01", "f_2", 2, 190000.0, {"class": "person"}, severity="low", risk_score=10.0)

        to_retain, to_purge = retention.evaluate_retention(ledger, current_time=200000.0)

        retain_ids = {r.evidence_id for r in to_retain}
        purge_ids = {r.evidence_id for r in to_purge}

        self.assertIn("ev_old_high", retain_ids, "High-risk record must be retained indefinitely!")
        self.assertIn("ev_fresh_low", retain_ids, "Fresh record must be retained!")
        self.assertIn("ev_old_low", purge_ids, "Old low-risk record must be purged!")


if __name__ == "__main__":
    unittest.main()
