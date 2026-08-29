import os
import tempfile
import time
import cv2
import numpy as np

from civis.detection import DetectorConfig, create_detector
from civis.ingestion import CameraConfig, CameraStatus, SourceType, StreamManager
from civis.tracking import TrackerConfig, create_tracker


def generate_moving_object_video(file_path: str, num_frames: int = 25, fps: int = 30) -> None:
    width, height = 640, 480
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(file_path, fourcc, fps, (width, height))

    for i in range(num_frames):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:] = (40, 40, 40)

        # Moving object 1 (left to right)
        x1_1 = 50 + i * 15
        y1_1 = 100
        cv2.rectangle(frame, (x1_1, y1_1), (x1_1 + 80, y1_1 + 160), (0, 255, 0), -1)
        cv2.putText(frame, "PERSON 1", (x1_1, y1_1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        # Moving object 2 (right to left)
        x1_2 = 500 - i * 12
        y1_2 = 250
        cv2.rectangle(frame, (x1_2, y1_2), (x1_2 + 100, y1_2 + 80), (255, 0, 0), -1)
        cv2.putText(frame, "CAR 2", (x1_2, y1_2 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        cv2.putText(frame, f"Frame {i+1}", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        writer.write(frame)

    writer.release()


def main():
    print("=" * 75)
    print(" CIVIS-CORE : End-to-End Ingestion + Detection + Multi-Object Tracking")
    print("=" * 75)

    with tempfile.TemporaryDirectory() as temp_dir:
        video_path = os.path.join(temp_dir, "tracking_test.mp4")
        print("[+] Generating sample video stream with moving objects...")
        generate_moving_object_video(video_path, num_frames=20, fps=30)

        # Step 1: Ingestion
        manager = StreamManager()
        cam_cfg = CameraConfig(
            camera_id="CAM_NORTH_01",
            name="North Gate Tracking Stream",
            source_type=SourceType.FILE,
            source=video_path,
            loop_file=False,
            fps_limit=30.0,
        )
        manager.add_camera(cam_cfg)

        # Step 2: Detection Engine
        det_cfg = DetectorConfig(use_mock=True)
        detector = create_detector(det_cfg)

        # Step 3: Tracking Engine (ByteTrack)
        track_cfg = TrackerConfig(track_buffer=30, track_thresh=0.4, use_mock=False)
        tracker = create_tracker(track_cfg)

        print("[+] Starting pipeline execution...")
        manager.start_all()
        time.sleep(0.3)

        print("\n" + "-" * 75)
        print(f"{'FRAME':<8} | {'CAM_ID':<14} | {'ACTIVE TRACKS (ID, CLASS, STATE, BBOX)':<45}")
        print("-" * 75)

        total_frames = 0
        try:
            while True:
                packet = manager.read_frame("CAM_NORTH_01", timeout=0.2)
                if packet is None:
                    status = manager.get_status("CAM_NORTH_01")
                    if status in (CameraStatus.DISCONNECTED, CameraStatus.STOPPED):
                        break
                    continue

                total_frames += 1

                # Ingestion FramePacket -> Detector -> DetectionResult
                det_result = detector.detect(packet)

                # DetectionResult -> ByteTrackTracker -> TrackResult
                track_result = tracker.update(det_result)

                track_summary = []
                for trk in track_result.tracks:
                    track_summary.append(
                        f"[ID:{trk.track_id} {trk.class_name} ({trk.state.value}) {trk.bbox.to_dict()['x1']:.0f},{trk.bbox.to_dict()['y1']:.0f}]"
                    )

                summary_str = ", ".join(track_summary)
                print(f"{track_result.frame_number:<8} | {track_result.camera_id:<14} | {summary_str}")

        finally:
            manager.stop_all()

        print("=" * 75)
        print(f" CIVIS-CORE Multi-Object Tracking Completed ({total_frames} frames processed)!")
        print("=" * 75)


if __name__ == "__main__":
    main()
