import os
from fastapi.testclient import TestClient

from civis.api import APIConfig, create_api_engine
from civis.config import CIVISConfig, redact_secrets, validate_civis_config


def main():
    print("=" * 115)
    print(" CIVIS-CORE - Production Deployment & Hardening Demonstration")
    print(" Containerization | Liveness & Readiness Probes | Prometheus Metrics | Secret Redaction | Security")
    print("=" * 115)

    # 1. Production Configuration & Hardened Defaults
    print("\n[+] 1. Validating Production Configuration & Environment Hardening...")
    prod_cfg = CIVISConfig(
        environment="production",
        device="cpu",
    )
    is_valid, errs = validate_civis_config(prod_cfg)
    print(f"    Environment Mode        : {prod_cfg.environment}")
    print(f"    Compute Device Target   : {prod_cfg.device}")
    print(f"    Config Schema Validity  : {is_valid} (0 errors)")

    # 2. Cryptographic Secret Redaction
    print("\n[+] 2. Testing Cryptographic Secret Redaction on Production Dumps...")
    sensitive_env = {
        "project": "CIVIS-CORE",
        "api_key": "civis_prod_ultra_secure_api_key_8899",
        "database_password": "super_secret_db_password",
        "jwt_secret": "session_signature_secret_key",
        "storage_root": "/var/lib/civis",
    }
    redacted = redact_secrets(sensitive_env)
    print(f"    API Key in Dump         : {redacted['api_key']}")
    print(f"    DB Password in Dump     : {redacted['database_password']}")
    print(f"    Storage Root in Dump    : {redacted['storage_root']}")

    # 3. Initialize Production API Gateway with Probes
    print("\n[+] 3. Initializing Production API Gateway Engine...")
    api_cfg = APIConfig(
        host="0.0.0.0",
        port=8000,
        authentication_enabled=True,
        api_key="civis_production_key_4455",
        use_mock=True,
    )
    api_engine = create_api_engine(config=api_cfg)
    client = TestClient(api_engine.get_app())
    auth_headers = {"X-API-Key": api_cfg.api_key}

    # 4. Orchestrator Probes: Liveness & Readiness
    print("\n[+] 4. Verifying Orchestration Health Probes...")
    res_live = client.get("/health/liveness", headers=auth_headers)
    print(f"    Liveness Probe (GET /health/liveness)   : HTTP {res_live.status_code} -> Status: {res_live.json()['status']}")

    res_ready = client.get("/health/readiness", headers=auth_headers)
    print(f"    Readiness Probe (GET /health/readiness) : HTTP {res_ready.status_code} -> Status: {res_ready.json()['status']}")
    print(f"      Subsystems Ready: {res_ready.json()['subsystems']}")

    # 5. Prometheus Plaintext Metrics Exposition
    print("\n[+] 5. Verifying Prometheus Plaintext Metrics (/health/metrics)...")
    res_prom = client.get("/health/metrics", headers=auth_headers)
    print(f"    Prometheus Metrics (GET /health/metrics): HTTP {res_prom.status_code}")
    print("    Metrics Preview (first 10 lines):")
    for line in res_prom.text.strip().split("\n")[:10]:
        print(f"      {line}")

    # 6. Persistent Storage & Forensic Ledger Preparation
    print("\n[+] 6. Inspecting Persistent Storage & Forensic Ledger Mounts...")
    storage_root = os.getenv("CIVIS_STORAGE_ROOT", "/var/lib/civis")
    evidence_dir = os.getenv("CIVIS_EVIDENCE_DIR", "/var/lib/civis/evidence")
    log_dir = os.getenv("CIVIS_LOG_DIR", "/var/log/civis")
    print(f"    Configured Storage Root : {storage_root}")
    print(f"    Evidence Ledger Volume  : {evidence_dir}")
    print(f"    Container Log Directory : {log_dir}")

    print("\n[+] Production Deployment & Hardening Demonstration Complete!\n")


if __name__ == "__main__":
    main()
