import time
from typing import Dict, List, Optional
from civis.detection.models import DetectionResult
from civis.tracking.base import BaseTracker
from civis.tracking.models import (
    TrackState,
    TrackedObject,
    TrackResult,
    TrackerConfig,
)


class CameraMockState:
    def __init__(self, track_buffer: int) -> None:
        self.next_track_id = 1
        self.active_tracks: Dict[int, TrackedObject] = {}
        self.track_buffer = track_buffer


class MockTracker(BaseTracker):
    """
    Mock tracker for deterministic unit testing without external dependencies.
    Maintains camera-scoped track IDs and CIVIS TrackState lifecycle.
    """

    def __init__(self, config: Optional[TrackerConfig] = None) -> None:
        cfg = config if config is not None else TrackerConfig(use_mock=True)
        super().__init__(cfg)
        self._camera_states: Dict[str, CameraMockState] = {}

    def _get_state(self, camera_id: str) -> CameraMockState:
        if camera_id not in self._camera_states:
            self._camera_states[camera_id] = CameraMockState(self._config.track_buffer)
        return self._camera_states[camera_id]

    def reset(self, camera_id: Optional[str] = None) -> None:
        if camera_id is None:
            self._camera_states.clear()
        elif camera_id in self._camera_states:
            del self._camera_states[camera_id]

    def update(self, detection_result: DetectionResult) -> TrackResult:
        start_time = time.perf_counter()
        cam_id = detection_result.camera_id
        state = self._get_state(cam_id)

        current_time = detection_result.timestamp
        matched_track_ids = set()
        output_tracks: List[TrackedObject] = []

        # Process detections and map/assign track IDs
        for det in detection_result.detections:
            matched_id: Optional[int] = None

            # Attempt to match existing active/lost track by class_id
            for tid, track in state.active_tracks.items():
                if tid not in matched_track_ids and track.class_id == det.class_id:
                    matched_id = tid
                    break

            if matched_id is not None:
                # Existing track updated
                track = state.active_tracks[matched_id]
                track.bbox = det.bbox
                track.confidence = det.confidence
                track.age += 1
                track.time_since_update = 0
                track.last_seen_timestamp = current_time
                track.state = TrackState.TRACKED
                matched_track_ids.add(matched_id)
                output_tracks.append(track)
            else:
                # New track created
                new_id = state.next_track_id
                state.next_track_id += 1
                new_track = TrackedObject(
                    track_id=new_id,
                    class_id=det.class_id,
                    class_name=det.class_name,
                    confidence=det.confidence,
                    bbox=det.bbox,
                    state=TrackState.NEW,
                    age=1,
                    time_since_update=0,
                    first_seen_timestamp=current_time,
                    last_seen_timestamp=current_time,
                )
                state.active_tracks[new_id] = new_track
                matched_track_ids.add(new_id)
                output_tracks.append(new_track)

        # Handle unmatched tracks (LOST / REMOVED)
        to_remove = []
        for tid, track in state.active_tracks.items():
            if tid not in matched_track_ids:
                track.time_since_update += 1
                track.age += 1

                if track.time_since_update > state.track_buffer:
                    track.state = TrackState.REMOVED
                    to_remove.append(tid)
                else:
                    track.state = TrackState.LOST
                    output_tracks.append(track)

        for tid in to_remove:
            del state.active_tracks[tid]

        active_ids = [t.track_id for t in output_tracks if t.state in (TrackState.NEW, TrackState.TRACKED)]
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        return TrackResult(
            camera_id=cam_id,
            frame_id=detection_result.frame_id,
            timestamp=detection_result.timestamp,
            frame_number=detection_result.frame_number,
            dimensions=detection_result.dimensions,
            tracks=output_tracks,
            active_track_ids=active_ids,
            processing_time_ms=elapsed_ms,
            metadata={"engine": "MockTracker"},
        )
