import time
import unittest
import numpy as np

from civis.ingestion.models import FramePacket
from civis.runtime import (
    BasePipelineStage,
    BoundedFrameQueue,
    CameraRuntimeConfig,
    DropPolicy,
    PipelineContext,
    PipelineRuntimeConfig,
    RuntimeEvent,
    RuntimeEventBus,
    RuntimeEventType,
    RuntimeState,
    SequentialPipeline,
    StageConfig,
    StageState,
    create_runtime_engine,
)


def _make_dummy_frame(camera_id: str, frame_num: int) -> FramePacket:
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    return FramePacket(
        camera_id=camera_id,
        frame_id=f"{camera_id}_{frame_num}",
        timestamp=time.time(),
        frame_number=frame_num,
        dimensions=(640, 480),
        frame=img,
    )


class TestRuntimeOrchestration(unittest.TestCase):

    def test_single_camera_pipeline_execution_sync(self):
        """Test executing the complete sequential pipeline on a single frame."""
        engine = create_runtime_engine(PipelineRuntimeConfig(
            use_mock=True,
            cameras=[CameraRuntimeConfig(camera_id="CAM_01", name="Front Camera", queue_size=5)],
        ))
        cam_runtime = engine.get_camera_runtime("CAM_01")
        self.assertIsNotNone(cam_runtime)

        packet = _make_dummy_frame("CAM_01", 1)
        ctx = cam_runtime.process_frame_sync(packet)

        # Assert that all stages produced outputs in PipelineContext
        self.assertIsNotNone(ctx.detection_result)
        self.assertIsNotNone(ctx.track_result)
        self.assertIsNotNone(ctx.identity_result)
        self.assertIsNotNone(ctx.behavior_result)
        self.assertIsNotNone(ctx.event_result)
        self.assertIsNotNone(ctx.risk_result)
        self.assertGreater(len(ctx.stage_timings_ms), 3)

    def test_stage_ordering_and_disabled_stages(self):
        """Test disabling a stage in config bypasses it cleanly."""
        cfg = PipelineRuntimeConfig(
            use_mock=True,
            cameras=[CameraRuntimeConfig(camera_id="CAM_01")],
            stages={"identity": StageConfig(name="identity", enabled=False)},
        )
        engine = create_runtime_engine(cfg)
        cam_runtime = engine.get_camera_runtime("CAM_01")
        packet = _make_dummy_frame("CAM_01", 1)
        ctx = cam_runtime.process_frame_sync(packet)

        # Detection and Tracking should run, Identity is bypassed
        self.assertIsNotNone(ctx.detection_result)
        self.assertIsNotNone(ctx.track_result)
        self.assertIsNone(ctx.identity_result)

    def test_bounded_queue_drop_oldest(self):
        """Test bounded queue with Drop Oldest policy for real-time video analytics."""
        dropped = []
        q = BoundedFrameQueue(
            maxsize=3,
            drop_policy=DropPolicy.DROP_OLDEST,
            on_drop_callback=lambda p, r: dropped.append(p.frame_number),
        )

        p1 = _make_dummy_frame("CAM_01", 1)
        p2 = _make_dummy_frame("CAM_01", 2)
        p3 = _make_dummy_frame("CAM_01", 3)
        p4 = _make_dummy_frame("CAM_01", 4)
        p5 = _make_dummy_frame("CAM_01", 5)

        q.put(p1)
        q.put(p2)
        q.put(p3)
        self.assertEqual(q.qsize(), 3)

        # Enqueue 4th and 5th frames: should evict 1 and 2
        q.put(p4)
        q.put(p5)
        self.assertEqual(q.qsize(), 3)
        self.assertEqual(dropped, [1, 2])

        # Dequeued frames should be [3, 4, 5]
        out1 = q.get()
        out2 = q.get()
        out3 = q.get()
        self.assertEqual([out1.frame_number, out2.frame_number, out3.frame_number], [3, 4, 5])

    def test_stage_failure_isolation_and_retry(self):
        """Test that an exception inside a pipeline stage is isolated and does not crash execution."""
        class FailingStage(BasePipelineStage):
            def __init__(self):
                super().__init__("failing_stage", enabled=True)
                self.calls = 0

            def process(self, context):
                self.calls += 1
                raise RuntimeError("Simulated stage error")

        fail_stage = FailingStage()
        pipeline = SequentialPipeline(
            stages=[fail_stage],
            stage_configs={"failing_stage": StageConfig(name="failing_stage", max_retries=1)},
        )

        ctx = PipelineContext(packet=_make_dummy_frame("CAM_01", 1), camera_id="CAM_01")
        ctx = pipeline.execute(ctx)

        self.assertEqual(fail_stage.calls, 2)  # Initial + 1 retry
        self.assertIn("failing_stage", ctx.errors)
        self.assertEqual(fail_stage.state, StageState.FAILED)

    def test_multi_camera_isolation_and_concurrency(self):
        """Test running multiple cameras and verifying that a failure on one camera does not affect the other."""
        engine = create_runtime_engine(PipelineRuntimeConfig(
            use_mock=True,
            cameras=[
                CameraRuntimeConfig(camera_id="CAM_01", name="Lobby", target_fps=30.0),
                CameraRuntimeConfig(camera_id="CAM_02", name="Corridor", target_fps=30.0),
            ],
        ))

        engine.start()
        time.sleep(0.3)

        health = engine.get_health()
        self.assertEqual(health.total_cameras, 2)
        self.assertEqual(health.state, RuntimeState.RUNNING)

        # Stop CAM_01 only
        cam1 = engine.get_camera_runtime("CAM_01")
        cam2 = engine.get_camera_runtime("CAM_02")
        cam1.stop()

        self.assertEqual(cam1.state, RuntimeState.STOPPED)
        self.assertEqual(cam2.state, RuntimeState.RUNNING)

        engine.stop()
        self.assertEqual(engine.state, RuntimeState.STOPPED)

    def test_pause_and_resume_lifecycle(self):
        """Test pause and resume lifecycle transitions."""
        engine = create_runtime_engine(PipelineRuntimeConfig(
            use_mock=True,
            cameras=[CameraRuntimeConfig(camera_id="CAM_01")],
        ))
        engine.start()
        time.sleep(0.2)

        engine.pause()
        self.assertEqual(engine.state, RuntimeState.PAUSED)
        self.assertEqual(engine.get_camera_runtime("CAM_01").state, RuntimeState.PAUSED)

        engine.resume()
        self.assertEqual(engine.state, RuntimeState.RUNNING)
        self.assertEqual(engine.get_camera_runtime("CAM_01").state, RuntimeState.RUNNING)

        engine.stop()

    def test_runtime_events_dispatching(self):
        """Test that operational runtime events are published and received by listeners."""
        bus = RuntimeEventBus()
        received_events = []

        bus.subscribe(RuntimeEventType.CAMERA_STARTED, lambda ev: received_events.append(ev.event_type))
        bus.subscribe(None, lambda ev: received_events.append(f"global_{ev.event_type.value}"))

        bus.publish(RuntimeEvent(event_type=RuntimeEventType.CAMERA_STARTED, camera_id="CAM_01"))

        self.assertIn(RuntimeEventType.CAMERA_STARTED, received_events)
        self.assertIn("global_camera_started", received_events)

    def test_health_and_metrics_calculation(self):
        """Test structured health and aggregate metrics aggregation."""
        engine = create_runtime_engine(PipelineRuntimeConfig(
            use_mock=True,
            cameras=[CameraRuntimeConfig(camera_id="CAM_01", queue_size=10)],
        ))
        cam = engine.get_camera_runtime("CAM_01")

        for i in range(5):
            cam.process_frame_sync(_make_dummy_frame("CAM_01", i + 1))

        health = engine.get_health()
        metrics = engine.get_metrics()

        self.assertEqual(health.total_frames_processed, 5)
        self.assertIn("CAM_01", metrics.per_camera_fps)
        self.assertIn("detection", metrics.per_stage_latency_ms)


if __name__ == "__main__":
    unittest.main()
