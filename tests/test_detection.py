import unittest
import numpy as np

from civis.detection.factory import create_detector
from civis.detection.mock_detector import MockDetector
from civis.detection.models import BoundingBox, Detection, DetectionResult, DetectorConfig
from civis.ingestion.models import FramePacket


class TestBoundingBoxAndModels(unittest.TestCase):
    def test_bounding_box_properties(self):
        bbox = BoundingBox(x1=10.0, y1=20.0, x2=110.0, y2=220.0)
        self.assertEqual(bbox.width, 100.0)
        self.assertEqual(bbox.height, 200.0)
        self.assertEqual(bbox.area, 20000.0)
        self.assertEqual(bbox.center, (60.0, 120.0))
        self.assertEqual(bbox.xywh, (60.0, 120.0, 100.0, 200.0))

        bdict = bbox.to_dict()
        self.assertEqual(bdict["x1"], 10.0)
        self.assertEqual(bdict["width"], 100.0)

    def test_detection_and_result(self):
        bbox = BoundingBox(x1=0.0, y1=0.0, x2=50.0, y2=50.0)
        det = Detection(class_id=0, class_name="person", confidence=0.95, bbox=bbox)
        res = DetectionResult(
            camera_id="cam_01",
            frame_id="frame_01",
            timestamp=123456.789,
            frame_number=1,
            dimensions=(640, 480),
            detections=[det],
            inference_time_ms=12.5,
        )
        self.assertEqual(res.num_detections, 1)
        self.assertEqual(res.detections[0].class_name, "person")


class TestMockDetector(unittest.TestCase):
    def test_mock_detector(self):
        detector = MockDetector()
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        packet = FramePacket.create(camera_id="cam_test", frame_number=1, frame=dummy_frame)

        result = detector.detect(packet)
        self.assertEqual(result.camera_id, "cam_test")
        self.assertEqual(result.frame_id, packet.frame_id)
        self.assertGreater(result.num_detections, 0)
        self.assertGreater(result.inference_time_ms, 0.0)


class TestDetectorFactory(unittest.TestCase):
    def test_factory_create_mock(self):
        cfg = DetectorConfig(use_mock=True)
        detector = create_detector(cfg)
        self.assertIsInstance(detector, MockDetector)

    def test_detector_config_backend_field(self):
        cfg = DetectorConfig(backend="mock", use_mock=True)
        self.assertEqual(cfg.backend, "mock")


if __name__ == "__main__":
    unittest.main()
