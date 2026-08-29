import unittest
import numpy as np

from civis.detection.models import BoundingBox, Detection, DetectionResult
from civis.tracking.bytetrack_tracker import ByteTrackTracker
from civis.tracking.factory import create_tracker
from civis.tracking.mock_tracker import MockTracker
from civis.tracking.models import TrackState, TrackerConfig


class TestMultiObjectTracking(unittest.TestCase):
    def setUp(self):
        self.mock_tracker = MockTracker(TrackerConfig(track_buffer=3))
        self.byte_tracker = ByteTrackTracker(TrackerConfig(track_buffer=3, track_thresh=0.1))

    def _make_detection_res(self, cam_id: str, frame_num: int, boxes: list) -> DetectionResult:
        dets = []
        for i, box in enumerate(boxes):
            dets.append(
                Detection(
                    class_id=0,
                    class_name="person",
                    confidence=0.9,
                    bbox=BoundingBox(x1=box[0], y1=box[1], x2=box[2], y2=box[3]),
                )
            )
        return DetectionResult(
            camera_id=cam_id,
            frame_id=f"{cam_id}_{frame_num}",
            timestamp=1000.0 + frame_num,
            frame_number=frame_num,
            dimensions=(640, 480),
            detections=dets,
        )

    def test_persistent_track_ids(self):
        for tracker in [self.mock_tracker, self.byte_tracker]:
            tracker.reset()
            # Frame 1
            res1 = self._make_detection_res("cam_01", 1, [[10, 10, 50, 50]])
            t_res1 = tracker.update(res1)
            self.assertEqual(len(t_res1.tracks), 1)
            tid = t_res1.tracks[0].track_id

            # Frame 2 (moving box)
            res2 = self._make_detection_res("cam_01", 2, [[12, 12, 52, 52]])
            t_res2 = tracker.update(res2)
            self.assertEqual(len(t_res2.tracks), 1)
            self.assertEqual(t_res2.tracks[0].track_id, tid)

    def test_track_lifecycle_states(self):
        tracker = MockTracker(TrackerConfig(track_buffer=2))

        # Frame 1: NEW
        res1 = self._make_detection_res("cam_life", 1, [[10, 10, 50, 50]])
        tr1 = tracker.update(res1)
        self.assertEqual(tr1.tracks[0].state, TrackState.NEW)

        # Frame 2: TRACKED
        res2 = self._make_detection_res("cam_life", 2, [[12, 12, 52, 52]])
        tr2 = tracker.update(res2)
        self.assertEqual(tr2.tracks[0].state, TrackState.TRACKED)

        # Frame 3: Object missed -> LOST
        res3 = self._make_detection_res("cam_life", 3, [])
        tr3 = tracker.update(res3)
        self.assertEqual(len(tr3.tracks), 1)
        self.assertEqual(tr3.tracks[0].state, TrackState.LOST)

        # Frame 4 & 5: Missed exceeds buffer (2) -> REMOVED
        res4 = self._make_detection_res("cam_life", 4, [])
        tr4 = tracker.update(res4)

        res5 = self._make_detection_res("cam_life", 5, [])
        tr5 = tracker.update(res5)
        self.assertEqual(len(tr5.tracks), 0)

    def test_multi_camera_isolation(self):
        for tracker in [self.mock_tracker, self.byte_tracker]:
            tracker.reset()

            # Cam 1 Detection
            res_cam1 = self._make_detection_res("cam_north", 1, [[10, 10, 50, 50]])
            tr_cam1 = tracker.update(res_cam1)
            cam1_tid = tr_cam1.tracks[0].track_id
            self.assertEqual(tr_cam1.camera_id, "cam_north")

            # Cam 2 Detection
            res_cam2 = self._make_detection_res("cam_south", 1, [[10, 10, 50, 50]])
            tr_cam2 = tracker.update(res_cam2)
            cam2_tid = tr_cam2.tracks[0].track_id
            self.assertEqual(tr_cam2.camera_id, "cam_south")

            # Both cameras start their track sequence independently
            self.assertIsNotNone(cam1_tid)
            self.assertIsNotNone(cam2_tid)

    def test_tracker_factory(self):
        cfg = TrackerConfig(use_mock=True)
        tr = create_tracker(cfg)
        self.assertIsInstance(tr, MockTracker)


if __name__ == "__main__":
    unittest.main()
