import logging
import uuid
from typing import Dict, List, Optional, Set, Tuple
import numpy as np

from civis.reid.models import (
    AppearanceEmbedding,
    CameraTrackBinding,
    GlobalEntity,
)

logger = logging.getLogger(__name__)


class TrackAppearanceEntry:
    def __init__(
        self,
        camera_id: str,
        track_id: int,
        initial_embedding: np.ndarray,
        timestamp: float,
        bbox: Tuple[float, float, float, float],
    ) -> None:
        self.camera_id = camera_id
        self.track_id = track_id
        self.smoothed_embedding = initial_embedding.copy()
        self.first_seen = timestamp
        self.last_seen = timestamp
        self.last_bbox = bbox
        self.observations_count = 1
        self.global_entity_id: Optional[str] = None

    def update(
        self,
        new_embedding: np.ndarray,
        timestamp: float,
        bbox: Tuple[float, float, float, float],
        ema_alpha: float = 0.7,
    ) -> None:
        # EMA update: E(t) = alpha * E_new + (1 - alpha) * E_old
        updated = ema_alpha * new_embedding + (1.0 - ema_alpha) * self.smoothed_embedding
        norm = np.linalg.norm(updated)
        if norm > 0:
            self.smoothed_embedding = updated / norm
        self.last_seen = timestamp
        self.last_bbox = bbox
        self.observations_count += 1

    def to_binding(self, appearance_conf: float = 1.0) -> CameraTrackBinding:
        return CameraTrackBinding(
            camera_id=self.camera_id,
            track_id=self.track_id,
            first_seen=self.first_seen,
            last_seen=self.last_seen,
            last_bbox=self.last_bbox,
            observations_count=self.observations_count,
            appearance_confidence=appearance_conf,
        )


