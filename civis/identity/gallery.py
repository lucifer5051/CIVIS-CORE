import logging
from typing import Dict, Optional, Tuple
import numpy as np

from civis.identity.base import BaseIdentityGallery
from civis.identity.models import FaceEmbedding, IdentityMatch

logger = logging.getLogger(__name__)


class MemoryIdentityGallery(BaseIdentityGallery):
    """
    In-memory vector gallery and cosine similarity search engine.
    Tags vectors with model_version and embedding dimension metadata.
    """

    def __init__(self) -> None:
        self._gallery: Dict[str, Tuple[str, np.ndarray, str]] = {}  # identity_id -> (name, normalized_vector, model_version)

    def add_identity(self, identity_id: str, name: str, embedding: np.ndarray, model_version: str = "v1.0") -> None:
        norm = np.linalg.norm(embedding)
        normalized = embedding / norm if norm > 0 else embedding
        self._gallery[identity_id] = (name, normalized, model_version)
        logger.info("Registered identity: %s (%s) [dim=%d, model=%s]", identity_id, name, len(embedding), model_version)

    def search(self, embedding: FaceEmbedding, threshold: float) -> Optional[IdentityMatch]:
        if not self._gallery:
            return None

        query_vec = embedding.embedding
        query_norm = np.linalg.norm(query_vec)
        if query_norm > 0:
            query_vec = query_vec / query_norm

        best_id: Optional[str] = None
        best_name: str = ""
        best_sim: float = -1.0

        for identity_id, (name, ref_vec, model_ver) in self._gallery.items():
            if model_ver != embedding.model_version:
                logger.debug("Skipping gallery search for %s due to model_version mismatch (%s vs %s)", identity_id, model_ver, embedding.model_version)
                continue

            # Cosine similarity
            sim = float(np.dot(query_vec, ref_vec))
            if sim > best_sim:
                best_sim = sim
                best_id = identity_id
                best_name = name

        if best_id is not None and best_sim >= threshold:
            return IdentityMatch(
                identity_id=best_id,
                name=best_name,
                similarity_score=round(best_sim, 4),
                is_known=True,
            )

        return IdentityMatch(
            identity_id="UNKNOWN",
            name="Unknown Person",
            similarity_score=round(max(0.0, best_sim), 4) if best_id is not None else 0.0,
            is_known=False,
        )
