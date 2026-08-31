import unittest
from fastapi.testclient import TestClient

from civis.api import APIConfig, create_api_engine
from civis.evidence.models import EvidenceRecord


class TestAPISubsystem(unittest.TestCase):

    def setUp(self):
        self.api_engine = create_api_engine(use_mock=True)
        self.client = TestClient(self.api_engine.get_app())

    def test_application_creation_and_openapi(self):
        """Test OpenAPI schema generation and docs endpoint."""
        res_docs = self.client.get("/docs")
        self.assertEqual(res_docs.status_code, 200)

        res_openapi = self.client.get("/openapi.json")
        self.assertEqual(res_openapi.status_code, 200)
        data = res_openapi.json()
        self.assertIn("openapi", data)
        self.assertEqual(data["info"]["title"], "CIVIS-CORE External Integration Gateway")

    def test_health_endpoints(self):
        """Test /health and /health/detailed endpoints."""
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("status", data)
        self.assertIn("uptime_seconds", data)

        res_det = self.client.get("/health/detailed")
        self.assertEqual(res_det.status_code, 200)
        self.assertIn("observability", res_det.json())

    def test_cameras_endpoints(self):
        """Test camera status and lifecycle control endpoints."""
        res = self.client.get("/cameras")
        self.assertEqual(res.status_code, 200)
        cams = res.json()
        self.assertGreaterEqual(len(cams), 1)

        cam_id = cams[0]["camera_id"]
        res_single = self.client.get(f"/cameras/{cam_id}")
        self.assertEqual(res_single.status_code, 200)
        self.assertEqual(res_single.json()["camera_id"], cam_id)

        # Test lifecycle actions
        self.assertEqual(self.client.post(f"/cameras/{cam_id}/pause").status_code, 200)
        self.assertEqual(self.client.post(f"/cameras/{cam_id}/resume").status_code, 200)
        self.assertEqual(self.client.post(f"/cameras/{cam_id}/stop").status_code, 200)
        self.assertEqual(self.client.post(f"/cameras/{cam_id}/start").status_code, 200)

    def test_analytics_endpoints_and_filtering(self):
        """Test analytics query endpoints with query parameter filters."""
        # Detections
        res_det = self.client.get("/detections?camera_id=CAM_01")
        self.assertEqual(res_det.status_code, 200)
        for d in res_det.json():
            self.assertEqual(d["camera_id"], "CAM_01")

        # Tracks
        res_tr = self.client.get("/tracks?track_id=1")
        self.assertEqual(res_tr.status_code, 200)
        self.assertGreaterEqual(len(res_tr.json()), 1)

        # Identities
        res_id = self.client.get("/identities?camera_id=CAM_01")
        self.assertEqual(res_id.status_code, 200)

        # Re-ID entities
        res_reid = self.client.get("/reid/entities")
        self.assertEqual(res_reid.status_code, 200)

        # Behavior & Correlated Events
        self.assertEqual(self.client.get("/behavior/events").status_code, 200)
        self.assertEqual(self.client.get("/events").status_code, 200)

        # Risks & Alerts
        self.assertEqual(self.client.get("/risks").status_code, 200)
        self.assertEqual(self.client.get("/risks/alerts").status_code, 200)

    def test_evidence_endpoints_and_verification(self):
        """Test forensic evidence retrieval and hash verification."""
        ev_eng = self.api_engine.dependencies.get_evidence_engine()
        from civis.evidence.models import EvidenceStage
        rec = ev_eng._ledger.append(
            evidence_id="ev_test_1001",
            stage=EvidenceStage.DETECTION,
            camera_id="CAM_01",
            frame_id="CAM_01_0001",
            frame_number=1,
            timestamp=100.0,
            payload={"test": "data"},
        )

        res = self.client.get("/evidence")
        self.assertEqual(res.status_code, 200)
        self.assertGreaterEqual(len(res.json()), 1)

        res_single = self.client.get(f"/evidence/{rec.evidence_id}")
        self.assertEqual(res_single.status_code, 200)
        self.assertEqual(res_single.json()["evidence_id"], rec.evidence_id)

        res_ver = self.client.get(f"/evidence/{rec.evidence_id}/verify")
        self.assertEqual(res_ver.status_code, 200)
        self.assertTrue(res_ver.json()["is_valid"])

    def test_runtime_endpoints(self):
        """Test runtime pipeline control and status endpoints."""
        res_stat = self.client.get("/runtime/status")
        self.assertEqual(res_stat.status_code, 200)

        res_start = self.client.post("/runtime/start")
        self.assertEqual(res_start.status_code, 200)
        self.assertEqual(res_start.json()["status"], "started")

        res_stop = self.client.post("/runtime/stop")
        self.assertEqual(res_stop.status_code, 200)
        self.assertEqual(res_stop.json()["status"], "stopped")

    def test_config_endpoints(self):
        """Test configuration query, snapshot, validation, and safe update."""
        res_cfg = self.client.get("/config")
        self.assertEqual(res_cfg.status_code, 200)

        res_snap = self.client.get("/config/snapshot")
        self.assertEqual(res_snap.status_code, 200)
        self.assertIn("checksum", res_snap.json())

        res_sec = self.client.get("/config/detection")
        self.assertEqual(res_sec.status_code, 200)

        # Validate valid payload
        res_val = self.client.post("/config/validate", json={"detection": {"conf_threshold": 0.75}})
        self.assertEqual(res_val.status_code, 200)
        self.assertTrue(res_val.json()["valid"])

        # Patch subsystem section
        res_patch = self.client.patch("/config/detection", json={"conf_threshold": 0.80})
        self.assertEqual(res_patch.status_code, 200)
        self.assertTrue(res_patch.json()["success"])

    def test_api_key_authentication_enforcement(self):
        """Test API key authentication enforcement and unauthorized rejections."""
        auth_cfg = APIConfig(
            use_mock=True,
            authentication_enabled=True,
            api_key="secret_civis_token_xyz",
        )
        auth_engine = create_api_engine(config=auth_cfg)
        auth_client = TestClient(auth_engine.get_app())

        # 1. Missing header -> 401
        res_unauth = auth_client.get("/health")
        self.assertEqual(res_unauth.status_code, 401)
        self.assertIn("Missing", res_unauth.json()["detail"])

        # 2. Invalid header -> 401
        res_bad = auth_client.get("/health", headers={"X-API-Key": "wrong_key"})
        self.assertEqual(res_bad.status_code, 401)

        # 3. Valid header -> 200
        res_ok = auth_client.get("/health", headers={"X-API-Key": "secret_civis_token_xyz"})
        self.assertEqual(res_ok.status_code, 200)

    def test_consistent_error_responses(self):
        """Test uniform JSON error payload format on missing resource."""
        res = self.client.get("/cameras/NON_EXISTENT_CAM_99")
        self.assertEqual(res.status_code, 404)
        err = res.json()
        self.assertIn("error", err)
        self.assertIn("detail", err)
        self.assertIn("timestamp", err)
        self.assertEqual(err["status_code"], 404)

    def test_websocket_streaming(self):
        """Test WebSocket client connection and message exchange."""
        with self.client.websocket_connect("/ws/events") as websocket:
            websocket.send_text("ping")
            # Connection remains open and responsive


if __name__ == "__main__":
    unittest.main()