class CrossCameraGallery:
    """
    Manages spatial-temporal appearance representations across camera feeds,
    EMA smoothing, and GlobalEntity associations.
    """

    def __init__(self, ema_alpha: float = 0.7, gallery_ttl_seconds: float = 120.0) -> None:
        self.ema_alpha = ema_alpha
        self.gallery_ttl_seconds = gallery_ttl_seconds

        # Active track appearance dictionary: (camera_id, track_id) -> TrackAppearanceEntry
        self._tracks: Dict[Tuple[str, int], TrackAppearanceEntry] = {}

        # Global entities dictionary: global_entity_id -> GlobalEntity
        self._global_entities: Dict[str, GlobalEntity] = {}

    def update_track_appearance(
        self,
        camera_id: str,
        track_id: int,
        embedding: np.ndarray,
        timestamp: float,
        bbox: Tuple[float, float, float, float],
    ) -> TrackAppearanceEntry:
        """Adds or updates track appearance with EMA smoothing."""
        key = (camera_id, track_id)
        if key not in self._tracks:
            entry = TrackAppearanceEntry(camera_id, track_id, embedding, timestamp, bbox)
            self._tracks[key] = entry
        else:
            entry = self._tracks[key]
            entry.update(embedding, timestamp, bbox, ema_alpha=self.ema_alpha)
        return entry

    def get_track_entry(self, camera_id: str, track_id: int) -> Optional[TrackAppearanceEntry]:
        return self._tracks.get((camera_id, track_id))

    def get_other_camera_tracks(self, exclude_camera_id: str) -> List[TrackAppearanceEntry]:
        """Returns all active track appearance records from other cameras."""
        return [entry for (cam, _), entry in self._tracks.items() if cam != exclude_camera_id]

    def create_or_bind_global_entity(
        self,
        query_entry: TrackAppearanceEntry,
        matched_entry: Optional[TrackAppearanceEntry] = None,
        similarity_score: float = 1.0,
        primary_identity_id: Optional[str] = None,
    ) -> GlobalEntity:
        """
        Binds query track (and optional matched track) to a GlobalEntity.
        If matched track already belongs to a GlobalEntity, adds query track to it.
        Otherwise creates a new GlobalEntity.
        """
        old_entity_id = query_entry.global_entity_id

        # Case 1: Matched entry already has a global entity
        if matched_entry and matched_entry.global_entity_id and matched_entry.global_entity_id in self._global_entities:
            entity = self._global_entities[matched_entry.global_entity_id]
            if old_entity_id and old_entity_id != entity.global_entity_id and old_entity_id in self._global_entities:
                del self._global_entities[old_entity_id]
            query_entry.global_entity_id = entity.global_entity_id
            
            # Update bindings
            existing_cams = {t.camera_id: t for t in entity.associated_tracks}
            if query_entry.camera_id in existing_cams:
                # Update existing camera track binding
                b = existing_cams[query_entry.camera_id]
                b.track_id = query_entry.track_id
                b.last_seen = query_entry.last_seen
                b.last_bbox = query_entry.last_bbox
                b.observations_count = query_entry.observations_count
            else:
                entity.associated_tracks.append(query_entry.to_binding(similarity_score))

            entity.last_seen_timestamp = max(entity.last_seen_timestamp, query_entry.last_seen)
            if primary_identity_id and not entity.primary_identity_id:
                entity.primary_identity_id = primary_identity_id
            self._update_entity_mean_embedding(entity)
            return entity

        # Case 2: Query entry already has a global entity
        if query_entry.global_entity_id and query_entry.global_entity_id in self._global_entities:
            entity = self._global_entities[query_entry.global_entity_id]
            if matched_entry:
                if matched_entry.global_entity_id and matched_entry.global_entity_id != entity.global_entity_id:
                    if matched_entry.global_entity_id in self._global_entities:
                        del self._global_entities[matched_entry.global_entity_id]
                matched_entry.global_entity_id = entity.global_entity_id
                entity.associated_tracks.append(matched_entry.to_binding(similarity_score))
            entity.last_seen_timestamp = max(entity.last_seen_timestamp, query_entry.last_seen)
            if primary_identity_id and not entity.primary_identity_id:
                entity.primary_identity_id = primary_identity_id
            self._update_entity_mean_embedding(entity)
            return entity

        # Case 3: Create brand new global entity
        entity_id = f"global_ent_{uuid.uuid4().hex[:8]}"
        query_entry.global_entity_id = entity_id

        bindings = [query_entry.to_binding(1.0)]
        if matched_entry:
            matched_entry.global_entity_id = entity_id
            bindings.append(matched_entry.to_binding(similarity_score))

        entity = GlobalEntity(
            global_entity_id=entity_id,
            associated_tracks=bindings,
            primary_identity_id=primary_identity_id,
            first_seen_timestamp=query_entry.first_seen,
            last_seen_timestamp=query_entry.last_seen,
            is_active=True,
        )
        self._update_entity_mean_embedding(entity)
        self._global_entities[entity_id] = entity
        return entity

    def _update_entity_mean_embedding(self, entity: GlobalEntity) -> None:
        vectors = []
        for b in entity.associated_tracks:
            entry = self.get_track_entry(b.camera_id, b.track_id)
            if entry is not None:
                vectors.append(entry.smoothed_embedding)
        if vectors:
            mean_vec = np.mean(vectors, axis=0)
            norm = np.linalg.norm(mean_vec)
            if norm > 0:
                entity.mean_embedding = (mean_vec / norm).astype(np.float32)

    def cleanup_inactive(self, current_time: float) -> List[GlobalEntity]:
        """Removes inactive tracks and global entities exceeding TTL."""
        to_del_tracks = [
            k for k, v in self._tracks.items()
            if (current_time - v.last_seen) > self.gallery_ttl_seconds
        ]
        for k in to_del_tracks:
            del self._tracks[k]

        expired_entities = []
        to_del_entities = []
        for e_id, entity in self._global_entities.items():
            if (current_time - entity.last_seen_timestamp) > self.gallery_ttl_seconds:
                entity.is_active = False
                expired_entities.append(entity)
                to_del_entities.append(e_id)

        for e_id in to_del_entities:
            del self._global_entities[e_id]

        return expired_entities

    def get_all_global_entities(self, active_only: bool = True) -> List[GlobalEntity]:
        if active_only:
            return [e for e in self._global_entities.values() if e.is_active]
        return list(self._global_entities.values())

    def reset(self, camera_id: Optional[str] = None) -> None:
        if camera_id is None:
            self._tracks.clear()
            self._global_entities.clear()
        else:
            to_del = [k for k in self._tracks.keys() if k[0] == camera_id]
            for k in to_del:
                del self._tracks[k]
