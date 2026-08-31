import json
import unittest
from fastapi.testclient import TestClient

from civis.api import create_api_engine
from civis.dashboard import DashboardConfig


class TestDashboardSubsystem(unittest.TestCase):

    def setUp(self):
        self.api_engine = create_api_engine(use_mock=True)
        self.client = TestClient(self.api_engine.get_app())

    def test_dashboard_config_defaults(self):
        """Test DashboardConfig initialization and defaults."""
        cfg = DashboardConfig()
        self.assertEqual(cfg.port, 3000)
        self.assertEqual(cfg.api_base_url, "http://127.0.0.1:8000")
        self.assertEqual(cfg.max_timeline_events, 100)
        self.assertEqual(cfg.theme, "dark")

    def test_dashboard_health_and_diagnostics_integration(self):
        """Test health retrieval for operator dashboard."""
        res_h = self.client.get("/health")
        self.assertEqual(res_h.status_code, 200)
        data = res_h.json()
        self.assertIn("status", data)
        self.assertIn("active_cameras", data)

        res_det = self.client.get("/health/detailed")
        self.assertEqual(res_det.status_code, 200)
        det_data = res_det.json()
        self.assertIn("runtime", det_data)
        self.assertIn("observability", det_data)

    def test_dashboard_camera_grid_data(self):
        """Test camera grid endpoint discovery."""
        res = self.client.get("/cameras")
        self.assertEqual(res.status_code, 200)
        cams = res.json()
        self.assertIsInstance(cams, list)
        self.assertGreaterEqual(len(cams), 1)
        self.assertEqual(cams[0]["camera_id"], "CAM_01")

    def test_dashboard_risk_and_alert_feed(self):
        """Test risk assessments and alerts retrieval for risk panel."""
        res_rsk = self.client.get("/risks")
        self.assertEqual(res_rsk.status_code, 200)
        risks = res_rsk.json()
        self.assertGreaterEqual(len(risks), 1)
        self.assertEqual(risks[0]["camera_id"], "CAM_01")
        self.assertIn("severity", risks[0])

        res_alt = self.client.get("/risks/alerts")
        self.assertEqual(res_alt.status_code, 200)
        alerts = res_alt.json()
        self.assertGreaterEqual(len(alerts), 1)

    def test_dashboard_evidence_verification_flow(self):
        """Test evidence ledger queries and SHA-256 verification."""
        ev_eng = self.api_engine.dependencies.get_evidence_engine()
        from civis.evidence.models import EvidenceStage
        rec = ev_eng._ledger.append(
            evidence_id="ev_dash_001",
            stage=EvidenceStage.DETECTION,
            camera_id="CAM_01",
            frame_id="CAM_01_001",
            frame_number=1,
            timestamp=100.0,
            payload={"source": "test"},
        )

        res_ev = self.client.get("/evidence")
        self.assertEqual(res_ev.status_code, 200)

        res_ver = self.client.get(f"/evidence/{rec.evidence_id}/verify")
        self.assertEqual(res_ver.status_code, 200)
        self.assertTrue(res_ver.json()["is_valid"])

    def test_dashboard_runtime_controls(self):
        """Test runtime pipeline start/stop and camera control actions."""
        self.assertEqual(self.client.post("/runtime/start").status_code, 200)
        self.assertEqual(self.client.post("/cameras/CAM_01/pause").status_code, 200)
        self.assertEqual(self.client.post("/cameras/CAM_01/resume").status_code, 200)
        self.assertEqual(self.client.post("/cameras/CAM_01/stop").status_code, 200)
        self.assertEqual(self.client.post("/cameras/CAM_01/start").status_code, 200)
        self.assertEqual(self.client.post("/runtime/stop").status_code, 200)

    def test_dashboard_websocket_event_streaming(self):
        """Test WebSocket client connectivity for live timeline streaming."""
        with self.client.websocket_connect("/ws/events") as websocket:
            websocket.send_text("ping")

    def test_bounded_event_ring_buffer_logic(self):
        """Test simulated client ring buffer capping to max_timeline_events."""
        buffer = []
        max_size = 5
        for i in range(10):
            buffer = [{"id": i}] + buffer
            buffer = buffer[:max_size]

        self.assertEqual(len(buffer), max_size)
        self.assertEqual(buffer[0]["id"], 9)
        self.assertEqual(buffer[-1]["id"], 5)


if __name__ == "__main__":
    unittest.main()
