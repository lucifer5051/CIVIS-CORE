import json
from fastapi.testclient import TestClient

from civis.api import create_api_engine
from civis.dashboard import DashboardConfig
from civis.evidence.models import EvidenceStage


def main():
    print("=" * 115)
    print(" CIVIS-CORE - Web Dashboard & Operator Console Integration Demo")
    print(" React Operator Console | Live Feed Grid | Risk Feeds | WebSocket Stream | Evidence Verification")
    print("=" * 115)

    # 1. Initialize Dashboard Configuration & Backend Client
    print("\n[+] 1. Initializing Dashboard Integration (Mock API Mode)...")
    dash_cfg = DashboardConfig(
        host="127.0.0.1",
        port=3000,
        api_base_url="http://127.0.0.1:8000",
        ws_url="ws://127.0.0.1:8000/ws/events",
        theme="dark",
        max_timeline_events=100,
    )
    print(f"    Dashboard UI Port       : {dash_cfg.port}")
    print(f"    Backend API Target      : {dash_cfg.api_base_url}")
    print(f"    WebSocket Stream Target : {dash_cfg.ws_url}")
    print(f"    Max Buffered Events     : {dash_cfg.max_timeline_events}")

    api_engine = create_api_engine(use_mock=True)
    client = TestClient(api_engine.get_app())

    # 2. System Health & Diagnostics Bar
    print("\n[+] 2. Operator Console -> Fetching Top Bar System Health & Diagnostics...")
    res_health = client.get("/health")
    health_data = res_health.json()
    print(f"    System Health Status    : [{health_data['status']}]")
    print(f"    Active Cameras Online   : {health_data['active_cameras']} / {health_data['total_cameras']}")
    print(f"    Pipeline Uptime         : {health_data['uptime_seconds']}s")

    # 3. Multi-Camera Feed Discovery
    print("\n[+] 3. Operator Console -> Discovering Configured Video Feeds for Camera Grid...")
    res_cams = client.get("/cameras")
    cams = res_cams.json()
    for cam in cams:
        print(f"    * Camera Tile [{cam['camera_id']:<8}] -> Running: {str(cam['is_running']):<5} | FPS: {cam['current_fps']:.1f} | Processed: {cam['processed_frames']}")

    # 4. Live Risk & Alert Panel Queries
    print("\n[+] 4. Operator Console -> Querying Active Security Risks & Alerts for Risk Panel...")
    res_risks = client.get("/risks")
    risks = res_risks.json()
    for r in risks:
        print(f"    * [SEVERITY: {r['severity'].upper():<8}] Score: {r['overall_score']:.2f} | Entity: {r['entity_key']} | {r['summary']}")

    res_alerts = client.get("/risks/alerts")
    alerts = res_alerts.json()
    for alt in alerts:
        print(f"    * Actionable Alert [{alt['alert_id']}] -> {alt['explanation']}")

    # 5. Entity Intelligence & Re-ID Inspection
    print("\n[+] 5. Operator Console -> Querying Cross-Camera Re-ID & Identity Modal Data...")
    res_reid = client.get("/reid/entities")
    for entity in res_reid.json():
        print(f"    * Global Entity [{entity['global_id']}] -> Camera: {entity['camera_id']} | Match Score: {entity['similarity']:.2f}")

    # 6. Cryptographic Evidence Verification
    print("\n[+] 6. Operator Console -> Testing Forensic Evidence Verification Action...")
    ev_eng = api_engine.dependencies.get_evidence_engine()
    rec = ev_eng._ledger.append(
        evidence_id="ev_dash_demo_990",
        stage=EvidenceStage.RISK_ASSESSMENT,
        camera_id="CAM_01",
        frame_id="CAM_01_0001",
        frame_number=1,
        timestamp=100.0,
        payload={"alert": "perimeter_breach", "score": 0.89},
    )
    res_ver = client.get(f"/evidence/{rec.evidence_id}/verify")
    print(f"    Verification Request for {rec.evidence_id}:")
    print(f"      Valid: {res_ver.json()['is_valid']} | Message: {res_ver.json()['message']}")

    # 7. Operator Runtime Pipeline Controls
    print("\n[+] 7. Operator Console -> Dispatching Runtime Orchestration Control Actions...")
    start_rt = client.post("/runtime/start")
    print(f"    POST /runtime/start     : {start_rt.json()['message']}")
    pause_cam = client.post("/cameras/CAM_01/pause")
    print(f"    POST /cameras/CAM_01/pause: {pause_cam.json()['message']}")
    resume_cam = client.post("/cameras/CAM_01/resume")
    print(f"    POST /cameras/CAM_01/resume: {resume_cam.json()['message']}")

    # 8. Live WebSocket Event Subscription
    print("\n[+] 8. Operator Console -> Subscribing to Real-Time Event Timeline (/ws/events)...")
    with client.websocket_connect("/ws/events") as websocket:
        websocket.send_text("console_operator_active")
        print("    Connected to WebSocket stream successfully. Event buffer active.")

    print("\n[+] Web Dashboard & Operator Console Integration Demo Complete!\n")


if __name__ == "__main__":
    main()
