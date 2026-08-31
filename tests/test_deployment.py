import os
import unittest
from fastapi.testclient import TestClient

from civis.api import create_api_engine
from civis.config import CIVISConfig, ConfigLoader, redact_secrets, validate_civis_config


class TestProductionDeployment(unittest.TestCase):

    def setUp(self):
        self.api_engine = create_api_engine(use_mock=True)
        self.client = TestClient(self.api_engine.get_app())

    def test_liveness_probe(self):
        """Test container orchestrator liveness probe."""
        res = self.client.get("/health/liveness")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "alive")
        self.assertIn("timestamp", data)

    def test_readiness_probe(self):
        """Test container orchestrator readiness probe."""
        res = self.client.get("/health/readiness")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "ready")
        self.assertTrue(data["subsystems"]["runtime"])
        self.assertTrue(data["subsystems"]["observability"])
        self.assertTrue(data["subsystems"]["config"])

    def test_prometheus_metrics_exposition(self):
        """Test Prometheus plaintext /health/metrics endpoint."""
        res = self.client.get("/health/metrics")
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/plain", res.headers.get("content-type", ""))
        text = res.text
        self.assertIn("civis_up 1", text)
        self.assertIn("civis_active_cameras", text)
        self.assertIn("civis_frames_processed_total", text)

    def test_production_config_validation(self):
        """Test production configuration composition and validation."""
        cfg = CIVISConfig(environment="production", device="cpu")
        is_valid, errors = validate_civis_config(cfg)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)

    def test_production_secret_redaction(self):
        """Verify sensitive credentials are never stored plaintext."""
        payload = {
            "civis_api_key": "super_secret_token_val",
            "ssl_private_key": "private_rsa_key_data",
            "db_password": "my_db_password",
            "safe_param": 100,
        }
        sanitized = redact_secrets(payload)
        self.assertEqual(sanitized["civis_api_key"], "******")
        self.assertEqual(sanitized["ssl_private_key"], "******")
        self.assertEqual(sanitized["db_password"], "******")
        self.assertEqual(sanitized["safe_param"], 100)

    def test_deployment_artifacts_exist(self):
        """Verify Dockerfile, .dockerignore, and docker-compose.yml are present."""
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        dockerfile = os.path.join(root_dir, "Dockerfile")
        dockerignore = os.path.join(root_dir, ".dockerignore")
        compose = os.path.join(root_dir, "docker-compose.yml")

        self.assertTrue(os.path.isfile(dockerfile))
        self.assertTrue(os.path.isfile(dockerignore))
        self.assertTrue(os.path.isfile(compose))

        with open(dockerfile, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("USER civis:civis", content)
            self.assertIn("HEALTHCHECK", content)


if __name__ == "__main__":
    unittest.main()
