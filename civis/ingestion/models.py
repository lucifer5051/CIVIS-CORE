import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Tuple, Union
import numpy as np
from pydantic import BaseModel, Field


class SourceType(str, Enum):
    FILE = "file"
    WEBCAM = "webcam"
    RTSP = "rtsp"


class CameraStatus(str, Enum):
    STOPPED = "stopped"
    CONNECTING = "connecting"
    RUNNING = "running"
    RECONNECTING = "reconnecting"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class CameraConfig(BaseModel):
    camera_id: str = Field(..., description="Unique identifier for the camera/stream source")
    name: str = Field(default="", description="Human-readable camera name")
    source_type: SourceType = Field(..., description="Type of source: file, webcam, or rtsp")
    source: Union[str, int] = Field(..., description="Source path (str), device index (int), or RTSP URL")
    fps_limit: Optional[float] = Field(default=None, description="Optional target FPS cap")
    loop_file: bool = Field(default=False, description="Whether to loop local video files upon EOF")
    drop_outdated_frames: Optional[bool] = Field(
        default=None,
        description="Whether to drop outdated frames (defaults to True for webcam/rtsp, False for files)",
    )
    reconnect_interval: float = Field(default=3.0, ge=0.5, description="Interval in seconds between reconnect attempts")
    max_reconnect_attempts: Optional[int] = Field(
        default=None, description="Maximum reconnect attempts (None for infinite retries)"
    )
    rtsp_transport: str = Field(default="tcp", description="RTSP transport protocol ('tcp' or 'udp')")

    def model_post_init(self, __context: Any) -> None:
        if self.drop_outdated_frames is None:
            if self.source_type == SourceType.FILE:
                self.drop_outdated_frames = False
            else:
                self.drop_outdated_frames = True


@dataclass
class FramePacket:
    camera_id: str
    frame_id: str
    timestamp: float
    frame_number: int
    dimensions: Tuple[int, int]  # (width, height)
    frame: np.ndarray
    fps: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        camera_id: str,
        frame_number: int,
        frame: np.ndarray,
        fps: float = 0.0,
        timestamp: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "FramePacket":
        ts = timestamp if timestamp is not None else time.time()
        height, width = frame.shape[:2]
        frame_id = f"{camera_id}_{frame_number}_{uuid.uuid4().hex[:8]}"
        meta = metadata if metadata is not None else {}
        return cls(
            camera_id=camera_id,
            frame_id=frame_id,
            timestamp=ts,
            frame_number=frame_number,
            dimensions=(width, height),
            frame=frame,
            fps=fps,
            metadata=meta,
        )
