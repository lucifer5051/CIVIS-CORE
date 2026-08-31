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


def generate_demo_video(file_path: str, num_frames: int = 30, fps: int = 10) -> None:
    """Generate a synthetic security video with a stationary entity inside a restricted zone."""
    width, height = 640, 480
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(file_path, fourcc, fps, (width, height))
    for i in range(num_frames):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:] = (30, 30, 30)

        # Restricted Vault Zone
        cv2.rectangle(frame, (50, 50), (350, 400), (40, 40, 160), 2)
        cv2.putText(frame, "RESTRICTED VAULT", (60, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (80, 80, 220), 2)

        # Stationary target dwelling inside restricted zone
        cv2.rectangle(frame, (100, 120), (220, 350), (0, 200, 100), -1)

        # Moving bystander outside zone
        x = 380 + (i % 15) * 10
        cv2.rectangle(frame, (x, 180), (x + 80, 340), (200, 100, 0), -1)

        cv2.putText(frame, f"Frame {i+1}/{num_frames}", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)
        writer.write(frame)
    writer.release()


def main():
    print("=" * 115)
    print(" CIVIS-CORE End-to-End Intelligence Pipeline:")
    print(" Ingestion -> Detection -> Tracking -> Identity -> Behavior -> Event Intelligence -> Risk Assessment")
    print("=" * 115)

    with tempfile.TemporaryDirectory() as tmp:
        video_path = os.path.join(tmp, "risk_demo.mp4")
        print("[+] Generating synthetic high-risk surveillance video ...")
        generate_demo_video(video_path, num_frames=30, fps=10)

        # 1. Ingestion
        manager = StreamManager()
        manager.add_camera(CameraConfig(
            camera_id="CAM_VAULT_01",
            name="Vault Surveillance Camera",
            source_type=SourceType.FILE,
            source=video_path,
            loop_file=False,
            fps_limit=10.0,
        ))

        # 2. Detection, 3. Tracking, 4. Identity
        detector = create_detector(DetectorConfig(use_mock=True))
        tracker = create_tracker(TrackerConfig(use_mock=True))
        identity_engine = create_identity_engine(IdentityConfig(use_mock=True))

        # 5. Behavior Analysis
        vault_zone = PolygonZone(
            zone_id="RESTRICTED_VAULT",
            name="Restricted Vault Zone",
            polygon=[Point2D(50, 50), Point2D(350, 50), Point2D(350, 400), Point2D(50, 400)],
        )
        behavior_engine = create_behavior_engine(BehaviorConfig(
            use_mock=True,
            dwell_threshold_seconds=1.0,
            event_cooldown_seconds=2.0,
            zones=[vault_zone],
        ))

        # 6. Event Intelligence
        rule_vault_loitering = EventRule(
            rule_id="RULE_VAULT_LOITER",
            name="Vault Loitering Event",
            description="Subject is loitering inside the restricted vault zone.",
            logic_operator=LogicOperator.AND,
            conditions=[
                Condition(condition_type="BEHAVIOR_TYPE", target_value="loitering", operator="=="),
                Condition(condition_type="DWELL_TIME", target_value=0.5, operator=">="),
            ],
            temporal_window_seconds=30.0,
            cooldown_seconds=2.0,
            confidence_aggregation=ConfidenceAggregation.AVERAGE,
            min_confidence=0.4,
        )
        ei_engine = create_event_intelligence_engine(EventIntelligenceConfig(
            use_mock=True,
            rules=[rule_vault_loitering],
            temporal_window_seconds=60.0,
            expiry_timeout_seconds=10.0,
        ))

        # 7. Risk Assessment Engine
        rule_vault_intrusion_risk = RiskRule(
            rule_id="RISK_VAULT_INTRUSION",
            name="Vault Intrusion Threat",
            category=ThreatCategory.SECURITY_INTRUSION,
            priority=10,
            base_severity_score=50.0,
            required_events=["RULE_VAULT_LOITER"],
            context_multipliers=[
                ContextMultiplier(
                    condition_type="ZONE_RESTRICTED",
                    target_value="RESTRICTED_VAULT",
                    multiplier=1.35,
                    description="Subject inside high-security vault zone",
                ),
                ContextMultiplier(
                    condition_type="UNKNOWN_IDENTITY",
                    target_value=True,
                    multiplier=1.2,
                    description="Subject has unrecognized biometric identity",
                ),
            ],
            escalation_rate_per_sec=3.0,
            max_escalated_score=98.0,
            de_escalation_half_life_sec=4.0,
            cooldown_seconds=5.0,
            min_confidence=0.3,
            weight=1.0,
        )
        risk_engine = create_risk_engine(RiskEngineConfig(
            use_mock=True,
            rules=[rule_vault_intrusion_risk],
            alert_score_delta_threshold=12.0,
            alert_cooldown_seconds=6.0,
            min_alert_severity=RiskSeverity.LOW,
        ))

        print("[+] Starting pipeline and processing camera stream...\n")
        manager.start_all()
        time.sleep(0.3)

        header = f"{'FRAME':<6} | {'TRACKS':<6} | {'CORRELATED EVENTS':<25} | {'SEVERITY':<10} | {'SCORE':<7} | {'CONF':<6} | {'ALERTS'}"
        print(header)
        print("-" * 115)

        total_frames = 0
        total_alerts = 0

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

                ei_names = ", ".join(e.name for e in ei.events) if ei.events else "-"
                
                max_assessment = max(risk.assessments, key=lambda a: a.severity_score) if risk.assessments else None
                sev_str = max_assessment.severity.value.upper() if max_assessment else "INFO"
                score_str = f"{max_assessment.severity_score:.1f}" if max_assessment else "0.0"
                conf_str = f"{max_assessment.confidence * 100:.0f}%" if max_assessment else "-"

                alert_strs = []
                for alt in risk.alerts:
                    alert_strs.append(f"[{alt.headline}]")
                    total_alerts += 1

                print(
                    f"{packet.frame_number:<6} | "
                    f"{len(trk.tracks):<6} | "
                    f"{ei_names:<25} | "
                    f"{sev_str:<10} | "
                    f"{score_str:<7} | "
                    f"{conf_str:<6} | "
                    f"{', '.join(alert_strs) if alert_strs else '-'}"
                )

                for alt in risk.alerts:
                    print(f"\n  [!] >>> ACTIONABLE RISK ALERT DISPATCHED <<<")
                    print(f"  Headline: {alt.headline}")
                    print(f"  Narrative Explanation:\n{chr(10).join('    | ' + l for l in alt.explanation.split(chr(10)))}\n")

        finally:
            manager.stop_all()

        print("-" * 115)
        print(f"\n[+] Pipeline Run Complete. Total Frames: {total_frames}, Actionable Risk Alerts: {total_alerts}.\n")


if __name__ == "__main__":
    main()
