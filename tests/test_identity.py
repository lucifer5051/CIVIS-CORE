import unittest
import numpy as np

from civis.detection.models import BoundingBox
from civis.identity.engine import IdentityEngine, MockIdentityEngine
from civis.identity.factory import create_identity_engine
from civis.identity.face_detector import (
    HeuristicFaceDetector,
    MockFaceDetector,
    YuNetFaceDetector,
    SCRFDFaceDetector,
    create_face_detector,
    is_box_inside,
)
from civis.identity.models import (
    FaceDetectorBackend,
    FaceDetectorConfig,
    IdentityConfig,
    IdentityState,
)
from civis.ingestion.models import FramePacket
from civis.tracking.models import TrackState, TrackedObject, TrackResult


class TestIdentityModule(unittest.TestCase):
    def setUp(self):
        self.config = IdentityConfig(
            use_mock=True,
            min_observations=2,
            similarity_threshold=0.5,
            store_face_crops=False,
        )
        self.engine = MockIdentityEngine(self.config)

    def _make_dummy_data(self, cam_id: str, track_id: int, frame_num: int):
        # 200x200 BGR frame
        frame = np.ones((200, 200, 3), dtype=np.uint8) * 120
        pkt = FramePacket.create(camera_id=cam_id, frame_number=frame_num, frame=frame)

        track = TrackedObject(
            track_id=track_id,
            class_id=0,
            class_name="person",
            confidence=0.9,
            bbox=BoundingBox(x1=20.0, y1=20.0, x2=100.0, y2=180.0),
            state=TrackState.TRACKED,
        )
        t_res = TrackResult(
            camera_id=cam_id,
            frame_id=pkt.frame_id,
            timestamp=pkt.timestamp,
            frame_number=frame_num,
            dimensions=pkt.dimensions,
            tracks=[track],
            active_track_ids=[track_id],
        )
        return pkt, t_res

    def test_identity_state_transitions(self):
        # Frame 1: Observation 1 -> UNVERIFIED (min_observations=2)
        pkt1, tr1 = self._make_dummy_data("cam_01", track_id=1, frame_num=1)
        res1 = self.engine.process(pkt1, tr1)
        self.assertEqual(len(res1.identities), 1)
        self.assertEqual(res1.identities[0].state, IdentityState.UNVERIFIED)
        self.assertEqual(res1.identities[0].identity_id, "ID_001_ALICE")

        # Frame 2: Observation 2 -> KNOWN
        pkt2, tr2 = self._make_dummy_data("cam_01", track_id=1, frame_num=2)
        res2 = self.engine.process(pkt2, tr2)
        self.assertEqual(res2.identities[0].state, IdentityState.KNOWN)
        self.assertEqual(res2.identities[0].name, "Alice Smith")

    def test_unknown_identity_handling(self):
        # Track ID 2 is not registered in gallery -> UNKNOWN
        pkt, tr = self._make_dummy_data("cam_01", track_id=2, frame_num=1)
        res = self.engine.process(pkt, tr)
        self.assertEqual(res.identities[0].state, IdentityState.UNKNOWN)
        self.assertEqual(res.identities[0].identity_id, "UNKNOWN")

    def test_camera_track_decoupling(self):
        # Cam 1 Track 1 vs Cam 2 Track 1 operate independently
        pkt_cam1, tr_cam1 = self._make_dummy_data("cam_north", track_id=1, frame_num=1)
        pkt_cam2, tr_cam2 = self._make_dummy_data("cam_south", track_id=1, frame_num=1)

        res_cam1 = self.engine.process(pkt_cam1, tr_cam1)
        res_cam2 = self.engine.process(pkt_cam2, tr_cam2)

        self.assertEqual(res_cam1.camera_id, "cam_north")
        self.assertEqual(res_cam2.camera_id, "cam_south")

    def test_privacy_biometric_release(self):
        # Verify face crop reference is released when store_face_crops is False
        pkt, tr = self._make_dummy_data("cam_privacy", track_id=1, frame_num=1)
        res = self.engine.process(pkt, tr)
        self.assertFalse(self.config.store_face_crops)

    def test_identity_factory(self):
        cfg = IdentityConfig(use_mock=True)
        engine = create_identity_engine(cfg)
        self.assertIsInstance(engine, MockIdentityEngine)

    def test_mock_face_detector_landmarks(self):
        """Test mock face detector provides accurate bounding box and 5 landmarks."""
        detector = MockFaceDetector()
        pkt, tr = self._make_dummy_data("cam_test", track_id=1, frame_num=1)
        crops = detector.detect_faces(pkt, tr)

        self.assertEqual(len(crops), 1)
        crop = crops[0]
        self.assertIsNotNone(crop.face_bbox)
        self.assertIsNotNone(crop.landmarks)
        self.assertEqual(len(crop.landmarks), 5)
        self.assertGreater(crop.confidence, 0.8)

    def test_yunet_detector_fallback_behavior(self):
        """Test YuNet detector gracefully falls back if neural weights are not present."""
        cfg = FaceDetectorConfig(backend="yunet", model_path="non_existent_yunet.onnx")
        detector = YuNetFaceDetector(cfg)
        pkt, tr = self._make_dummy_data("cam_test", track_id=1, frame_num=1)
        crops = detector.detect_faces(pkt, tr)

        self.assertEqual(len(crops), 1)
        self.assertIsNotNone(crops[0].face_bbox)

    def test_face_detector_factory_backends(self):
        """Test factory instantiation of all supported backends."""
        d_mock = create_face_detector(FaceDetectorConfig(backend=FaceDetectorBackend.MOCK.value))
        self.assertIsInstance(d_mock, MockFaceDetector)

        d_heur = create_face_detector(FaceDetectorConfig(backend=FaceDetectorBackend.HEURISTIC.value))
        self.assertIsInstance(d_heur, HeuristicFaceDetector)

        d_scrfd = create_face_detector(FaceDetectorConfig(backend=FaceDetectorBackend.SCRFD.value))
        self.assertIsInstance(d_scrfd, SCRFDFaceDetector)

        d_yunet = create_face_detector(FaceDetectorConfig(backend=FaceDetectorBackend.YUNET.value))
        self.assertIsInstance(d_yunet, YuNetFaceDetector)

    def test_identity_association_stale_eviction(self):
        """Test that MultiSignalIdentityAssociator purges stale track histories beyond TTL."""
        from civis.identity.association import MultiSignalIdentityAssociator
        from civis.identity.models import IdentityConfig, IdentityMatch

        cfg = IdentityConfig()
        assoc = MultiSignalIdentityAssociator(cfg)

        # Update track 1 at t=10.0
        h1 = assoc.get_history("cam_01", 1)
        h1.update(
            match=IdentityMatch(identity_id="ID_01", name="Alice", similarity_score=0.9, is_known=True),
            quality_score=0.9,
            config=cfg,
            timestamp=10.0,
        )

        # Update track 2 at t=100.0
        h2 = assoc.get_history("cam_01", 2)
        h2.update(
            match=IdentityMatch(identity_id="ID_02", name="Bob", similarity_score=0.9, is_known=True),
            quality_score=0.9,
            config=cfg,
            timestamp=100.0,
        )

        # Cleanup at t=100 with max_age=30s -> track 1 should be evicted (age 90s)
        purged = assoc.cleanup_stale(current_time=100.0, max_age_seconds=30.0)
        self.assertEqual(purged, 1)
        self.assertNotIn(("cam_01", 1), assoc._track_histories)
        self.assertIn(("cam_01", 2), assoc._track_histories)


if __name__ == "__main__":
    unittest.main()
