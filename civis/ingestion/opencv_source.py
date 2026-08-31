import os
import queue
import threading
import time
from typing import Optional, Union
import cv2
import numpy as np

from civis.ingestion.base import VideoSource
from civis.ingestion.models import CameraConfig, CameraStatus, FramePacket, SourceType


class OpenCVVideoSource(VideoSource):
    """
    Unified OpenCV-backed VideoSource for local files, webcams, and RTSP streams.
    Ensures thread-safe VideoCapture lifecycle, buffer management, and automatic reconnection.
    """

    def __init__(self, config: CameraConfig) -> None:
        super().__init__(config)
        self._status = CameraStatus.STOPPED
        self._status_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # Queue configuration: size 1 for real-time streams (drop oldest), larger size for file preservation
        queue_size = 1 if self._config.drop_outdated_frames else 120
        self._frame_queue: queue.Queue = queue.Queue(maxsize=queue_size)
        self._frame_counter = 0

    def get_status(self) -> CameraStatus:
        with self._status_lock:
            return self._status

    def _set_status(self, status: CameraStatus) -> None:
        with self._status_lock:
            self._status = status

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._set_status(CameraStatus.CONNECTING)
        self._thread = threading.Thread(
            target=self._capture_loop,
            name=f"CaptureThread-{self.camera_id}",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        self._thread = None
        self._set_status(CameraStatus.STOPPED)

    def read(self, timeout: float = 1.0) -> Optional[FramePacket]:
        try:
            return self._frame_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def _open_capture(self) -> Optional[cv2.VideoCapture]:
        source_val: Union[str, int] = self._config.source

        # Handle numeric string passed as webcam index
        if self._config.source_type == SourceType.WEBCAM and isinstance(source_val, str) and source_val.isdigit():
            source_val = int(source_val)

        # Set FFmpeg transport options for RTSP
        if self._config.source_type == SourceType.RTSP:
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = f"rtsp_transport;{self._config.rtsp_transport}"

        cap = cv2.VideoCapture(source_val)

        if not cap.isOpened():
            return None

        # Set buffer size to minimum for live streams to avoid lag accumulation
        if self._config.drop_outdated_frames:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        # Apply target resolution if configured
        if self._config.width is not None and self._config.width > 0:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(self._config.width))
        if self._config.height is not None and self._config.height > 0:
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(self._config.height))

        return cap

    def _capture_loop(self) -> None:
        reconnect_attempts = 0
        self._frame_counter = 0

        while not self._stop_event.is_set():
            self._set_status(CameraStatus.CONNECTING if reconnect_attempts == 0 else CameraStatus.RECONNECTING)

            cap = self._open_capture()

            if cap is None or not cap.isOpened():
                reconnect_attempts += 1
                if (
                    self._config.max_reconnect_attempts is not None
                    and reconnect_attempts > self._config.max_reconnect_attempts
                ):
                    self._set_status(CameraStatus.ERROR)
                    break

                self._set_status(CameraStatus.RECONNECTING)
                # Wait before retrying reconnect
                if self._stop_event.wait(timeout=self._config.reconnect_interval):
                    break
                continue

            # Connection successfully established
            reconnect_attempts = 0
            self._set_status(CameraStatus.RUNNING)

            # Query source FPS if available
            source_fps = cap.get(cv2.CAP_PROP_FPS)
            if source_fps <= 0 or np.isnan(source_fps):
                source_fps = 30.0

            target_fps = self._config.fps_limit if self._config.fps_limit else source_fps
            frame_interval = 1.0 / target_fps if target_fps > 0 else 0.0

            last_frame_time = time.time()

            try:
                while not self._stop_event.is_set():
                    loop_start = time.time()
                    ret, frame = cap.read()

                    if not ret or frame is None:
                        if self._config.source_type == SourceType.FILE:
                            if self._config.loop_file:
                                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                                continue
                            else:
                                self._set_status(CameraStatus.DISCONNECTED)
                                break  # End of file reached
                        else:
                            # Stream disruption on webcam or RTSP
                            self._set_status(CameraStatus.RECONNECTING)
                            break

                    self._frame_counter += 1
                    now = time.time()
                    actual_fps = 1.0 / (now - last_frame_time) if (now - last_frame_time) > 0 else target_fps
                    last_frame_time = now

                    packet = FramePacket.create(
                        camera_id=self.camera_id,
                        frame_number=self._frame_counter,
                        frame=frame,
                        fps=actual_fps,
                        timestamp=now,
                        metadata={
                            "source_type": self._config.source_type.value,
                            "source": str(self._config.source),
                        },
                    )

                    self._push_frame(packet)

                    # Enforce FPS throttling if set
                    if frame_interval > 0:
                        elapsed = time.time() - loop_start
                        sleep_time = frame_interval - elapsed
                        if sleep_time > 0:
                            time.sleep(sleep_time)

            finally:
                # Always release OpenCV VideoCapture on the capture thread
                cap.release()

            # If stopped explicitly or EOF reached for non-looping file, exit loop
            if self._stop_event.is_set() or self.get_status() == CameraStatus.DISCONNECTED:
                break

            # If disconnected unexpectedly, wait reconnect interval before reconnecting
            if self._stop_event.wait(timeout=self._config.reconnect_interval):
                break

        if self.get_status() not in (CameraStatus.DISCONNECTED, CameraStatus.ERROR):
            self._set_status(CameraStatus.STOPPED)

    def _push_frame(self, packet: FramePacket) -> None:
        if self._config.drop_outdated_frames:
            # Latest frame buffer policy: drop oldest frame if full
            while not self._stop_event.is_set():
                try:
                    self._frame_queue.put_nowait(packet)
                    break
                except queue.Full:
                    try:
                        self._frame_queue.get_nowait()
                    except queue.Empty:
                        pass
        else:
            # Frame preservation policy: blocking put until space is available
            while not self._stop_event.is_set():
                try:
                    self._frame_queue.put(packet, timeout=0.1)
                    break
                except queue.Full:
                    continue
