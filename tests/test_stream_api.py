"""
Unit & Integration Tests for Live Camera MJPEG Streaming, WebSocket Telemetry,
and Camera Controls in CIVIS-CORE.
"""

import asyncio
import unittest
from fastapi.testclient import TestClient

from civis.api.engine import APIEngine, MockAPIEngine
from civis.api.models import APIConfig
from civis.runtime.models import CameraRuntimeConfig, PipelineRuntimeConfig
from civis.runtime.engine import RuntimeEngine
from civis.runtime.overlay import encode_jpeg, render_pipeline_overlay
import numpy as np


class TestStreamAndLiveTelemetryAPI(unittest.TestCase):

    def setUp(self):
        self.api_engine = MockAPIEngine()
        self.client = TestClient(self.api_engine.get_app())

    def test_camera_list_endpoint(self):
        """Test listing camera statuses."""
        resp = self.client.get("/cameras")
        self.assertEqual(resp.status_code, 200)
        cams = resp.json()
        self.assertIsInstance(cams, list)
        self.assertGreaterEqual(len(cams), 1)
        self.assertEqual(cams[0]["camera_id"], "CAM_01")

    def test_camera_snapshot_endpoint(self):
        """Test retrieving a single annotated JPEG snapshot."""
        resp = self.client.get("/cameras/CAM_01/snapshot")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers.get("content-type"), "image/jpeg")
        # Check JPEG magic bytes (0xFF, 0xD8, 0xFF)
        self.assertTrue(resp.content.startswith(b"\xff\xd8\xff"))

    def test_camera_stream_endpoint_headers(self):
        """Test camera stream multipart MJPEG endpoint response header."""
        resp = self.client.get("/cameras/CAM_01/stream?max_frames=1")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("multipart/x-mixed-replace", resp.headers.get("content-type", ""))
        self.assertIn(b"--frame", resp.content)

    def test_camera_start_stop_pause_resume_lifecycle(self):
        """Test camera action endpoints start, stop, pause, resume."""
        # Pause
        r_pause = self.client.post("/cameras/CAM_01/pause")
        self.assertEqual(r_pause.status_code, 200)
        self.assertTrue(r_pause.json()["success"])

        # Resume
        r_resume = self.client.post("/cameras/CAM_01/resume")
        self.assertEqual(r_resume.status_code, 200)
        self.assertTrue(r_resume.json()["success"])

        # Stop
        r_stop = self.client.post("/cameras/CAM_01/stop")
        self.assertEqual(r_stop.status_code, 200)
        self.assertTrue(r_stop.json()["success"])

        # Start
        r_start = self.client.post("/cameras/CAM_01/start")
        self.assertEqual(r_start.status_code, 200)
        self.assertTrue(r_start.json()["success"])

    def test_nonexistent_camera_stream_returns_404(self):
        """Test requesting stream for non-existent camera returns 404."""
        resp = self.client.get("/cameras/NON_EXISTENT_CAM/stream")
        self.assertEqual(resp.status_code, 404)

    def test_jpeg_overlay_encoder(self):
        """Test overlay renderer and JPEG encoder."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        annotated = render_pipeline_overlay(frame, context=None, camera_id="CAM_TEST", fps=30.0)
        self.assertEqual(annotated.shape, (480, 640, 3))

        jpeg = encode_jpeg(annotated, quality=75)
        self.assertIsNotNone(jpeg)
        self.assertTrue(jpeg.startswith(b"\xff\xd8\xff"))

    def test_websocket_telemetry_broadcast(self):
        """Test WebSocket client connection and event broadcasting."""
        with self.client.websocket_connect("/ws/events") as ws:
            # Broadcast mock event
            test_msg = {
                "event_type": "pipeline_telemetry",
                "camera_id": "CAM_01",
                "timestamp": 1234567.0,
                "data": {"fps": 30.0, "tracks": []},
            }
            asyncio.run(self.api_engine.ws_manager.broadcast(test_msg))

            # Receive on client websocket
            received = ws.receive_json()
            self.assertEqual(received["event_type"], "pipeline_telemetry")
            self.assertEqual(received["camera_id"], "CAM_01")
            self.assertEqual(received["data"]["fps"], 30.0)


if __name__ == "__main__":
    unittest.main()
