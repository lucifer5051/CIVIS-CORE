import os
import tempfile
import time
import unittest
import cv2
import numpy as np

from civis.ingestion.models import CameraConfig, CameraStatus, FramePacket, SourceType
from civis.ingestion.opencv_source import OpenCVVideoSource
from civis.ingestion.stream_manager import StreamManager


def create_synthetic_video(file_path: str, width: int = 320, height: int = 240, fps: float = 30.0, num_frames: int = 30) -> None:
    """Helper to generate a temporary synthetic video file for testing."""
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(file_path, fourcc, fps, (width, height))
    for i in range(num_frames):
        # Create a dynamic color frame with moving text
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        color = (int((i * 10) % 255), int((i * 20) % 255), 255 - int((i * 5) % 255))
        frame[:] = color
        cv2.putText(frame, f"Frame {i}", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
        writer.write(frame)
    writer.release()


class TestFramePacketAndModels(unittest.TestCase):
    def test_camera_config_defaults(self):
        config_file = CameraConfig(
            camera_id="cam_file",
            source_type=SourceType.FILE,
            source="test.mp4",
        )
        self.assertFalse(config_file.drop_outdated_frames)

        config_rtsp = CameraConfig(
            camera_id="cam_rtsp",
            source_type=SourceType.RTSP,
            source="rtsp://127.0.0.1:554/live",
        )
        self.assertTrue(config_rtsp.drop_outdated_frames)

    def test_frame_packet_creation(self):
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        packet = FramePacket.create(
            camera_id="cam_test",
            frame_number=1,
            frame=dummy_frame,
            fps=30.0,
            metadata={"test_key": "test_val"},
        )
        self.assertEqual(packet.camera_id, "cam_test")
        self.assertEqual(packet.frame_number, 1)
        self.assertEqual(packet.dimensions, (640, 480))
        self.assertEqual(packet.fps, 30.0)
        self.assertEqual(packet.metadata["test_key"], "test_val")
        self.assertTrue(packet.frame_id.startswith("cam_test_1_"))


class TestOpenCVVideoSource(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.video_path = os.path.join(self.temp_dir.name, "test_video.mp4")
        create_synthetic_video(self.video_path, width=320, height=240, num_frames=15)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_file_source_read_no_loop(self):
        config = CameraConfig(
            camera_id="test_file_cam",
            source_type=SourceType.FILE,
            source=self.video_path,
            loop_file=False,
        )
        source = OpenCVVideoSource(config)
        source.start()

        packets = []
        for _ in range(30):
            pkt = source.read(timeout=0.2)
            if pkt is not None:
                packets.append(pkt)
            elif source.get_status() == CameraStatus.DISCONNECTED:
                break

        source.stop()

        self.assertGreater(len(packets), 0)
        self.assertLessEqual(len(packets), 15)
        self.assertEqual(packets[0].dimensions, (320, 240))
        self.assertEqual(packets[0].camera_id, "test_file_cam")

    def test_file_source_looping(self):
        config = CameraConfig(
            camera_id="test_loop_cam",
            source_type=SourceType.FILE,
            source=self.video_path,
            loop_file=True,
            fps_limit=100.0,
        )
        source = OpenCVVideoSource(config)
        source.start()

        packets = []
        # Read more than original 15 frames to verify looping
        for _ in range(50):
            pkt = source.read(timeout=0.2)
            if pkt is not None:
                packets.append(pkt)
            if len(packets) >= 25:
                break

        source.stop()

        self.assertGreaterEqual(len(packets), 25)
        self.assertEqual(source.get_status(), CameraStatus.STOPPED)


class TestStreamManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.video_path1 = os.path.join(self.temp_dir.name, "cam1.mp4")
        self.video_path2 = os.path.join(self.temp_dir.name, "cam2.mp4")
        create_synthetic_video(self.video_path1, width=320, height=240, num_frames=10)
        create_synthetic_video(self.video_path2, width=320, height=240, num_frames=10)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_multi_camera_lifecycle(self):
        manager = StreamManager()

        cfg1 = CameraConfig(camera_id="cam_01", source_type=SourceType.FILE, source=self.video_path1, loop_file=True)
        cfg2 = CameraConfig(camera_id="cam_02", source_type=SourceType.FILE, source=self.video_path2, loop_file=True)

        manager.add_camera(cfg1)
        manager.add_camera(cfg2)

        self.assertEqual(set(manager.list_cameras()), {"cam_01", "cam_02"})

        manager.start_all()
        time.sleep(0.5)

        pkt1 = manager.read_frame("cam_01", timeout=0.5)
        pkt2 = manager.read_frame("cam_02", timeout=0.5)

        self.assertIsNotNone(pkt1)
        self.assertIsNotNone(pkt2)
        self.assertEqual(pkt1.camera_id, "cam_01")
        self.assertEqual(pkt2.camera_id, "cam_02")

        statuses = manager.get_all_statuses()
        self.assertEqual(statuses["cam_01"], CameraStatus.RUNNING)
        self.assertEqual(statuses["cam_02"], CameraStatus.RUNNING)

        manager.stop_all()
        statuses_after = manager.get_all_statuses()
        self.assertEqual(statuses_after["cam_01"], CameraStatus.STOPPED)
        self.assertEqual(statuses_after["cam_02"], CameraStatus.STOPPED)


if __name__ == "__main__":
    unittest.main()
