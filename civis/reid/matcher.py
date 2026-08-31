import logging
from typing import Dict, List, Optional, Tuple
import numpy as np

from civis.reid.gallery import CrossCameraGallery, TrackAppearanceEntry
from civis.reid.models import (
    CameraTopologyConstraint,
    CrossCameraMatch,
    MatchStatus,
)

logger = logging.getLogger(__name__)


class CrossCameraMatcher:
    """
    Computes cosine similarity matching across camera feeds with
    spatial-temporal camera transition topology gating.
    """

    def __init__(
        self,
        similarity_threshold: float = 0.70,
        topology_constraints: Optional[List[CameraTopologyConstraint]] = None,
    ) -> None:
        self.similarity_threshold = similarity_threshold
        self._topology_map: Dict[Tuple[str, str], CameraTopologyConstraint] = {}
        if topology_constraints:
            for c in topology_constraints:
                self._topology_map[(c.source_camera_id, c.target_camera_id)] = c
                if c.allow_bidirectional:
                    self._topology_map[(c.target_camera_id, c.source_camera_id)] = c

    def find_best_match(
        self,
        query_entry: TrackAppearanceEntry,
        gallery: CrossCameraGallery,
    ) -> Optional[CrossCameraMatch]:
        """
        Searches other camera tracks in the gallery for the highest-similarity match
        satisfying both the visual similarity threshold and spatial-temporal travel gating.
        """
        candidates = gallery.get_other_camera_tracks(exclude_camera_id=query_entry.camera_id)
        if not candidates:
            return None

        best_match: Optional[CrossCameraMatch] = None
        best_score = -1.0

        q_vec = query_entry.smoothed_embedding
        q_cam = query_entry.camera_id
        q_trk = query_entry.track_id
        q_time = query_entry.last_seen

        for cand in candidates:
            g_vec = cand.smoothed_embedding
            g_cam = cand.camera_id
            g_trk = cand.track_id
            g_time = cand.last_seen

            # 1. Cosine similarity
            sim = float(np.dot(q_vec, g_vec))
            if sim < self.similarity_threshold:
                continue

            # 2. Temporal Travel-Time & Topology Validation
            dt = abs(q_time - g_time)
            topo_key = (g_cam, q_cam)
            if topo_key in self._topology_map:
                constraint = self._topology_map[topo_key]
                if dt < constraint.min_travel_time_sec or dt > constraint.max_travel_time_sec:
                    continue

            if sim > best_score:
                best_score = sim
                # Determine target global entity ID if candidate has one
                entity_id = cand.global_entity_id or "unassigned"

                best_match = CrossCameraMatch(
                    query_camera_id=q_cam,
                    query_track_id=q_trk,
                    matched_camera_id=g_cam,
                    matched_track_id=g_trk,
                    global_entity_id=entity_id,
                    similarity_score=round(sim, 4),
                    time_delta_seconds=round(dt, 2),
                    status=MatchStatus.CONFIRMED,
                )

        return best_match
