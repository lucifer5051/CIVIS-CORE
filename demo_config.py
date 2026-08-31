import json
import os
import tempfile

from civis.config import (
    ConfigLoader,
    PolicyRule,
    create_config_engine,
)


def main():
    print("=" * 115)
    print(" CIVIS-CORE - Centralized Configuration & Policy Management Subsystem Demo")
    print(" Schema Validation | Layered Overrides | Safe Runtime Updates | Snapshots & Diffs | Policies")
    print("=" * 115)

    # 1. Simulate Layered Configuration & Environment Overrides
    print("\n[+] 1. Simulating Layered Configuration (File + Environment Overrides)...")
    os.environ["CIVIS_PROJECT_NAME"] = "CIVIS-ENTERPRISE-CORE"
    os.environ["CIVIS_DETECTION__CONF_THRESHOLD"] = "0.72"
    os.environ["CIVIS_OBSERVABILITY__MIN_ACCEPTABLE_FPS"] = "25.0"

    try:
        config_engine = create_config_engine(use_env=True)
        active_cfg = config_engine.get()

        print(f"    Project Name             : {active_cfg.project_name} (Overridden from ENV)")
        print(f"    Detection Confidence Thresh: {active_cfg.detection.conf_threshold} (Overridden from ENV)")
        print(f"    Observability Min FPS    : {active_cfg.observability.min_acceptable_fps} (Overridden from ENV)")
        print(f"    Active Compute Device    : {active_cfg.device}")

        # 2. Subsystem Registry Query
        print("\n[+] 2. Querying Subsystem Configuration Sections via Registry...")
        for section in ["detection", "tracking", "reid", "risk", "evidence", "observability"]:
            sec_obj = config_engine.get_section(section)
            print(f"    * [{section.upper():<14}] -> {sec_obj.__class__.__name__} (use_mock={getattr(sec_obj, 'use_mock', True)})")

        # 3. Policy Management & Evaluation
        print("\n[+] 3. Registering and Evaluating Operational Security Policies...")
        config_engine.policies.add_policy(PolicyRule(
            policy_id="POL_HIGH_SECURITY_VAULT",
            name="High Security Vault Protocol",
            priority=1,
            conditions={"zone_classification": "restricted_vault", "threat_level": "high"},
            parameters={"auto_seal_evidence": True, "alert_immediate_dispatch": True},
        ))
        config_engine.policies.add_policy(PolicyRule(
            policy_id="POL_NIGHT_MODE",
            name="Night Shift Operating Mode",
            priority=10,
            conditions={"time_of_day": "night"},
            parameters={"detection_sensitivity_boost": 0.15},
        ))

        print(f"    Registered Policies ({len(config_engine.policies.list_policies())}):")
        for p in config_engine.policies.list_policies():
            print(f"      - [Priority {p.priority:>2}] {p.policy_id}: {p.name}")

        context = {"zone_classification": "restricted_vault", "threat_level": "high"}
        matched, params = config_engine.policies.evaluate_policy("POL_HIGH_SECURITY_VAULT", context)
        print(f"    Policy Evaluation for context {context}:")
        print(f"      Matched: {matched} | Applied Parameters: {params}")

        # 4. Snapshot Baseline
        print("\n[+] 4. Capturing Baseline Configuration Snapshot (Snapshot #1)...")
        snap1 = config_engine.create_snapshot()
        print(f"    Snapshot ID : {snap1.snapshot_id}")
        print(f"    SHA-256     : {snap1.checksum}")

        # 5. Safe Runtime Update
        print("\n[+] 5. Applying Safe Operational Runtime Update (Raising detection threshold to 0.85)...")
        update_res = config_engine.update({"detection": {"conf_threshold": 0.85}})
        print(f"    Update Applied: {update_res.success} | Requires Restart: {update_res.requires_restart}")
        print(f"    New Detection Confidence: {config_engine.get().detection.conf_threshold}")

        # 6. Rejected Invalid Update & Automatic Rollback
        print("\n[+] 6. Testing Rejected Invalid Configuration Update (Invalid Compute Device)...")
        bad_update = config_engine.update({"device": "quantum_neural_asic_invalid"})
        print(f"    Update Accepted : {bad_update.success} (Cleanly Rejected)")
        print(f"    Validation Error: {bad_update.validation_errors[0]}")
        print(f"    Rollback Check  : Active device remains '{config_engine.get().device}'")

        # 7. Snapshot Diff
        print("\n[+] 7. Computing Cryptographic Snapshot Diff (Snapshot #1 vs Snapshot #2)...")
        snap2 = config_engine.create_snapshot()
        diff_res = config_engine.diff(snap1, snap2)
        print(f"    Has Modifications: {diff_res.has_changes}")
        for path, (old_val, new_val) in diff_res.changed.items():
            print(f"      * {path} : {old_val} -> {new_val}")

        # 8. Sanitized JSON Export
        print("\n[+] 8. Exporting Sanitized Configuration Snapshot to JSON...")
        with tempfile.TemporaryDirectory() as tmp_dir:
            export_path = os.path.join(tmp_dir, "civis_config_snapshot.json")
            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(snap2.config_data, f, indent=2, default=str)

            print(f"    Exported to: {export_path}")
            print("    Sanitized JSON Preview (first 20 lines):")
            with open(export_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                for l in lines[:20]:
                    print("      " + l.rstrip())
            print("      ... [truncated for display]")

    finally:
        os.environ.pop("CIVIS_PROJECT_NAME", None)
        os.environ.pop("CIVIS_DETECTION__CONFIDENCE_THRESHOLD", None)
        os.environ.pop("CIVIS_OBSERVABILITY__MIN_ACCEPTABLE_FPS", None)

    print("\n[+] Centralized Configuration & Policy Management Demo Complete!\n")


if __name__ == "__main__":
    main()
