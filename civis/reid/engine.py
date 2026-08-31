import logging
import threading
import time
from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np

from civis.identity.models import IdentityResult, IdentityState
from civis.ingestion.models import FramePacket
from civis.reid.base import BaseAppearanceEmbedder, BaseCrossCameraEngine
from civis.reid.embedder import MockAppearanceEmbedder, OSNetEmbedder
from civis.reid.gallery import CrossCameraGallery
from civis.reid.matcher import CrossCameraMatcher
from civis.reid.models import (
    CrossCameraMatch,
    CrossCameraReIDResult,
    GlobalEntity,
    ReIDEngineConfig,
)
from civis.tracking.models import TrackResult, TrackState

logger = logging.getLogger(__name__)


class CrossCameraReIDEngine(BaseCrossCameraEngine):
    """
    Cognitive Cross-Camera Person Re-Identification & Global Entity Tracking Engine for CIVIS.
    Extracts appearance features, applies EMA temporal smoothing, executes spatial-temporal
    topology matching, and maintains global cross-camera entities.
    """

    def __init__(self, config: Optional[ReIDEngineConfig] = None) -> None:
        cfg = config if config is not None else ReIDEngineConfig()
        super().__init__(cfg)

        if cfg.use_mock:
            self._embedder: BaseAppearanceEmbedder = MockAppearanceEmbedder(cfg)
        else:
            self._embedder = OSNetEmbedder(cfg)

        self._gallery = CrossCameraGallery(
            ema_alpha=cfg.ema_alpha,
            gallery_ttl_seconds=cfg.gallery_ttl_seconds,
        )
        self._matcher = CrossCameraMatcher(
            similarity_threshold=cfg.similarity_threshold,
            topology_constraints=cfg.topology_constraints,
        )
        self._lock = threading.Lock()

    def reset(self, camera_id: Optional[str] = None) -> None:
        """Resets gallery and memory state."""
        with self._lock:
            self._gallery.reset(camera_id)

    def process(
        self,
        frame_packets: Dict[str, FramePacket],
        track_results: Dict[str, TrackResult],
        identity_results: Optional[Dict[str, IdentityResult]] = None,
    ) -> CrossCameraReIDResult:
        with self._lock:
            start_time = time.perf_counter()
            packet_timestamps = [p.timestamp for p in frame_packets.values() if p is not None]
            latest_timestamp = max(packet_timestamps) if packet_timestamps else time.time()

            active_matches: List[CrossCameraMatch] = []

            # 1. Process each camera feed and update track appearance embeddings
            for cam_id, track_result in track_results.items():
                packet = frame_packets.get(cam_id)
                if packet is None:
                    continue

                current_time = packet.timestamp
                latest_timestamp = max(latest_timestamp, current_time)
                frame_img = packet.frame
                frame_h, frame_w = frame_img.shape[:2]

                # Index identities for this camera if available
                identities_map: Dict[int, str] = {}
                if identity_results and cam_id in identity_results:
                    for ident in identity_results[cam_id].identities:
                        if ident.state == IdentityState.KNOWN and ident.identity_id:
                            identities_map[ident.track_id] = ident.identity_id

                for trk in track_result.tracks:
                    # Only extract appearance for person detections
                    if trk.class_name.lower() != "person":
                        continue
                    if trk.state == TrackState.REMOVED:
                        continue

                    b = trk.bbox
                    x1 = max(0, min(frame_w - 1, int(b.x1)))
                    y1 = max(0, min(frame_h - 1, int(b.y1)))
                    x2 = max(0, min(frame_w, int(b.x2)))
                    y2 = max(0, min(frame_h, int(b.y2)))

                    if (x2 - x1) < self._config.min_crop_width or (y2 - y1) < self._config.min_crop_height:
                        continue

                    crop = frame_img[y1:y2, x1:x2]
                    embedding_res = self._embedder.extract_embedding(
                        crop_image=crop,
                        camera_id=cam_id,
                        track_id=trk.track_id,
                        timestamp=current_time,
                    )

                    if embedding_res is None:
                        continue

                    bbox_tuple = (float(x1), float(y1), float(x2), float(y2))

                    # Update gallery entry with EMA smoothing
                    entry = self._gallery.update_track_appearance(
                        camera_id=cam_id,
                        track_id=trk.track_id,
                        embedding=embedding_res.embedding,
                        timestamp=current_time,
                        bbox=bbox_tuple,
                    )

                    verified_ident = identities_map.get(trk.track_id)

                    # 2. Check cross-camera match if unassigned or currently single-camera entity
                    curr_entity = self._gallery._global_entities.get(entry.global_entity_id) if entry.global_entity_id else None
                    if entry.global_entity_id is None or (curr_entity and curr_entity.num_associated_cameras == 1):
                        match = self._matcher.find_best_match(entry, self._gallery)
                        if match:
                            matched_entry = self._gallery.get_track_entry(
                                match.matched_camera_id, match.matched_track_id
                            )
                            entity = self._gallery.create_or_bind_global_entity(
                                query_entry=entry,
                                matched_entry=matched_entry,
                                similarity_score=match.similarity_score,
                                primary_identity_id=verified_ident,
                            )
                            match.global_entity_id = entity.global_entity_id
                            active_matches.append(match)
                        elif entry.global_entity_id is None:
                            # Register as new global entity
                            self._gallery.create_or_bind_global_entity(
                                query_entry=entry,
                                matched_entry=None,
                                similarity_score=1.0,
                                primary_identity_id=verified_ident,
                            )
                    else:
                        # Update verified identity on existing global entity if newly recognized
                        if verified_ident:
                            self._gallery.create_or_bind_global_entity(
                                query_entry=entry,
                                primary_identity_id=verified_ident,
                            )

            # 3. Clean up inactive tracks beyond TTL
            self._gallery.cleanup_inactive(latest_timestamp)

            # 4. Fetch all active global entities
            global_entities = self._gallery.get_all_global_entities(active_only=True)

            elapsed_ms = (time.perf_counter() - start_time) * 1000.0

            return CrossCameraReIDResult(
                timestamp=latest_timestamp,
                global_entities=global_entities,
                active_matches=active_matches,
                processing_time_ms=elapsed_ms,
                metadata={"engine": "CrossCameraReIDEngine"},
            )


class MockCrossCameraEngine(CrossCameraReIDEngine):
    """
    Mock Cross-Camera Re-ID Engine for deterministic unit tests.
    """

    def __init__(self, config: Optional[ReIDEngineConfig] = None) -> None:
        cfg = config if config is not None else ReIDEngineConfig(use_mock=True)
        super().__init__(cfg)
