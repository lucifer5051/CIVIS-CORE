import os
import sys
import tempfile
import time
import cv2
import numpy as np

from civis.ingestion import CameraConfig, CameraStatus, SourceType, StreamManager


def generate_demo_video(filename: str, duration_sec: int = 5, fps: int = 30) -> str:
    """Generate a clean synthetic video file for demonstration purposes."""
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    width, height = 640, 480
    writer = cv2.VideoWriter(filename, fourcc, fps, (width, height))

    total_frames = duration_sec * fps
    for i in range(total_frames):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        # Gradient background
        frame[:, :, 0] = (i * 2) % 255
        frame[:, :, 1] = (i * 4) % 255
        frame[:, :, 2] = (128 + i * 3) % 255

        # Render text overlay
        cv2.putText(
            frame,
            f"CIVIS-CORE Ingestion Demo - Frame {i+1}/{total_frames}",
            (30, 80),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
        )
        cv2.putText(
            frame,
            f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            (30, 130),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (200, 255, 200),
            2,
        )
        writer.write(frame)

    writer.release()
    return filename


def main():
    print("=" * 70)
    print(" CIVIS-CORE : Camera & Video Ingestion Demonstration")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as temp_dir:
        file1 = os.path.join(temp_dir, "camera_north.mp4")
        file2 = os.path.join(temp_dir, "camera_south.mp4")

        print("[+] Generating synthetic video streams for North and South cameras...")
        generate_demo_video(file1, duration_sec=4, fps=30)
        generate_demo_video(file2, duration_sec=4, fps=30)

        # Initialize StreamManager
        manager = StreamManager()

        # Configure Camera 1 (North Gate)
        cfg_north = CameraConfig(
            camera_id="CAM_NORTH_01",
            name="North Gate Entrance",
            source_type=SourceType.FILE,
            source=file1,
            loop_file=True,
            fps_limit=30.0,
        )

        # Configure Camera 2 (South Gate)
        cfg_south = CameraConfig(
            camera_id="CAM_SOUTH_02",
            name="South Parking Area",
            source_type=SourceType.FILE,
            source=file2,
            loop_file=True,
            fps_limit=30.0,
        )

        print("[+] Registering cameras with StreamManager...")
        manager.add_camera(cfg_north)
        manager.add_camera(cfg_south)

        print(f"[+] Registered Cameras: {manager.list_cameras()}")

        print("[+] Starting ingestion streams...")
        manager.start_all()

        time.sleep(0.5)
        print("[+] Current Stream Statuses:")
        for cam_id, status in manager.get_all_statuses().items():
            print(f"    - {cam_id}: {status.value}")

        print("\n[+] Reading incoming FramePackets (Simulating Ingestion Loop for 3 seconds)...")
        start_time = time.time()
        packet_count = 0

        try:
            while time.time() - start_time < 3.0:
                for cam_id in manager.list_cameras():
                    packet = manager.read_frame(cam_id, timeout=0.05)
                    if packet is not None:
                        packet_count += 1
                        print(
                            f"  [RECEIVED] Cam: {packet.camera_id:<12} | "
                            f"FrameID: {packet.frame_id:<28} | "
                            f"Seq: {packet.frame_number:<4} | "
                            f"Dim: {packet.dimensions} | "
                            f"FPS: {packet.fps:.1f} | "
                            f"TS: {packet.timestamp:.3f}"
                        )
                time.sleep(0.02)
        except KeyboardInterrupt:
            print("\n[-] Interrupted by user.")

        print(f"\n[+] Total FramePackets ingested across streams: {packet_count}")

        print("[+] Stopping all ingestion streams...")
        manager.stop_all()

        print("[+] Final Stream Statuses:")
        for cam_id, status in manager.get_all_statuses().items():
            print(f"    - {cam_id}: {status.value}")

        print("=" * 70)
        print(" CIVIS-CORE Ingestion Module Test Completed Successfully!")
        print("=" * 70)


if __name__ == "__main__":
    main()
