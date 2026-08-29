import os
import tempfile
import time
import cv2
import numpy as np

from civis.behavior import (
    BehaviorConfig,
    LineTripwire,
    Point2D,
    PolygonZone,
    create_behavior_engine,
)
from civis.detection import DetectorConfig, create_detector
from civis.event_intelligence import (
    Condition,
    EventIntelligenceConfig,
    EventRule,
    LogicOperator,
    ConfidenceAggregation,
    create_event_intelligence_engine,
)
from civis.identity import IdentityConfig, create_identity_engine
from civis.ingestion import CameraConfig, CameraStatus, SourceType, StreamManager
from civis.tracking import TrackerConfig, create_tracker


def generate_demo_video(file_path: str, num_frames: int = 30, fps: int = 10) -> None:
    """Generate a synthetic demo video with two objects: one stationary, one moving."""
    width, height = 640, 480
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(file_path, fourcc, fps, (width, height))
    for i in range(num_frames):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:] = (30, 30, 30)
        # ROI zone boundary
        cv2.rectangle(frame, (80, 80), (320, 360), (40, 40, 120), 2)
        cv2.putText(frame, "ZONE A", (90, 105), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (80, 80, 200), 2)
        # Stationary object inside zone
        cv2.rectangle(frame, (130, 150), (210, 330), (0, 220, 80), -1)
        # Moving object crossing from left to right
        x = 50 + i * 18
        cv2.rectangle(frame, (x, 180), (x + 70, 350), (220, 80, 0), -1)
        cv2.putText(frame, f"Frame {i+1}/{num_frames}", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)
        writer.write(frame)
    writer.release()


def main():
    print("=" * 90)
    print(" CIVIS-CORE - End-to-End Pipeline: Ingestion -> Detection -> Tracking -> Identity -> Behavior -> Event Intelligence")
    print("=" * 90)

    with tempfile.TemporaryDirectory() as tmp:
        video_path = os.path.join(tmp, "event_intel_demo.mp4")
        print("[+] Generating synthetic demo video ...")
        generate_demo_video(video_path, num_frames=25, fps=10)

        # --- Pipeline Setup ---
        manager = StreamManager()
        manager.add_camera(CameraConfig(
            camera_id="CAM_01",
            name="Demo Camera",
            source_type=SourceType.FILE,
            source=video_path,
            loop_file=False,
            fps_limit=10.0,
        ))

        detector = create_detector(DetectorConfig(use_mock=True))
        tracker = create_tracker(TrackerConfig(use_mock=True))
        identity_engine = create_identity_engine(IdentityConfig(use_mock=True))

        # Behavior engine — Zone A + dwell threshold set low for demo
        zone_a = PolygonZone(
            zone_id="ZONE_A",
            name="Monitored Area A",
            polygon=[Point2D(80, 80), Point2D(320, 80), Point2D(320, 360), Point2D(80, 360)],
        )
        behavior_engine = create_behavior_engine(BehaviorConfig(
            use_mock=True,
            dwell_threshold_seconds=1.0,
            event_cooldown_seconds=3.0,
            zones=[zone_a],
        ))

        # Event Intelligence — two configurable data-driven rules
        rule_loitering = EventRule(
            rule_id="RULE_LOITERING",
            name="Prolonged Stationary Presence",
            description="Track has been dwelling for an extended period.",
            logic_operator=LogicOperator.AND,
            conditions=[
                Condition(condition_type="BEHAVIOR_TYPE", target_value="loitering", operator="=="),
                Condition(condition_type="DWELL_TIME", target_value=1.0, operator=">="),
            ],
            temporal_window_seconds=30.0,
            cooldown_seconds=3.0,
            confidence_aggregation=ConfidenceAggregation.AVERAGE,
            min_confidence=0.5,
        )
        rule_zone_loitering = EventRule(
            rule_id="RULE_ZONE_LOITER",
            name="Zone A Dwell Detected",
            description="Track is loitering inside Zone A.",
            logic_operator=LogicOperator.AND,
            conditions=[
                Condition(condition_type="BEHAVIOR_TYPE", target_value="loitering", operator="=="),
                Condition(condition_type="ZONE_ID", target_value="ZONE_A", operator="=="),
            ],
            temporal_window_seconds=30.0,
            cooldown_seconds=3.0,
            confidence_aggregation=ConfidenceAggregation.MIN,
            min_confidence=0.5,
        )

        ei_engine = create_event_intelligence_engine(EventIntelligenceConfig(
            use_mock=True,
            rules=[rule_loitering, rule_zone_loitering],
            temporal_window_seconds=60.0,
            expiry_timeout_seconds=10.0,
        ))

        print("[+] Pipeline started. Running frames...\n")
        manager.start_all()
        time.sleep(0.3)

        header = f"{'FRAME':<6} | {'TRACKS':<7} | {'BEHAVIOR EVENTS':<30} | {'CORRELATED EVENTS'}"
        print(header)
        print("-" * 90)

        total_frames = 0
        total_corr_events = 0

        try:
            while True:
                packet = manager.read_frame("CAM_01", timeout=0.2)
                if packet is None:
                    if manager.get_status("CAM_01") in (CameraStatus.DISCONNECTED, CameraStatus.STOPPED):
                        break
                    continue

                total_frames += 1
                det = detector.detect(packet)
                track = tracker.update(det)
                ident = identity_engine.process(packet, track)
                beh = behavior_engine.process(track, ident)
                ei = ei_engine.process(beh, ident, track)

                beh_ev_str = ", ".join(e.event_type for e in beh.events) if beh.events else "—"
                ei_ev_strs = []
                for evt in ei.events:
                    ei_ev_strs.append(f"[{evt.name}] conf={evt.overall_confidence:.2f}")
                    total_corr_events += 1

                print(
                    f"{beh.frame_number:<6} | "
                    f"{len(track.tracks):<7} | "
                    f"{beh_ev_str:<30} | "
                    f"{', '.join(ei_ev_strs) if ei_ev_strs else '—'}"
                )

                # Print explanation for any new correlated events
                for evt in ei.events:
                    print(f"\n  [EXPLANATION]:\n{chr(10).join('     ' + l for l in evt.explanation.split(chr(10)))}\n")

        finally:
            manager.stop_all()

        print("-" * 90)
        print(f"\nDone. Pipeline complete - {total_frames} frames, {total_corr_events} correlated events emitted.\n")


if __name__ == "__main__":
    main()
