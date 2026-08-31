import unittest
import numpy as np
import torch

from civis.detection.models import BoundingBox
from civis.identity.models import AssociatedIdentity, IdentityResult, IdentityState
from civis.ingestion.models import FramePacket
from civis.reid import (
    CameraTopologyConstraint,
    CrossCameraReIDEngine,
    MockAppearanceEmbedder,
    OSNetEmbedder,
    ReIDEngineConfig,
    create_cross_camera_reid_engine,
)
from civis.reid.gallery import CrossCameraGallery
from civis.reid.matcher import CrossCameraMatcher
from civis.reid.osnet import OSNet, build_osnet_x1_0
from civis.tracking.models import TrackResult, TrackState, TrackedObject


def _make_frame_packet(cam_id: str, frame_num: int, ts: float) -> FramePacket:
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frame[100:300, 100:200] = (120, 180, 220)  # Distinct person region
    return FramePacket.create(
        camera_id=cam_id,
        frame_number=frame_num,
        frame=frame,
        timestamp=ts,
    )


def _make_track_result(cam_id: str, frame_num: int, ts: float, track_ids: list) -> TrackResult:
    tracks = [
        TrackedObject(
            track_id=t_id,
            class_id=0,
            class_name="person",
            confidence=0.95,
            bbox=BoundingBox(100.0, 100.0, 200.0, 300.0),
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


class TestCrossCameraReID(unittest.TestCase):

    def test_osnet_architecture_and_l2_normalization(self):
        """Test OSNet forward pass output shape (B, 512) and L2 unit norm."""
        model = build_osnet_x1_0()
        model.eval()
        dummy_input = torch.randn(2, 3, 256, 128)
        with torch.no_grad():
            output = model(dummy_input, normalize=True)

        self.assertEqual(output.shape, (2, 512))
        norms = torch.norm(output, p=2, dim=1).numpy()
        np.testing.assert_allclose(norms, [1.0, 1.0], atol=1e-5)

    def test_embedder_extraction_and_mock(self):
        """Test OSNetEmbedder and MockAppearanceEmbedder."""
        crop = np.full((200, 100, 3), 150, dtype=np.uint8)

        # Mock embedder
        mock_emb = MockAppearanceEmbedder()
        res_mock = mock_emb.extract_embedding(crop, "CAM_01", 1, 10.0)
        self.assertIsNotNone(res_mock)
        self.assertEqual(res_mock.dimension, 512)
        self.assertAlmostEqual(np.linalg.norm(res_mock.embedding), 1.0, places=4)

        # Small crop filtering
        small_crop = np.zeros((10, 10, 3), dtype=np.uint8)
        res_small = mock_emb.extract_embedding(small_crop, "CAM_01", 1, 10.0)
        self.assertIsNone(res_small)

    def test_ema_track_appearance_smoothing(self):
        """Test that sequential observations update the gallery embedding via EMA."""
        gallery = CrossCameraGallery(ema_alpha=0.6)
        v1 = np.zeros(512, dtype=np.float32)
        v1[0] = 1.0
        v2 = np.zeros(512, dtype=np.float32)
        v2[1] = 1.0

        entry1 = gallery.update_track_appearance("CAM_01", 1, v1, 1.0, (100, 100, 200, 300))
        self.assertEqual(entry1.observations_count, 1)
        self.assertEqual(entry1.smoothed_embedding[0], 1.0)

        entry2 = gallery.update_track_appearance("CAM_01", 1, v2, 2.0, (100, 100, 200, 300))
        self.assertEqual(entry2.observations_count, 2)
        # Expected unnormalized: 0.6 * v2 + 0.4 * v1 -> [0.4, 0.6, 0, ...]
        expected_norm = np.linalg.norm([0.4, 0.6])
        self.assertAlmostEqual(entry2.smoothed_embedding[0], 0.4 / expected_norm, places=4)
        self.assertAlmostEqual(entry2.smoothed_embedding[1], 0.6 / expected_norm, places=4)

    def test_cross_camera_matching_and_global_entity(self):
        """Test matching the same person appearance across CAM_01 and CAM_02."""
        config = ReIDEngineConfig(similarity_threshold=0.80, use_mock=True)
        engine = create_cross_camera_reid_engine(config)

        # Force identical appearance embeddings for CAM_01 Track 1 and CAM_02 Track 5
        vec = np.zeros(512, dtype=np.float32)
        vec[0] = 1.0

        # Step 1: Camera 1 detects Track 1 at t=0s
        p1 = _make_frame_packet("CAM_01", 1, 0.0)
        t1 = _make_track_result("CAM_01", 1, 0.0, [1])
        res1 = engine.process({"CAM_01": p1}, {"CAM_01": t1})

        self.assertEqual(len(res1.global_entities), 1)
        global_id_1 = res1.global_entities[0].global_entity_id
        self.assertEqual(len(res1.active_matches), 0)

        # Manually set matching embedding in gallery for test determinism
        entry_cam1 = engine._gallery.get_track_entry("CAM_01", 1)
        entry_cam1.smoothed_embedding = vec

        # Step 2: Camera 2 detects Track 5 with matching appearance at t=10s
        p2 = _make_frame_packet("CAM_02", 1, 10.0)
        t2 = _make_track_result("CAM_02", 1, 10.0, [5])

        # Overwrite embedder vector for Track 5
        engine._embedder.extract_embedding = lambda crop_image=None, camera_id=None, track_id=None, timestamp=0.0, **kwargs: type(
            "Emb", (), {"embedding": vec, "dimension": 512, "timestamp": timestamp}
        )()

        res2 = engine.process({"CAM_02": p2}, {"CAM_02": t2})

        self.assertEqual(len(res2.active_matches), 1)
        match = res2.active_matches[0]
        self.assertEqual(match.query_camera_id, "CAM_02")
        self.assertEqual(match.query_track_id, 5)
        self.assertEqual(match.matched_camera_id, "CAM_01")
        self.assertEqual(match.matched_track_id, 1)
        self.assertAlmostEqual(match.similarity_score, 1.0, places=3)
        self.assertEqual(match.global_entity_id, global_id_1)

        # Global entity should now bind both cameras
        self.assertEqual(len(res2.global_entities), 1)
        ent = res2.global_entities[0]
        self.assertEqual(ent.num_associated_cameras, 2)
        cams = {b.camera_id for b in ent.associated_tracks}
        self.assertEqual(cams, {"CAM_01", "CAM_02"})

    def test_camera_topology_and_temporal_gating(self):
        """Test rejection of candidate matches violating travel time constraints."""
        topo = [
            CameraTopologyConstraint(
                source_camera_id="CAM_01",
                target_camera_id="CAM_02",
                min_travel_time_sec=5.0,
                max_travel_time_sec=60.0,
            )
        ]
        matcher = CrossCameraMatcher(similarity_threshold=0.70, topology_constraints=topo)
        gallery = CrossCameraGallery()

        vec = np.zeros(512, dtype=np.float32)
        vec[0] = 1.0

        # CAM_01 track at t=10.0s
        gallery.update_track_appearance("CAM_01", 1, vec, 10.0, (0, 0, 100, 100))

        # Query CAM_02 track at t=11.0s (dt = 1.0s < min_travel_time 5.0s -> physically impossible)
        query_entry_too_fast = gallery.update_track_appearance("CAM_02", 2, vec, 11.0, (0, 0, 100, 100))
        match_fast = matcher.find_best_match(query_entry_too_fast, gallery)
        self.assertIsNone(match_fast, "Match should be rejected due to travel time too fast!")

        # Query CAM_02 track at t=20.0s (dt = 10.0s -> within [5.0, 60.0]s)
        query_entry_valid = gallery.update_track_appearance("CAM_02", 3, vec, 20.0, (0, 0, 100, 100))
        match_valid = matcher.find_best_match(query_entry_valid, gallery)
        self.assertIsNotNone(match_valid, "Valid topology match should be accepted!")

    def test_gallery_ttl_cleanup(self):
        """Test that inactive tracks beyond TTL are purged."""
        gallery = CrossCameraGallery(gallery_ttl_seconds=15.0)
        vec = np.zeros(512, dtype=np.float32)
        vec[0] = 1.0

        e1 = gallery.update_track_appearance("CAM_01", 1, vec, 0.0, (0, 0, 100, 100))
        gallery.create_or_bind_global_entity(e1)
        self.assertEqual(len(gallery.get_all_global_entities()), 1)

        # Cleanup at t=10s (within TTL)
        gallery.cleanup_inactive(10.0)
        self.assertEqual(len(gallery.get_all_global_entities()), 1)

        # Cleanup at t=25s (> 15s TTL)
        gallery.cleanup_inactive(25.0)
        self.assertEqual(len(gallery.get_all_global_entities()), 0)

    def test_biometric_identity_and_reid_coexistence(self):
        """Test that verified biometric identity links to GlobalEntity while keeping Re-ID modular."""
        config = ReIDEngineConfig(use_mock=True)
        engine = create_cross_camera_reid_engine(config)

        p1 = _make_frame_packet("CAM_01", 1, 0.0)
        t1 = _make_track_result("CAM_01", 1, 0.0, [1])

        ident = AssociatedIdentity(
            track_id=1,
            camera_id="CAM_01",
            identity_id="PERSON_ALICE",
            name="Alice",
            state=IdentityState.KNOWN,
            similarity_score=0.94,
            recognition_confidence=0.95,
            association_confidence=0.98,
            observations_count=5,
        )
        ident_res = IdentityResult("CAM_01", "CAM_01_1", 0.0, 1, (640, 480), [ident])

        res = engine.process({"CAM_01": p1}, {"CAM_01": t1}, {"CAM_01": ident_res})
        self.assertEqual(len(res.global_entities), 1)
        self.assertEqual(res.global_entities[0].primary_identity_id, "PERSON_ALICE")


if __name__ == "__main__":
    unittest.main()
