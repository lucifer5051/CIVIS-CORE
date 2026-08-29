import unittest
import numpy as np

from civis.behavior.engine import MockBehaviorEngine
from civis.behavior.factory import create_behavior_engine
from civis.behavior.models import (
    BehaviorConfig,
    BehaviorState,
    LineTripwire,
    Point2D,
    PolygonZone,
)
from civis.behavior.zones import line_intersects, point_in_polygon
from civis.detection.models import BoundingBox
from civis.tracking.models import TrackState, TrackedObject, TrackResult


class TestBehaviorAnalysisModule(unittest.TestCase):
    def setUp(self):
        self.zone1 = PolygonZone(
            zone_id="ZONE_RESTRICTED",
            name="Restricted Area",
            polygon=[Point2D(0, 0), Point2D(200, 0), Point2D(200, 200), Point2D(0, 200)],
        )
        self.tripwire1 = LineTripwire(
            tripwire_id="LINE_GATE",
            name="Gate Entrance Line",
            p1=Point2D(100, 0),
            p2=Point2D(100, 200),
        )
        self.config = BehaviorConfig(
            use_mock=True,
            dwell_threshold_seconds=2.0,
            stationary_speed_threshold_px_sec=5.0,
            proximity_threshold_pixels=50.0,
            event_cooldown_seconds=3.0,
            zones=[self.zone1],
            tripwires=[self.tripwire1],
        )
        self.engine = MockBehaviorEngine(self.config)

    def _make_track_res(self, cam_id: str, frame_num: int, tracks: list, timestamp: float) -> TrackResult:
        t_objs = []
        for tid, cls_name, (x1, y1, x2, y2) in tracks:
            t_objs.append(
                TrackedObject(
                    track_id=tid,
                    class_id=0 if cls_name == "person" else 2,
                    class_name=cls_name,
                    confidence=0.9,
                    bbox=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2),
                    state=TrackState.TRACKED,
                )
            )
        return TrackResult(
            camera_id=cam_id,
            frame_id=f"{cam_id}_{frame_num}",
            timestamp=timestamp,
            frame_number=frame_num,
            dimensions=(640, 480),
            tracks=t_objs,
            active_track_ids=[t[0] for t in tracks],
        )

    def test_point_in_polygon_and_line_intersects(self):
        poly = [Point2D(0, 0), Point2D(100, 0), Point2D(100, 100), Point2D(0, 100)]
        self.assertTrue(point_in_polygon(Point2D(50, 50), poly))
        self.assertFalse(point_in_polygon(Point2D(150, 50), poly))

        self.assertTrue(
            line_intersects(
                Point2D(50, 50),
                Point2D(150, 50),
                Point2D(100, 0),
                Point2D(100, 100),
            )
        )

    def test_loitering_and_dwell_detection(self):
        # Frame 1 (t=1.0s): Stationary track at (50, 50)
        tr1 = self._make_track_res("cam_01", 1, [(1, "person", (30, 10, 70, 90))], timestamp=1.0)
        res1 = self.engine.process(tr1)
        self.assertEqual(res1.observations[0].state, BehaviorState.STATIONARY)

        # Frame 2 (t=2.5s): Still stationary (> 2.0s dwell threshold) -> LOITERING
        tr2 = self._make_track_res("cam_01", 2, [(1, "person", (30, 10, 70, 90))], timestamp=3.5)
        res2 = self.engine.process(tr2)
        self.assertEqual(res2.observations[0].state, BehaviorState.LOITERING)
        self.assertGreater(len(res2.events), 0)
        self.assertEqual(res2.events[0].event_type, "LOITERING_DETECTED")

    def test_proximity_by_class(self):
        # Two tracks within 30px distance (dist threshold=50px)
        tr = self._make_track_res(
            "cam_01",
            1,
            [
                (1, "person", (10, 10, 50, 90)),
                (2, "person", (30, 10, 70, 90)),
            ],
            timestamp=1.0,
        )
        res = self.engine.process(tr)
        self.assertIn(2, res.observations[0].proximity_track_ids)
        self.assertIn(1, res.observations[1].proximity_track_ids)

    def test_event_cooldown_deduplication(self):
        # Event emitted at t=1.0s
        tr1 = self._make_track_res("cam_01", 1, [(1, "person", (30, 10, 70, 90))], timestamp=1.0)
        self.engine.process(tr1)

        # Event trigger at t=3.5s (dwell threshold met) -> emits event
        tr2 = self._make_track_res("cam_01", 2, [(1, "person", (30, 10, 70, 90))], timestamp=3.5)
        res2 = self.engine.process(tr2)
        loiter_events_count1 = sum(1 for e in res2.events if e.event_type == "LOITERING_DETECTED")
        self.assertEqual(loiter_events_count1, 1)

        # Event trigger at t=4.0s (within 3.0s cooldown window) -> deduplicated/suppressed
        tr3 = self._make_track_res("cam_01", 3, [(1, "person", (30, 10, 70, 90))], timestamp=4.0)
        res3 = self.engine.process(tr3)
        loiter_events_count2 = sum(1 for e in res3.events if e.event_type == "LOITERING_DETECTED")
        self.assertEqual(loiter_events_count2, 0)

    def test_behavior_factory(self):
        cfg = BehaviorConfig(use_mock=True)
        engine = create_behavior_engine(cfg)
        self.assertIsInstance(engine, MockBehaviorEngine)


if __name__ == "__main__":
    unittest.main()
