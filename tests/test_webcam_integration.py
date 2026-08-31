"""
Unit and Integration Tests for Real Laptop Webcam Ingestion & Live Pipeline
Tests webcam configuration, error handling, mock fallback, overlays, and pipeline execution.
"""

import os
import tempfile
import unittest
import numpy as np

from civis.detection.models import BoundingBox, Detection, DetectionMode, DetectionResult
from civis.ingestion.models import CameraConfig, CameraStatus, FramePacket, SourceType
from civis.ingestion.opencv_source import OpenCVVideoSource
from civis.runtime.pipeline import PipelineContext
from demo_webcam import (
    build_live_pipeline,
    draw_pipeline_overlays,
    make_mock_webcam_packet,
    run_webcam_demo,
)


class TestWebcamIntegration(unittest.TestCase):

    def test_camera_config_resolution_and_validation(self):
        """Test CameraConfig supports width, height, and numeric webcam index."""
        cfg = CameraConfig(
            camera_id="WEBCAM_TEST",
            source_type=SourceType.WEBCAM,
            source=0,
            fps_limit=30.0,
            width=1280,
            height=720,
        )
        self.assertEqual(cfg.camera_id, "WEBCAM_TEST")
        self.assertEqual(cfg.source, 0)
        self.assertEqual(cfg.width, 1280)
        self.assertEqual(cfg.height, 720)
        self.assertTrue(cfg.drop_outdated_frames)

    def test_invalid_webcam_source_graceful_handling(self):
        """Test that attempting to open an invalid camera index handles errors gracefully without crashing."""
        cfg = CameraConfig(
            camera_id="INVALID_CAM",
            source_type=SourceType.WEBCAM,
            source=999,  # Non-existent index
            max_reconnect_attempts=1,
            reconnect_interval=0.5,
        )
        source = OpenCVVideoSource(cfg)
        source.start()

        # Reading from invalid source should return None and not hang
        pkt = source.read(timeout=0.5)
        self.assertIsNone(pkt)

        source.stop()
        self.assertIn(source.get_status(), (CameraStatus.STOPPED, CameraStatus.ERROR, CameraStatus.RECONNECTING))

    def test_synthetic_mock_webcam_packet_generation(self):
        """Test synthetic mock packet generation for environments without hardware cameras."""
        pkt = make_mock_webcam_packet("MOCK_CAM", 1, 640, 480)
        self.assertEqual(pkt.camera_id, "MOCK_CAM")
        self.assertEqual(pkt.dimensions, (640, 480))
        self.assertEqual(pkt.frame.shape, (480, 640, 3))
        self.assertGreater(pkt.timestamp, 0.0)

    def test_overlay_rendering_with_complete_context(self):
        """Test draw_pipeline_overlays draws HUD, banners, and detection boxes on raw frame."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        pkt = FramePacket.create("CAM_TEST", 1, frame)
        ctx = PipelineContext(packet=pkt, camera_id="CAM_TEST")

        # Fake detections
        from civis.tracking.models import TrackResult, TrackedObject, TrackState
        trk = TrackedObject(
            track_id=1,
            class_id=0,
            class_name="person",
            confidence=0.88,
            bbox=BoundingBox(x1=100, y1=100, x2=200, y2=400),
            state=TrackState.TRACKED,
        )
        ctx.track_result = TrackResult(
            camera_id="CAM_TEST",
            frame_id="f1",
            timestamp=pkt.timestamp,
            frame_number=1,
            dimensions=(640, 480),
            tracks=[trk],
        )
        ctx.stage_timings_ms = {"detection": 1.2, "tracking": 0.4, "identity": 0.8}

        annotated = draw_pipeline_overlays(
            frame=frame,
            context=ctx,
            fps_capture=29.8,
            fps_processed=30.2,
            latency_ms=2.4,
            camera_id="CAM_TEST",
            privacy_mode=True,
        )

        self.assertEqual(annotated.shape, (480, 640, 3))
        # Verify frame was modified (non-zero pixels where overlays were drawn)
        self.assertGreater(np.count_nonzero(annotated), 0)

    def test_build_live_pipeline_instantiation(self):
        """Test build_live_pipeline creates functional SequentialPipeline across all stages."""
        pipeline, obs, evd = build_live_pipeline(
            camera_id="CAM_01",
            sahi_mode=DetectionMode.AUTO,
            confidence_threshold=0.4,
            face_backend="heuristic",
            use_mock=True,
            save_evidence=True,
        )
        stage_names = [s.name for s in pipeline.stages]
        self.assertIn("detection", stage_names)
        self.assertIn("tracking", stage_names)
        self.assertIn("identity", stage_names)
        self.assertIn("reid", stage_names)
        self.assertIn("behavior", stage_names)
        self.assertIn("event_intelligence", stage_names)
        self.assertIn("risk", stage_names)
        self.assertIn("evidence", stage_names)
        self.assertIsNotNone(evd)
        self.assertIsNotNone(obs)

    def test_webcam_demo_headless_mock_run(self):
        """Test run_webcam_demo executes end-to-end in headless mode with evidence export."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            ret = run_webcam_demo(
                camera_source="invalid_source_to_test_fallback",
                camera_id="TEST_RUN",
                target_width=640,
                target_height=480,
                target_fps=30.0,
                frame_interval=1,
                sahi_mode="auto",
                conf_threshold=0.35,
                face_detector_backend="heuristic",
                use_mock=True,
                save_evidence=True,
                export_dir=tmp_dir,
                no_display=True,
                max_frames=10,
            )
            self.assertEqual(ret, 0)

            # Verify exported evidence package
            exported_folders = os.listdir(tmp_dir)
            self.assertGreater(len(exported_folders), 0)


if __name__ == "__main__":
    unittest.main()
