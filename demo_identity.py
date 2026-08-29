import os
import tempfile
import time
import cv2
import numpy as np

from civis.detection import DetectorConfig, create_detector
from civis.identity import IdentityConfig, create_identity_engine
from civis.ingestion import CameraConfig, CameraStatus, SourceType, StreamManager
from civis.tracking import TrackerConfig, create_tracker


def generate_person_video(file_path: str, num_frames: int = 20, fps: int = 30) -> None:
    width, height = 640, 480
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(file_path, fourcc, fps, (width, height))

    for i in range(num_frames):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:] = (50, 50, 50)

        # Draw a synthetic person box (Track 1)
        cv2.rectangle(frame, (100, 80), (220, 400), (0, 255, 0), -1)
        # Draw face region inside person box
        cv2.rectangle(frame, (130, 100), (190, 170), (255, 200, 150), -1)
        cv2.putText(frame, "Alice", (135, 140), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

        cv2.putText(frame, f"Frame {i+1}", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        writer.write(frame)

    writer.release()


def main():
    print("=" * 80)
    print(" CIVIS-CORE : End-to-End Pipeline (Ingestion -> Detection -> Tracking -> Identity)")
    print("=" * 80)

    with tempfile.TemporaryDirectory() as temp_dir:
        video_path = os.path.join(temp_dir, "identity_test.mp4")
        print("[+] Generating sample video with person & face targets...")
        generate_person_video(video_path, num_frames=15, fps=30)

        # Step 1: Ingestion StreamManager
        manager = StreamManager()
        cam_cfg = CameraConfig(
            camera_id="CAM_LOBBY_01",
            name="Main Lobby Camera",
            source_type=SourceType.FILE,
            source=video_path,
            loop_file=False,
            fps_limit=30.0,
        )
        manager.add_camera(cam_cfg)

        # Step 2: Detection Engine
        det_cfg = DetectorConfig(use_mock=True)
        detector = create_detector(det_cfg)

        # Step 3: Tracking Engine
        track_cfg = TrackerConfig(use_mock=True)
        tracker = create_tracker(track_cfg)

        # Step 4: Identity Association Engine
        id_cfg = IdentityConfig(use_mock=True, min_observations=2, similarity_threshold=0.5)
        identity_engine = create_identity_engine(id_cfg)

        print("[+] Starting pipeline execution...")
        manager.start_all()
        time.sleep(0.3)

        print("\n" + "-" * 80)
        print(f"{'FRAME':<7} | {'CAM_ID':<14} | {'TRACK_ID':<9} | {'IDENTITY_ID':<16} | {'NAME':<15} | {'STATE':<11} | {'CONF':<6}")
        print("-" * 80)

        total_frames = 0
        try:
            while True:
                packet = manager.read_frame("CAM_LOBBY_01", timeout=0.2)
                if packet is None:
                    status = manager.get_status("CAM_LOBBY_01")
                    if status in (CameraStatus.DISCONNECTED, CameraStatus.STOPPED):
                        break
                    continue

                total_frames += 1

                # Pipeline Step 1: Ingestion FramePacket -> Detector -> DetectionResult
                det_result = detector.detect(packet)

                # Pipeline Step 2: DetectionResult -> Tracker -> TrackResult
                track_result = tracker.update(det_result)

                # Pipeline Step 3: TrackResult + FramePacket -> IdentityEngine -> IdentityResult
                id_result = identity_engine.process(packet, track_result)

                for assoc in id_result.identities:
                    print(
                        f"{id_result.frame_number:<7} | "
                        f"{id_result.camera_id:<14} | "
                        f"{assoc.track_id:<9} | "
                        f"{assoc.identity_id:<16} | "
                        f"{assoc.name:<15} | "
                        f"{assoc.state.value:<11} | "
                        f"{assoc.association_confidence:.2f}"
                    )

        finally:
            manager.stop_all()

        print("=" * 80)
        print(f" CIVIS-CORE Identity Pipeline Test Completed ({total_frames} frames processed)!")
        print("=" * 80)


if __name__ == "__main__":
    main()
