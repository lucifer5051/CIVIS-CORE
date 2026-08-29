from civis.tracking.base import BaseTracker
from civis.tracking.bytetrack_tracker import ByteTrackTracker
from civis.tracking.mock_tracker import MockTracker
from civis.tracking.models import TrackerConfig


def create_tracker(config: TrackerConfig) -> BaseTracker:
    """
    Factory function to instantiate appropriate tracker based on configuration.
    Returns MockTracker if config.use_mock is True, else ByteTrackTracker.
    """
    if config.use_mock:
        return MockTracker(config)
    return ByteTrackTracker(config)
