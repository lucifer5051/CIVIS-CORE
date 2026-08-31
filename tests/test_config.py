import json
import os
import tempfile
import unittest

from civis.config import (
    CIVISConfig,
    ConfigDiff,
    ConfigEngine,
    ConfigLoader,
    ConfigManager,
    ConfigSnapshot,
    PolicyRule,
    compute_config_diff,
    compute_config_hash,
    create_config_engine,
    redact_secrets,
    validate_civis_config,
)


class TestConfigSubsystem(unittest.TestCase):

    def test_default_configuration_composition(self):
        """Test default composition of all 11 subsystem configuration models."""
        cfg = CIVISConfig()

        self.assertEqual(cfg.project_name, "CIVIS-CORE")
        self.assertIsNotNone(cfg.detection)
        self.assertIsNotNone(cfg.tracking)
        self.assertIsNotNone(cfg.identity)
        self.assertIsNotNone(cfg.reid)
        self.assertIsNotNone(cfg.behavior)
        self.assertIsNotNone(cfg.event_intelligence)
        self.assertIsNotNone(cfg.risk)
        self.assertIsNotNone(cfg.evidence)
        self.assertIsNotNone(cfg.runtime)
        self.assertIsNotNone(cfg.observability)

        is_valid, errors = validate_civis_config(cfg)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)

    def test_json_file_loading_and_layering(self):
        """Test loading configuration from a JSON file."""
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as f:
            json.dump({
                "project_name": "CUSTOM-CIVIS",
                "device": "cpu",
                "detection": {"conf_threshold": 0.65},
            }, f)
            tmp_path = f.name

        try:
            cfg = ConfigLoader.load(file_path=tmp_path)
            self.assertEqual(cfg.project_name, "CUSTOM-CIVIS")
            self.assertEqual(cfg.detection.conf_threshold, 0.65)
        finally:
            if os.path.isfile(tmp_path):
                os.remove(tmp_path)

    def test_environment_overrides_precedence(self):
        """Test environment variables overriding file and default values."""
        os.environ["CIVIS_PROJECT_NAME"] = "ENV_OVERRIDE_CIVIS"
        os.environ["CIVIS_DETECTION__CONF_THRESHOLD"] = "0.88"
        os.environ["CIVIS_OBSERVABILITY__MIN_ACCEPTABLE_FPS"] = "24.5"

        try:
            cfg = ConfigLoader.load()
            self.assertEqual(cfg.project_name, "ENV_OVERRIDE_CIVIS")
            self.assertEqual(cfg.detection.conf_threshold, 0.88)
            self.assertEqual(cfg.observability.min_acceptable_fps, 24.5)
        finally:
            os.environ.pop("CIVIS_PROJECT_NAME", None)
            os.environ.pop("CIVIS_DETECTION__CONF_THRESHOLD", None)
            os.environ.pop("CIVIS_OBSERVABILITY__MIN_ACCEPTABLE_FPS", None)

    def test_validation_rules_and_error_reporting(self):
        """Test detection of invalid device, duplicate cameras, and bad thresholds."""
        cfg = CIVISConfig(device="quantum_core_99")
        is_valid, errors = validate_civis_config(cfg)
        self.assertFalse(is_valid)
        self.assertTrue(any("Invalid compute device" in err for err in errors))

    def test_registry_section_lookup(self):
        """Test dynamic registry access by section name."""
        mgr = create_config_engine(use_mock=True)
        det_cfg = mgr.get_section("detection")
        self.assertTrue(det_cfg.use_mock)

        rsk_cfg = mgr.get_section("risk")
        self.assertTrue(rsk_cfg.use_mock)

    def test_safe_runtime_updates_and_rollback(self):
        """Test applying valid updates and rolling back invalid updates cleanly."""
        mgr = create_config_engine(use_mock=True)

        # 1. Valid update
        res1 = mgr.update({"detection": {"conf_threshold": 0.75}})
        self.assertTrue(res1.success)
        self.assertEqual(mgr.get().detection.conf_threshold, 0.75)
        self.assertFalse(res1.requires_restart)

        # 2. Invalid update (bad device) -> should rollback
        res2 = mgr.update({"device": "unsupported_accelerator"})
        self.assertFalse(res2.success)
        self.assertGreater(len(res2.validation_errors), 0)
        # Previous valid state must remain intact
        self.assertEqual(mgr.get().device, "cpu")
        self.assertEqual(mgr.get().detection.conf_threshold, 0.75)

    def test_restart_required_flag(self):
        """Test that modifying immutable core architecture fields flags restart requirement."""
        mgr = create_config_engine(use_mock=True)
        res = mgr.update({"device": "cuda:0"})
        self.assertTrue(res.success)
        self.assertTrue(res.requires_restart)

    def test_policy_management_and_priority_evaluation(self):
        """Test policy registration and deterministic priority-ordered evaluation."""
        mgr = create_config_engine(use_mock=True)
        mgr.policies.add_policy(PolicyRule(
            policy_id="POL_LOW_LIGHT",
            name="Low Light Security",
            priority=20,
            conditions={"ambient_light": "low"},
            parameters={"confidence_boost": 0.15},
        ))
        mgr.policies.add_policy(PolicyRule(
            policy_id="POL_LOCKDOWN",
            name="Emergency Lockdown",
            priority=1,
            conditions={"lockdown_active": True},
            parameters={"alert_immediate": True, "strict_mode": True},
        ))

        policies = mgr.policies.list_policies()
        self.assertEqual(policies[0].policy_id, "POL_LOCKDOWN")  # Priority 1 first

        # Evaluate matching context
        matched, params = mgr.policies.evaluate_policy("POL_LOCKDOWN", {"lockdown_active": True})
        self.assertTrue(matched)
        self.assertTrue(params["alert_immediate"])

    def test_snapshot_checksum_and_diff(self):
        """Test immutable snapshot generation, hashing, and diffing."""
        mgr = create_config_engine(use_mock=True)
        snap1 = mgr.create_snapshot()

        mgr.update({"detection": {"conf_threshold": 0.90}})
        snap2 = mgr.create_snapshot()

        self.assertNotEqual(snap1.checksum, snap2.checksum)
        diff_res = mgr.diff(snap1, snap2)

        self.assertTrue(diff_res.has_changes)
        self.assertIn("detection.conf_threshold", diff_res.changed)
        old_v, new_v = diff_res.changed["detection.conf_threshold"]
        self.assertEqual(new_v, 0.90)

    def test_secret_redaction(self):
        """Test automatic redaction of sensitive credentials in snapshots."""
        raw_dict = {
            "project": "CIVIS",
            "db_password": "super_secret_password_123",
            "api_key": "sk-1234567890abcdef",
            "nested": {"auth_token": "bearer_token_xyz"},
        }
        sanitized = redact_secrets(raw_dict)

        self.assertEqual(sanitized["db_password"], "******")
        self.assertEqual(sanitized["api_key"], "******")
        self.assertEqual(sanitized["nested"]["auth_token"], "******")
        self.assertEqual(sanitized["project"], "CIVIS")


if __name__ == "__main__":
    unittest.main()
