import threading
from typing import Dict, Optional

from civis.identity.models import IdentityResult
from civis.ingestion.models import FramePacket
from civis.reid.base import BaseCrossCameraEngine
from civis.reid.models import CrossCameraReIDResult
from civis.tracking.models import TrackResult


class CrossCameraCoordinator:
    """
    Thread-safe coordinator for cross-camera analytics (e.g. shared Re-ID gallery).
    """

    def __init__(self, reid_engine: Optional[BaseCrossCameraEngine] = None) -> None:
        self.reid_engine = reid_engine
        self._lock = threading.Lock()

    def process_camera_frame(
        self,
        camera_id: str,
        packet: FramePacket,
        track_result: TrackResult,
        identity_result: Optional[IdentityResult] = None,
    ) -> Optional[CrossCameraReIDResult]:
        if self.reid_engine is None:
            return None

        with self._lock:
            packets = {camera_id: packet}
            tracks = {camera_id: track_result}
            identities = {camera_id: identity_result} if identity_result else None
            return self.reid_engine.process(packets, tracks, identities)

    def reset(self) -> None:
        with self._lock:
            if self.reid_engine and hasattr(self.reid_engine, "reset"):
                self.reid_engine.reset()
