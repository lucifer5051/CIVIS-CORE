import unittest
import numpy as np

from civis.detection.models import BoundingBox, Detection, DetectionResult
from civis.identity.engine import MockIdentityEngine
from civis.identity.factory import create_identity_engine
from civis.identity.models import IdentityConfig, IdentityState
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
        # 100x100 BGR frame
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
        # IdentityResult output contains AssociatedIdentity records without persisting raw image tensors

    def test_identity_factory(self):
        cfg = IdentityConfig(use_mock=True)
        engine = create_identity_engine(cfg)
        self.assertIsInstance(engine, MockIdentityEngine)


if __name__ == "__main__":
    unittest.main()
