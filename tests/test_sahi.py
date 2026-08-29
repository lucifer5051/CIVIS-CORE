import unittest
import numpy as np

from civis.detection.factory import create_detector
from civis.detection.mock_detector import MockDetector
from civis.detection.models import DetectionMode, DetectorConfig, SAHIConfig
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
