import os
import tempfile
import time
import cv2
import numpy as np

from civis.detection import DetectorConfig, create_detector
from civis.ingestion import CameraConfig, CameraStatus, SourceType, StreamManager


def generate_test_video(file_path: str, num_frames: int = 15, fps: int = 30) -> None:
    width, height = 640, 480
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(file_path, fourcc, fps, (width, height))

    for i in range(num_frames):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:] = (50, 50, 50)
        # Draw synthetic objects (person / car box representation)
        cv2.rectangle(frame, (100, 100), (250, 400), (0, 255, 0), -1)  # Synthetic object
        cv2.putText(frame, "PERSON", (110, 140), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        cv2.rectangle(frame, (350, 200), (550, 380), (255, 0, 0), -1)  # Synthetic object
        cv2.putText(frame, "CAR", (360, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        cv2.putText(frame, f"Frame {i+1}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        writer.write(frame)

    writer.release()


def main():
    print("=" * 70)
    print(" CIVIS-CORE : End-to-End Ingestion + Detection Engine Demonstration")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as temp_dir:
        video_file = os.path.join(temp_dir, "test_input.mp4")
        print("[+] Creating sample video for detection test...")
        generate_test_video(video_file, num_frames=20, fps=30)

        # Step 1: Initialize Ingestion StreamManager
        manager = StreamManager()
        cam_cfg = CameraConfig(
            camera_id="CAM_TEST_01",
            name="Main Gate Camera",
            source_type=SourceType.FILE,
            source=video_file,
            loop_file=False,
            fps_limit=30.0,
        )
        manager.add_camera(cam_cfg)

        # Step 2: Initialize Detector (MockDetector for fast verification or YOLO12Detector)
        det_cfg = DetectorConfig(
            model_path="yolov8n.pt",  # lightweight default weights
            conf_threshold=0.25,
            iou_threshold=0.45,
            device="cpu",
            use_mock=True,  # Set to True for deterministic test without downloading weights
        )
        print(f"[+] Initializing Detector Engine (Mock: {det_cfg.use_mock}, Device: {det_cfg.device})...")
        detector = create_detector(det_cfg)

        # Step 3: Start Ingestion
        print("[+] Starting video ingestion...")
        manager.start_all()
        time.sleep(0.3)

        print("\n[+] Processing FramePackets through Detection Engine:")
        processed_frames = 0
        total_detections_found = 0

        while True:
            packet = manager.read_frame("CAM_TEST_01", timeout=0.2)
            if packet is None:
                status = manager.get_status("CAM_TEST_01")
                if status in (CameraStatus.DISCONNECTED, CameraStatus.STOPPED):
                    break
                continue

            processed_frames += 1

            # Run detection directly on incoming FramePacket
            result = detector.detect(packet)
            total_detections_found += result.num_detections

            det_summary = ", ".join([f"{d.class_name}({d.confidence:.2f})" for d in result.detections])
            print(
                f"  [FRAME {result.frame_number:02d}] "
                f"Cam: {result.camera_id} | "
                f"Detections: {result.num_detections} [{det_summary}] | "
                f"Latency: {result.inference_time_ms:.2f} ms"
            )

        manager.stop_all()

        print(f"\n[+] Total Frames Processed: {processed_frames}")
        print(f"[+] Total Objects Detected: {total_detections_found}")

        print("=" * 70)
        print(" CIVIS-CORE Detection Engine Test Completed Successfully!")
        print("=" * 70)


if __name__ == "__main__":
    main()
