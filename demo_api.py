import json
from fastapi.testclient import TestClient

from civis.api import APIConfig, create_api_engine
from civis.evidence.models import EvidenceRecord


def main():
    print("=" * 115)
    print(" CIVIS-CORE - External Integration & API Gateway Subsystem Demo")
    print(" FastAPI REST API | Constant-time API-Key Auth | WebSocket Event Streaming | OpenAPI Docs")
    print("=" * 115)

    # 1. Initialize API Engine in Mock Mode with Auth Enabled
    print("\n[+] 1. Initializing CIVIS API Gateway (Mock Mode + API-Key Security)...")
    api_cfg = APIConfig(
        host="127.0.0.1",
        port=8000,
        authentication_enabled=True,
        api_key="civis_demo_secret_key_7788",
        use_mock=True,
    )
    api_engine = create_api_engine(config=api_cfg)
    client = TestClient(api_engine.get_app())
    auth_headers = {"X-API-Key": api_cfg.api_key}

    # 2. OpenAPI & Documentation Endpoints
    print("\n[+] 2. Checking OpenAPI Schema & Swagger Documentation...")
    res_docs = client.get("/docs")
    res_openapi = client.get("/openapi.json")
    print(f"    GET /docs         : HTTP {res_docs.status_code} (Interactive Swagger UI Ready)")
    print(f"    GET /openapi.json : HTTP {res_openapi.status_code} ({len(res_openapi.json().get('paths', {}))} API endpoints documented)")

    # 3. Authentication Enforcement
    print("\n[+] 3. Demonstrating Constant-Time API-Key Authentication...")
    res_unauth = client.get("/health")
    print(f"    GET /health (No Auth Header)    : HTTP {res_unauth.status_code} -> {res_unauth.json()['detail']}")
    res_bad = client.get("/health", headers={"X-API-Key": "invalid_key"})
    print(f"    GET /health (Invalid Key)       : HTTP {res_bad.status_code} -> {res_bad.json()['detail']}")
    res_auth = client.get("/health", headers=auth_headers)
    print(f"    GET /health (Valid Auth Key)    : HTTP {res_auth.status_code} -> Status: {res_auth.json()['status']}")

    # 4. System Health & Diagnostics
    print("\n[+] 4. Querying Detailed System Health & Diagnostics...")
    res_det = client.get("/health/detailed", headers=auth_headers)
    print(f"    System Status Snapshot: {json.dumps(res_det.json(), indent=2)[:300]} ... [truncated]")

    # 5. Multi-Camera Stream Controls
    print("\n[+] 5. Inspecting Camera Streams & Lifecycle Controls...")
    res_cams = client.get("/cameras", headers=auth_headers)
    cameras = res_cams.json()
    for cam in cameras:
        print(f"    * Camera [{cam['camera_id']}]: Running={cam['is_running']} | FPS={cam['current_fps']} | Frames={cam['processed_frames']}")

    # 6. Analytics Query Endpoints
    print("\n[+] 6. Querying Analytics Endpoints (Detections, Tracks, Identities, Re-ID)...")
    res_det = client.get("/detections?camera_id=CAM_01", headers=auth_headers)
    print(f"    GET /detections (CAM_01) : {len(res_det.json())} detections found")
    res_tr = client.get("/tracks?track_id=1", headers=auth_headers)
    print(f"    GET /tracks (Track 1)    : {len(res_tr.json())} active tracks found")
    res_id = client.get("/identities", headers=auth_headers)
    print(f"    GET /identities          : {res_id.json()[0]['name']} (Confidence: {res_id.json()[0]['confidence']})")
    res_reid = client.get("/reid/entities", headers=auth_headers)
    print(f"    GET /reid/entities       : Global ID {res_reid.json()[0]['global_id']} (Sim: {res_reid.json()[0]['similarity']})")

    # 7. Explainable Risks & Alerts
    print("\n[+] 7. Querying Explainable Risk Assessments & Alerts...")
    res_rsk = client.get("/risks", headers=auth_headers)
    print(f"    GET /risks               : Severity={res_rsk.json()[0]['severity']} | Score={res_rsk.json()[0]['overall_score']} | {res_rsk.json()[0]['summary']}")
    res_alt = client.get("/risks/alerts", headers=auth_headers)
    print(f"    GET /risks/alerts        : Alert ID={res_alt.json()[0]['alert_id']} | Explanation: {res_alt.json()[0]['explanation']}")

    # 8. Forensic Evidence & Cryptographic Verification
    print("\n[+] 8. Querying Forensic Evidence & Cryptographic Hash Verification...")
    ev_eng = api_engine.dependencies.get_evidence_engine()
    from civis.evidence.models import EvidenceStage
    rec = ev_eng._ledger.append(
        evidence_id="ev_demo_5544",
        stage=EvidenceStage.RISK_ASSESSMENT,
        camera_id="CAM_01",
        frame_id="CAM_01_0001",
        frame_number=1,
        timestamp=100.0,
        payload={"risk_score": 0.88, "type": "intrusion"},
    )
    res_ev_ver = client.get(f"/evidence/{rec.evidence_id}/verify", headers=auth_headers)
    print(f"    GET /evidence/{rec.evidence_id}/verify : {res_ev_ver.json()['message']}")

    # 9. Configuration Management & Validation API
    print("\n[+] 9. Configuration Query, Snapshot & Validation API...")
    res_snap = client.get("/config/snapshot", headers=auth_headers)
    print(f"    GET /config/snapshot     : Snapshot ID={res_snap.json()['snapshot_id']} | Checksum={res_snap.json()['checksum']}")
    res_val = client.post("/config/validate", json={"detection": {"conf_threshold": 0.85}}, headers=auth_headers)
    print(f"    POST /config/validate    : Valid={res_val.json()['valid']}")

    # 10. WebSocket Live Stream Connection
    print("\n[+] 10. Subscribing to Live WebSocket Event Stream (/ws/events)...")
    with client.websocket_connect("/ws/events") as websocket:
        websocket.send_text("client_heartbeat_ping")
        print("    Connected to /ws/events successfully. Ready for real-time streaming.")

    print("\n[+] External Integration & API Gateway Demo Complete!\n")


if __name__ == "__main__":
    main()
