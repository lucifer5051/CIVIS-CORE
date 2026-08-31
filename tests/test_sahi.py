import unittest
import numpy as np

from civis.detection.factory import create_detector
from civis.detection.mock_detector import MockDetector
from civis.detection.models import BoundingBox, Detection, DetectionMode, DetectorConfig, SAHIConfig
from civis.detection.sahi_detector import SAHIDetector
from civis.ingestion.models import FramePacket


class TestSAHIDetector(unittest.TestCase):
    def setUp(self):
        self.mock_base = MockDetector()
        self.dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        self.packet = FramePacket.create(camera_id="cam_sahi_test", frame_number=1, frame=self.dummy_frame)

    def test_full_frame_mode(self):
        sahi_cfg = SAHIConfig(mode=DetectionMode.FULL_FRAME)
        sahi_det = SAHIDetector(base_detector=self.mock_base, sahi_config=sahi_cfg)

        result = sahi_det.detect(self.packet)
        self.assertEqual(result.camera_id, "cam_sahi_test")
        self.assertEqual(result.metadata.get("sahi_mode"), "full_frame")

    def test_sliced_only_mode(self):
        sahi_cfg = SAHIConfig(
            slice_height=240,
            slice_width=320,
            overlap_height_ratio=0.1,
            overlap_width_ratio=0.1,
            mode=DetectionMode.SLICED_ONLY,
        )
        sahi_det = SAHIDetector(base_detector=self.mock_base, sahi_config=sahi_cfg)

        result = sahi_det.detect(self.packet)
        self.assertEqual(result.camera_id, "cam_sahi_test")
        self.assertEqual(result.metadata.get("sahi_mode"), "sliced_only")
        self.assertGreater(result.metadata.get("slice_count"), 1)
        self.assertGreater(result.num_detections, 0)

    def test_hybrid_mode(self):
        sahi_cfg = SAHIConfig(
            slice_height=240,
            slice_width=320,
            overlap_height_ratio=0.2,
            overlap_width_ratio=0.2,
            mode=DetectionMode.HYBRID,
        )
        sahi_det = SAHIDetector(base_detector=self.mock_base, sahi_config=sahi_cfg)

        result = sahi_det.detect(self.packet)
        self.assertEqual(result.camera_id, "cam_sahi_test")
        self.assertEqual(result.metadata.get("sahi_mode"), "hybrid")
        self.assertGreater(result.num_detections, 0)

    def test_auto_adaptive_mode_resolution(self):
        """Test AUTO mode selectively triggers full_frame on standard res, hybrid on 4K res."""
        # 1. Standard low-res frame (640x480) -> Resolves to full_frame
        sahi_cfg = SAHIConfig(mode=DetectionMode.AUTO, auto_min_dimension=960)
        sahi_det = SAHIDetector(base_detector=self.mock_base, sahi_config=sahi_cfg)
        res_low = sahi_det.detect(self.packet)
        self.assertEqual(res_low.metadata.get("sahi_mode"), "full_frame")

        # 2. High-res frame (1920x1080) -> Resolves to hybrid slicing
        high_res_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        high_res_pkt = FramePacket.create(camera_id="cam_4k", frame_number=1, frame=high_res_frame)
        res_high = sahi_det.detect(high_res_pkt)
        self.assertEqual(res_high.metadata.get("sahi_mode"), "hybrid")

    def test_tile_coordinate_restoration(self):
        """Verify sliced detections restore global coordinates within frame boundary."""
        sahi_cfg = SAHIConfig(
            slice_height=200,
            slice_width=200,
            mode=DetectionMode.SLICED_ONLY,
        )
        sahi_det = SAHIDetector(base_detector=self.mock_base, sahi_config=sahi_cfg)
        result = sahi_det.detect(self.packet)

        for det in result.detections:
            self.assertGreaterEqual(det.bbox.x1, 0.0)
            self.assertGreaterEqual(det.bbox.y1, 0.0)
            self.assertLessEqual(det.bbox.x2, 640.0)
            self.assertLessEqual(det.bbox.y2, 480.0)

    def test_duplicate_suppression_nms(self):
        """Test duplicate detections from overlapping slices are merged cleanly."""
        sahi_cfg = SAHIConfig(
            slice_height=200,
            slice_width=200,
            postprocess_match_threshold=0.5,
        )
        sahi_det = SAHIDetector(base_detector=self.mock_base, sahi_config=sahi_cfg)

        raw_duplicates = [
            Detection(class_id=0, class_name="person", confidence=0.85, bbox=BoundingBox(x1=50, y1=50, x2=150, y2=150)),
            Detection(class_id=0, class_name="person", confidence=0.90, bbox=BoundingBox(x1=52, y1=48, x2=153, y2=152)),
        ]
        merged = sahi_det._merge_detections(raw_duplicates, (640, 480))
        self.assertEqual(len(merged), 1)
        self.assertAlmostEqual(merged[0].confidence, 0.90, places=2)

    def test_factory_with_sahi(self):
        det_cfg = DetectorConfig(
            use_mock=True,
            sahi_config=SAHIConfig(
                slice_height=200,
                slice_width=200,
                mode=DetectionMode.HYBRID,
            ),
        )
        detector = create_detector(det_cfg)
        self.assertIsInstance(detector, SAHIDetector)
        self.assertEqual(detector.sahi_config.slice_height, 200)


if __name__ == "__main__":
    unittest.main()
