"""
Camera & Video Ingestion Module for CIVIS.
"""

from civis.ingestion.models import SourceType, CameraStatus, CameraConfig, FramePacket
from civis.ingestion.base import VideoSource
from civis.ingestion.opencv_source import OpenCVVideoSource
from civis.ingestion.factory import create_video_source
from civis.ingestion.stream_manager import StreamManager

__all__ = [
    "SourceType",
    "CameraStatus",
    "CameraConfig",
    "FramePacket",
    "VideoSource",
    "OpenCVVideoSource",
    "create_video_source",
    "StreamManager",
]
