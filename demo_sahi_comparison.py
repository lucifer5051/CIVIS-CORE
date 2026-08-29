import os
import tempfile
import time
import cv2
import numpy as np

from civis.detection import (
    DetectionMode,
    DetectorConfig,
    SAHIConfig,
    create_detector,
)
from civis.ingestion import CameraConfig, CameraStatus, SourceType, StreamManager


def generate_highres_test_video(file_path: str, num_frames: int = 10, fps: int = 30) -> None:
    width, height = 1280, 720
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(file_path, fourcc, fps, (width, height))

    for i in range(num_frames):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:] = (40, 40, 40)

        # Draw 1 large object
        cv2.rectangle(frame, (100, 100), (400, 400), (0, 200, 200), -1)
        cv2.putText(frame, "LARGE VEHICLE", (110, 140), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        # Draw 4 tiny objects in different quadrants (to test SAHI slicing)
        cv2.circle(frame, (800, 150), 12, (0, 255, 0), -1)  # Small target top-right
        cv2.circle(frame, (1100, 600), 10, (0, 0, 255), -1)  # Small target bottom-right
        cv2.circle(frame, (200, 620), 14, (255, 0, 255), -1)  # Small target bottom-left

        cv2.putText(frame, f"Frame {i+1}", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
        writer.write(frame)

    writer.release()


def main():
    print("=" * 75)
    print(" CIVIS-CORE : Full-Frame YOLO12 vs SAHI Sliced Inference Benchmark")
    print("=" * 75)

    with tempfile.TemporaryDirectory() as temp_dir:
        video_path = os.path.join(temp_dir, "benchmark_720p.mp4")
        print("[+] Generating 720p synthetic test stream with small targets...")
        generate_highres_test_video(video_path, num_frames=10, fps=30)

        manager = StreamManager()
        cam_cfg = CameraConfig(
            camera_id="CAM_HD_01",
            name="HD Surveillance Stream",
            source_type=SourceType.FILE,
            source=video_path,
            loop_file=True,
            fps_limit=30.0,
        )
        manager.add_camera(cam_cfg)
        manager.start_all()
        time.sleep(0.3)

        # Detector 1: Full-Frame YOLO12
        cfg_full = DetectorConfig(
            use_mock=True,
            sahi_config=SAHIConfig(mode=DetectionMode.FULL_FRAME),
        )
        det_full = create_detector(cfg_full)

        # Detector 2: YOLO12 + SAHI Sliced Inference
        sahi_params = SAHIConfig(
            slice_height=360,
            slice_width=640,
            overlap_height_ratio=0.2,
            overlap_width_ratio=0.2,
            mode=DetectionMode.HYBRID,
            postprocess_match_threshold=0.5,
        )
        cfg_sahi = DetectorConfig(
            use_mock=True,
            sahi_config=sahi_params,
        )
        det_sahi = create_detector(cfg_sahi)

        print(f"\n[+] SAHI Configuration Applied:")
        print(f"    - Slice Dimensions: {sahi_params.slice_width}x{sahi_params.slice_height} px")
        print(f"    - Overlap Ratios  : Width {sahi_params.overlap_width_ratio*100:.0f}%, Height {sahi_params.overlap_height_ratio*100:.0f}%")
        print(f"    - Inference Mode  : {sahi_params.mode.value}")
        print(f"    - NMS Match Thresh: {sahi_params.postprocess_match_threshold}")

        print("\n" + "-" * 75)
        print(f"{'FRAME':<8} | {'FULL-FRAME DETECTIONS':<22} | {'SAHI DETECTIONS (HYBRID)':<25} | {'SAHI SLICES':<11}")
        print("-" * 75)

        for i in range(5):
            packet = manager.read_frame("CAM_HD_01", timeout=0.5)
            if packet is None:
                break

            # Benchmark 1: Full-frame
            res_full = det_full.detect(packet)

            # Benchmark 2: SAHI Hybrid
            res_sahi = det_sahi.detect(packet)

            slice_count = res_sahi.metadata.get("slice_count", 0)

            print(
                f"{packet.frame_number:<8} | "
                f"Count: {res_full.num_detections:<3} ({res_full.inference_time_ms:5.2f} ms)   | "
                f"Count: {res_sahi.num_detections:<3} ({res_sahi.inference_time_ms:5.2f} ms)   | "
                f"{slice_count:<11}"
            )

        manager.stop_all()

        print("=" * 75)
        print(" CIVIS-CORE SAHI Comparison Benchmark Completed Successfully!")
        print("=" * 75)


if __name__ == "__main__":
    main()
