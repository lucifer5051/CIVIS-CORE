import logging
import threading
from typing import Dict, List, Optional

from civis.ingestion.base import VideoSource
from civis.ingestion.factory import create_video_source
from civis.ingestion.models import CameraConfig, CameraStatus, FramePacket

logger = logging.getLogger(__name__)


class StreamManager:
    """
    Manages multiple VideoSource instances concurrently.
    Provides thread-safe camera registration, stream controls, frame fetching, and status tracking.
    """

    def __init__(self) -> None:
        self._sources: Dict[str, VideoSource] = {}
        self._lock = threading.Lock()

    def add_camera(self, config: CameraConfig) -> VideoSource:
        with self._lock:
            if config.camera_id in self._sources:
                raise ValueError(f"Camera ID '{config.camera_id}' is already registered.")

            source = create_video_source(config)
            self._sources[config.camera_id] = source
            logger.info("Added camera: %s (%s)", config.camera_id, config.source_type.value)
            return source

    def remove_camera(self, camera_id: str) -> None:
        with self._lock:
            if camera_id not in self._sources:
                return
            source = self._sources.pop(camera_id)

        source.stop()
        logger.info("Removed camera: %s", camera_id)

    def get_camera(self, camera_id: str) -> Optional[VideoSource]:
        with self._lock:
            return self._sources.get(camera_id)

    def list_cameras(self) -> List[str]:
        with self._lock:
            return list(self._sources.keys())

    def start_camera(self, camera_id: str) -> None:
        camera = self.get_camera(camera_id)
        if camera is None:
            raise KeyError(f"Camera ID '{camera_id}' not found.")
        camera.start()

    def stop_camera(self, camera_id: str) -> None:
        camera = self.get_camera(camera_id)
        if camera is None:
            raise KeyError(f"Camera ID '{camera_id}' not found.")
        camera.stop()

    def start_all(self) -> None:
        with self._lock:
            sources = list(self._sources.values())
        for source in sources:
            source.start()

    def stop_all(self) -> None:
        with self._lock:
            sources = list(self._sources.values())
        for source in sources:
            source.stop()

    def read_frame(self, camera_id: str, timeout: float = 1.0) -> Optional[FramePacket]:
        camera = self.get_camera(camera_id)
        if camera is None:
            return None
        return camera.read(timeout=timeout)

    def get_status(self, camera_id: str) -> Optional[CameraStatus]:
        camera = self.get_camera(camera_id)
        if camera is None:
            return None
        return camera.get_status()

    def get_all_statuses(self) -> Dict[str, CameraStatus]:
        with self._lock:
            return {cam_id: source.get_status() for cam_id, source in self._sources.items()}
