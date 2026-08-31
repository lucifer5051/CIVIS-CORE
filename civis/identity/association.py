import logging, time
from typing import Dict, List, Optional, Tuple
from civis.identity.models import (
    AssociatedIdentity,
    IdentityConfig,
    IdentityMatch,
    IdentityState,
)

logger = logging.getLogger(__name__)


class TrackIdentityHistory:
    def __init__(self, camera_id: str, track_id: int) -> None:
        self.camera_id = camera_id
        self.track_id = track_id
        self.identity_id: str = "UNKNOWN"
        self.name: str = "Unknown Person"
        self.state: IdentityState = IdentityState.UNKNOWN
        self.observations_count: int = 0
        self.similarity_scores: List[float] = []
        self.quality_scores: List[float] = []
        self.last_updated_time: float = time.time()
        self.frames_since_update: int = 0

    def update(
        self,
        match: IdentityMatch,
        quality_score: float,
        config: IdentityConfig,
        timestamp: float,
    ) -> AssociatedIdentity:
        self.last_updated_time = timestamp
        self.frames_since_update = 0

        sim = match.similarity_score
        qual = quality_score

        self.similarity_scores.append(sim)
        self.quality_scores.append(qual)

        if len(self.similarity_scores) > 30:
            self.similarity_scores.pop(0)
            self.quality_scores.pop(0)

        if match.is_known and qual >= config.min_quality_score:
            self.observations_count += 1
        elif not match.is_known:
            self.observations_count = max(0, self.observations_count - 1)

        # Multi-signal confidence calculations
        avg_sim = float(sum(self.similarity_scores[-5:]) / len(self.similarity_scores[-5:])) if self.similarity_scores else sim
        rec_conf = 0.6 * sim + 0.4 * qual
        obs_factor = min(1.0, self.observations_count / float(config.min_observations))
        assoc_conf = 0.5 * avg_sim + 0.3 * qual + 0.2 * obs_factor

        # Identity State Resolution
        if (
            match.is_known
            and self.observations_count >= config.min_observations
            and assoc_conf >= config.similarity_threshold
        ):
            self.state = IdentityState.KNOWN
            self.identity_id = match.identity_id
            self.name = match.name
        elif match.is_known or (self.state == IdentityState.KNOWN and self.frames_since_update < config.track_memory_buffer):
            self.state = IdentityState.UNVERIFIED
            if match.is_known:
                self.identity_id = match.identity_id
                self.name = match.name
        else:
            self.state = IdentityState.UNKNOWN
            self.identity_id = "UNKNOWN"
            self.name = "Unknown Person"

        return AssociatedIdentity(
            track_id=self.track_id,
            camera_id=self.camera_id,
            identity_id=self.identity_id,
            name=self.name,
            state=self.state,
            similarity_score=round(sim, 4),
            recognition_confidence=round(rec_conf, 4),
            association_confidence=round(assoc_conf, 4),
            observations_count=self.observations_count,
            metadata={
                "avg_similarity": round(avg_sim, 4),
                "quality_score": round(qual, 4),
            },
        )

    def retain_memory(self, config: IdentityConfig) -> Optional[AssociatedIdentity]:
        self.frames_since_update += 1
        if self.frames_since_update > config.track_memory_buffer:
            return None

        # Retain previous identity with decaying confidence
        decay = max(0.2, 1.0 - (self.frames_since_update / float(config.track_memory_buffer)))
        state = IdentityState.UNVERIFIED if self.state == IdentityState.KNOWN else self.state

        return AssociatedIdentity(
            track_id=self.track_id,
            camera_id=self.camera_id,
            identity_id=self.identity_id,
            name=self.name,
            state=state,
            similarity_score=0.0,
            recognition_confidence=round(0.5 * decay, 4),
            association_confidence=round(0.5 * decay, 4),
            observations_count=self.observations_count,
            metadata={"retained_memory": True, "decay": round(decay, 2)},
        )


class MultiSignalIdentityAssociator:
    """
    Associates camera-scoped tracks with global identities using multi-signal memory.
    """

    def __init__(self, config: IdentityConfig) -> None:
        self._config = config
        self._track_histories: Dict[Tuple[str, int], TrackIdentityHistory] = {}

    def get_history(self, camera_id: str, track_id: int) -> TrackIdentityHistory:
        key = (camera_id, track_id)
        if key not in self._track_histories:
            self._track_histories[key] = TrackIdentityHistory(camera_id, track_id)
        return self._track_histories[key]

    def cleanup_stale(self, current_time: float, max_age_seconds: float = 60.0) -> int:
        """Purges stale track identity histories exceeding max_age_seconds."""
        stale_keys = [
            k for k, v in self._track_histories.items()
            if (current_time - v.last_updated_time) > max_age_seconds
        ]
        for k in stale_keys:
            del self._track_histories[k]
        return len(stale_keys)

    def reset(self, camera_id: Optional[str] = None) -> None:
        if camera_id is None:
            self._track_histories.clear()
        else:
            keys_to_del = [k for k in self._track_histories.keys() if k[0] == camera_id]
            for k in keys_to_del:
                del self._track_histories[k]
