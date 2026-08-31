import os
import tempfile
import time
import cv2
import numpy as np

from civis.behavior import (
    BehaviorConfig,
    Point2D,
    PolygonZone,
    create_behavior_engine,
)
from civis.detection import DetectorConfig, create_detector
from civis.event_intelligence import (
    Condition,
    ConfidenceAggregation,
    EventIntelligenceConfig,
    EventRule,
    LogicOperator,
    create_event_intelligence_engine,
)
from civis.evidence import (
    CustodyAction,
    EvidenceEngineConfig,
    ForensicPackager,
    create_evidence_engine,
)
from civis.identity import IdentityConfig, create_identity_engine
from civis.ingestion import CameraConfig, CameraStatus, SourceType, StreamManager
from civis.risk import (
    ContextMultiplier,
    RiskEngineConfig,
    RiskRule,
    RiskSeverity,
    ThreatCategory,
    create_risk_engine,
)
from civis.tracking import TrackerConfig, create_tracker


def generate_demo_video(file_path: str, num_frames: int = 20, fps: int = 10) -> None:
    width, height = 640, 480
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(file_path, fourcc, fps, (width, height))
    for i in range(num_frames):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:] = (30, 30, 30)

        # Restricted Vault Zone
        cv2.rectangle(frame, (50, 50), (350, 400), (40, 40, 160), 2)
        cv2.putText(frame, "SECURE VAULT", (60, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (80, 80, 220), 2)

        # Stationary target inside vault
        cv2.rectangle(frame, (100, 120), (220, 350), (0, 200, 100), -1)

        cv2.putText(frame, f"Frame {i+1}/{num_frames}", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)
        writer.write(frame)
    writer.release()


def main():
    print("=" * 115)
    print(" CIVIS-CORE - End-to-End Forensic Evidence & Audit Subsystem Demo")
    print(" Detection -> Track -> Identity -> Behavior -> Event -> Risk -> Immutable Evidence Ledger")
    print("=" * 115)

    with tempfile.TemporaryDirectory() as tmp:
        video_path = os.path.join(tmp, "evidence_demo.mp4")
        print("[+] Synthesizing video for evidence capture ...")
        generate_demo_video(video_path, num_frames=15, fps=10)

        # 1. Ingestion
        manager = StreamManager()
        manager.add_camera(CameraConfig(
            camera_id="CAM_VAULT_01",
            name="Secure Vault",
            source_type=SourceType.FILE,
            source=video_path,
            loop_file=False,
            fps_limit=10.0,
        ))

        # 2. Pipeline Subsystems
        detector = create_detector(DetectorConfig(use_mock=True))
        tracker = create_tracker(TrackerConfig(use_mock=True))
        identity_engine = create_identity_engine(IdentityConfig(use_mock=True))

        vault_zone = PolygonZone(
            zone_id="RESTRICTED_VAULT",
            name="Vault Zone",
            polygon=[Point2D(50, 50), Point2D(350, 50), Point2D(350, 400), Point2D(50, 400)],
        )
        behavior_engine = create_behavior_engine(BehaviorConfig(
            use_mock=True,
            dwell_threshold_seconds=1.0,
            zones=[vault_zone],
        ))

        ei_engine = create_event_intelligence_engine(EventIntelligenceConfig(
            use_mock=True,
            rules=[
                EventRule(
                    rule_id="RULE_VAULT_LOITER",
                    name="Vault Loitering",
                    description="Loitering inside restricted vault",
                    logic_operator=LogicOperator.AND,
                    conditions=[
                        Condition(condition_type="BEHAVIOR_TYPE", target_value="loitering", operator="=="),
                        Condition(condition_type="DWELL_TIME", target_value=1.0, operator=">="),
                    ],
                    temporal_window_seconds=30.0,
                    cooldown_seconds=2.0,
                    min_confidence=0.4,
                )
            ],
        ))

        risk_engine = create_risk_engine(RiskEngineConfig(
            use_mock=True,
            rules=[
                RiskRule(
                    rule_id="RISK_VAULT_BREACH",
                    name="Vault Intrusion Hazard",
                    category=ThreatCategory.SECURITY_INTRUSION,
                    base_severity_score=60.0,
                    required_events=["RULE_VAULT_LOITER"],
                    context_multipliers=[
                        ContextMultiplier(
                            condition_type="ZONE_RESTRICTED",
                            target_value="RESTRICTED_VAULT",
                            multiplier=1.3,
                            description="Inside high-security vault",
                        )
                    ],
                    min_confidence=0.4,
                )
            ],
            min_alert_severity=RiskSeverity.MEDIUM,
        ))

        # 3. Evidence Engine
        evidence_dir = os.path.join(tmp, "evidence_store")
        evidence_engine = create_evidence_engine(EvidenceEngineConfig(
            storage_directory=evidence_dir,
            enable_hash_chain=True,
            auto_seal_alerts=True,
            use_mock=True,
        ))

        print("[+] Starting pipeline stream and logging cryptographic evidence...\n")
        manager.start_all()
        time.sleep(0.3)

        header = f"{'FRAME':<6} | {'STAGE RECORDS INGESTED':<25} | {'RISK LEVEL':<10} | {'LEDGER SEQ':<10} | {'RECORD SHA-256 (PREFIX)'}"
        print(header)
        print("-" * 115)

        total_frames = 0
        total_records = 0

        try:
            while True:
                packet = manager.read_frame("CAM_VAULT_01", timeout=0.2)
                if packet is None:
                    if manager.get_status("CAM_VAULT_01") in (CameraStatus.DISCONNECTED, CameraStatus.STOPPED):
                        break
                    continue

                total_frames += 1
                det = detector.detect(packet)
                trk = tracker.update(det)
                ident = identity_engine.process(packet, trk)
                beh = behavior_engine.process(trk, ident)
                ei = ei_engine.process(beh, ident, trk)
                risk = risk_engine.assess(ei, beh, ident, trk)

                records = evidence_engine.ingest_pipeline_frame(
                    detection_result=det,
                    track_result=trk,
                    identity_result=ident,
                    behavior_result=beh,
                    event_result=ei,
                    risk_result=risk,
                )
                total_records += len(records)

                max_ass = max(risk.assessments, key=lambda a: a.severity_score) if risk.assessments else None
                sev_str = max_ass.severity.value.upper() if max_ass else "INFO"
                last_rec = records[-1] if records else None
                hash_preview = f"{last_rec.record_hash[:16]}..." if last_rec else "-"
                seq_str = str(last_rec.sequence_number) if last_rec else "-"

                print(
                    f"{packet.frame_number:<6} | "
                    f"{f'+{len(records)} evidence entries':<25} | "
                    f"{sev_str:<10} | "
                    f"{seq_str:<10} | "
                    f"{hash_preview}"
                )

        finally:
            manager.stop_all()

        print("-" * 115)

        # 4. Cryptographic Ledger Verification
        print("\n[+] 1. Running Cryptographic Hash-Chain Verification on Ledger...")
        is_valid, err = evidence_engine.verify_ledger_integrity()
        print(f"    Ledger Integrity Status: {'[OK] VERIFIED UNTAMPERED' if is_valid else '[FAIL] ' + err}")

        # 5. Timeline Reconstruction
        print("\n[+] 2. Synthesizing Chronological Incident Investigation Timeline...")
        timeline = evidence_engine.build_timeline(camera_id="CAM_VAULT_01", min_severity="medium")
        print(f"    Timeline ID: {timeline.timeline_id}")
        print(f"    Total Filtered Evidence Records: {timeline.total_records}")
        print(f"    Timeline Summary Narrative:\n{chr(10).join('      | ' + l for l in timeline.summary.split(chr(10)))}\n")

        # 6. Forensic Package Export & BagIt Checksum Manifest
        export_pkg_dir = os.path.join(tmp, "forensic_export_package")
        print(f"[+] 3. Exporting RFC 8493 BagIt Forensic Package to '{export_pkg_dir}' ...")
        manifest = evidence_engine.export_forensic_package(timeline, export_pkg_dir)
        print(f"    Package ID: {manifest.package_id}")
        print(f"    Total Payload Files: {manifest.total_files}")
        for rel_path, csum in manifest.file_checksums.items():
            print(f"      * {rel_path} -> SHA256:{csum[:16]}...")

        # 7. Forensic Package Independent Verification
        print("\n[+] 4. Verifying Exported Package Checksums against Manifest...")
        pkg_valid, pkg_err = ForensicPackager.verify_package(export_pkg_dir)
        print(f"    Forensic Package Verification: {'[OK] 100% CHECKSUM MATCH' if pkg_valid else '[FAIL] ' + pkg_err}")
        print("\n[+] Evidence & Forensic Demo Complete!\n")


if __name__ == "__main__":
    main()
