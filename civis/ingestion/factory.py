from civis.ingestion.base import VideoSource
from civis.ingestion.models import CameraConfig
from civis.ingestion.opencv_source import OpenCVVideoSource


def create_video_source(config: CameraConfig) -> VideoSource:
    """
    Factory function to instantiate appropriate VideoSource based on camera configuration.
    Currently maps all sources (File, Webcam, RTSP) through the unified OpenCVVideoSource implementation.
    """
    return OpenCVVideoSource(config)
