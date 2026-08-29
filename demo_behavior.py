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
from civis.identity import IdentityConfig, create_identity_engine
from civis.ingestion import CameraConfig, CameraStatus, SourceType, StreamManager
from civis.tracking import TrackerConfig, create_tracker


def generate_surveillance_video(file_path: str, num_frames: int = 25, fps: int = 30) -> None:
    width, height = 640, 480
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(file_path, fourcc, fps, (width, height))

    for i in range(num_frames):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:] = (40, 40, 40)

        # Draw ROI Zone (Restricted Area)
        cv2.rectangle(frame, (100, 100), (350, 350), (50, 50, 150), 2)
        cv2.putText(frame, "Restricted Zone A", (110, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 100, 255), 2)

        # Draw Tripwire Line
        cv2.line(frame, (400, 50), (400, 400), (0, 255, 255), 2)
        cv2.putText(frame, "Tripwire 1", (410, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        # Person 1: Dwelling inside Restricted Zone A
        cv2.rectangle(frame, (150, 150), (230, 320), (0, 255, 0), -1)

        # Person 2: Moving from left to right across Tripwire 1
        x2 = 300 + i * 10
        cv2.rectangle(frame, (x2, 200), (x2 + 70, 360), (255, 0, 0), -1)

        cv2.putText(frame, f"Frame {i+1}", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        writer.write(frame)

    writer.release()


def main():
    print("=" * 85)
    print(" CIVIS-CORE : End-to-End Pipeline (Ingestion -> Detection -> Tracking -> Identity -> Behavior)")
    print("=" * 85)

    with tempfile.TemporaryDirectory() as temp_dir:
        video_path = os.path.join(temp_dir, "behavior_test.mp4")
        print("[+] Generating synthetic video with ROI zone and tripwire crossing targets...")
        generate_surveillance_video(video_path, num_frames=20, fps=30)

        # Pipeline Setup
        manager = StreamManager()
        cam_cfg = CameraConfig(
            camera_id="CAM_PERIMETER_01",
            name="Perimeter Gate Camera",
            source_type=SourceType.FILE,
            source=video_path,
            loop_file=False,
            fps_limit=30.0,
        )
        manager.add_camera(cam_cfg)

        detector = create_detector(DetectorConfig(use_mock=True))
        tracker = create_tracker(TrackerConfig(use_mock=True))
        identity_engine = create_identity_engine(IdentityConfig(use_mock=True))

        # Behavior Setup with ROI Zone & Tripwire
        zone_a = PolygonZone(
            zone_id="ZONE_RESTRICTED_A",
            name="Restricted Area A",
            polygon=[Point2D(100, 100), Point2D(350, 100), Point2D(350, 350), Point2D(100, 350)],
        )
        line_1 = LineTripwire(
            tripwire_id="LINE_GATE_1",
            name="Gate Entrance Line",
            p1=Point2D(400, 50),
            p2=Point2D(400, 400),
        )

        behavior_cfg = BehaviorConfig(
            use_mock=True,
            dwell_threshold_seconds=1.0,
            event_cooldown_seconds=3.0,
            zones=[zone_a],
            tripwires=[line_1],
        )
        behavior_engine = create_behavior_engine(behavior_cfg)

        print("[+] Starting pipeline execution...")
        manager.start_all()
        time.sleep(0.3)

        print("\n" + "-" * 85)
        print(f"{'FRAME':<6} | {'CAM_ID':<17} | {'TRACK_ID':<9} | {'BEHAVIOR STATE':<15} | {'SPEED':<7} | {'DWELL':<6} | {'EVENTS DETECTED'}")
        print("-" * 85)

        total_frames = 0
        try:
            while True:
                packet = manager.read_frame("CAM_PERIMETER_01", timeout=0.2)
                if packet is None:
                    status = manager.get_status("CAM_PERIMETER_01")
                    if status in (CameraStatus.DISCONNECTED, CameraStatus.STOPPED):
                        break
                    continue

                total_frames += 1

                # Ingestion -> Detection -> Tracking -> Identity -> Behavior
                det_result = detector.detect(packet)
                track_result = tracker.update(det_result)
                id_result = identity_engine.process(packet, track_result)
                beh_result = behavior_engine.process(track_result, id_result)

                events_str = ", ".join([f"[{e.event_type} (Zone:{e.zone_id})]" for e in beh_result.events])

                for obs in beh_result.observations:
                    print(
                        f"{beh_result.frame_number:<6} | "
                        f"{beh_result.camera_id:<17} | "
                        f"{obs.track_id:<9} | "
                        f"{obs.state.value:<15} | "
                        f"{obs.speed_px_sec:5.1f} | "
                        f"{obs.dwell_time_sec:4.1f}s | "
                        f"{events_str if events_str else 'None'}"
                    )

        finally:
            manager.stop_all()

        print("=" * 85)
        print(f" CIVIS-CORE Behavior Analysis Pipeline Test Completed ({total_frames} frames processed)!")
        print("=" * 85)


if __name__ == "__main__":
    main()
