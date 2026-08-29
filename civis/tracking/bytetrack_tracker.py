import logging
import time
from typing import Dict, List, Optional
import numpy as np
import supervision as sv

from civis.detection.models import BoundingBox, DetectionResult
from civis.tracking.base import BaseTracker
from civis.tracking.models import (
    TrackState,
    TrackedObject,
    TrackResult,
    TrackerConfig,
)

logger = logging.getLogger(__name__)


class ByteTrackTracker(BaseTracker):
    """
    ByteTrack-powered Multi-Object Tracking Engine for CIVIS.
    Maintains camera-scoped isolated tracking state and enforces CIVIS TrackState lifecycle.
    """

    def __init__(self, config: Optional[TrackerConfig] = None) -> None:
        cfg = config if config is not None else TrackerConfig()
        super().__init__(cfg)
        self._trackers: Dict[str, sv.ByteTrack] = {}
        self._histories: Dict[str, Dict[int, TrackedObject]] = {}

    def _get_camera_state(self, camera_id: str) -> tuple[sv.ByteTrack, Dict[int, TrackedObject]]:
        if camera_id not in self._trackers:
            tracker = sv.ByteTrack(
                track_activation_threshold=self._config.track_thresh,
                lost_track_buffer=self._config.track_buffer,
                minimum_matching_threshold=self._config.match_thresh,
                frame_rate=self._config.frame_rate,
            )
            self._trackers[camera_id] = tracker
            self._histories[camera_id] = {}
        return self._trackers[camera_id], self._histories[camera_id]

    def reset(self, camera_id: Optional[str] = None) -> None:
        if camera_id is None:
            self._trackers.clear()
            self._histories.clear()
        else:
            if camera_id in self._trackers:
                del self._trackers[camera_id]
            if camera_id in self._histories:
                del self._histories[camera_id]

    def update(self, detection_result: DetectionResult) -> TrackResult:
        start_time = time.perf_counter()
        cam_id = detection_result.camera_id
        tracker, history = self._get_camera_state(cam_id)
        current_time = detection_result.timestamp

        detections = detection_result.detections
        updated_track_ids = set()

        if detections:
            # Format detections into supervision format
            xyxy_list = []
            conf_list = []
            class_id_list = []
            class_name_map = {}

            for det in detections:
                xyxy_list.append([det.bbox.x1, det.bbox.y1, det.bbox.x2, det.bbox.y2])
                conf_list.append(det.confidence)
                class_id_list.append(det.class_id)
                class_name_map[det.class_id] = det.class_name

            sv_detections = sv.Detections(
                xyxy=np.array(xyxy_list, dtype=np.float32),
                confidence=np.array(conf_list, dtype=np.float32),
                class_id=np.array(class_id_list, dtype=np.int32),
            )

            tracked_sv = tracker.update_with_detections(sv_detections)

            if tracked_sv.tracker_id is not None:
                for i in range(len(tracked_sv)):
                    tid = int(tracked_sv.tracker_id[i])
                    x1, y1, x2, y2 = tracked_sv.xyxy[i]
                    conf = float(tracked_sv.confidence[i]) if tracked_sv.confidence is not None else 1.0
                    cls_id = int(tracked_sv.class_id[i]) if tracked_sv.class_id is not None else 0
                    cls_name = class_name_map.get(cls_id, str(cls_id))

                    bbox = BoundingBox(x1=float(x1), y1=float(y1), x2=float(x2), y2=float(y2))
                    updated_track_ids.add(tid)

                    if tid not in history:
                        # New track created
                        track = TrackedObject(
                            track_id=tid,
                            class_id=cls_id,
                            class_name=cls_name,
                            confidence=conf,
                            bbox=bbox,
                            state=TrackState.NEW,
                            age=1,
                            time_since_update=0,
                            first_seen_timestamp=current_time,
                            last_seen_timestamp=current_time,
                        )
                        history[tid] = track
                    else:
                        # Active track updated
                        track = history[tid]
                        track.bbox = bbox
                        track.confidence = conf
                        track.age += 1
                        track.time_since_update = 0
                        track.last_seen_timestamp = current_time
                        track.state = TrackState.TRACKED

        # Update lost and removed track lifecycles
        to_remove = []
        output_tracks: List[TrackedObject] = []

        for tid, track in history.items():
            if tid in updated_track_ids:
                output_tracks.append(track)
            else:
                track.time_since_update += 1
                track.age += 1
                if track.time_since_update > self._config.track_buffer:
                    track.state = TrackState.REMOVED
                    to_remove.append(tid)
                else:
                    track.state = TrackState.LOST
                    output_tracks.append(track)

        for tid in to_remove:
            del history[tid]

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
            metadata={
                "engine": "ByteTrackTracker",
                "camera_id": cam_id,
            },
        )
