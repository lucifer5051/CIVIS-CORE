import logging
import time
from typing import List, Optional
import numpy as np

from civis.identity.association import MultiSignalIdentityAssociator
from civis.identity.base import (
    BaseFaceAligner,
    BaseFaceDetector,
    BaseFaceEmbedder,
    BaseFaceQuality,
    BaseIdentityGallery,
)
from civis.identity.gallery import MemoryIdentityGallery
from civis.identity.models import (
    AssociatedIdentity,
    FaceCrop,
    FaceEmbedding,
    IdentityConfig,
    IdentityMatch,
    IdentityResult,
    IdentityState,
)
from civis.identity.quality import LaplacianFaceQuality
from civis.ingestion.models import FramePacket
from civis.tracking.models import TrackResult

logger = logging.getLogger(__name__)


from civis.identity.face_detector import (
    HeuristicFaceDetector,
    MockFaceDetector,
    create_face_detector,
)

# Backward-compatible alias
DefaultFaceDetector = HeuristicFaceDetector


class DefaultFaceAligner(BaseFaceAligner):
    def align_face(self, crop: FaceCrop) -> FaceCrop:
        # Default pass-through aligner
        return crop


class IdentityEngine:
    """
    Main Identity Association Pipeline Engine for CIVIS.
    Integrates Face Detection, Quality Validation, Alignment, Vector Embedding,
    Gallery Search, and Multi-Signal Track-to-Identity Association.
    """

    def __init__(
        self,
        config: Optional[IdentityConfig] = None,
        face_detector: Optional[BaseFaceDetector] = None,
        quality_assessor: Optional[BaseFaceQuality] = None,
        aligner: Optional[BaseFaceAligner] = None,
        embedder: Optional[BaseFaceEmbedder] = None,
        gallery: Optional[BaseIdentityGallery] = None,
    ) -> None:
        self._config = config if config is not None else IdentityConfig()
        self._detector = (
            face_detector
            if face_detector is not None
            else create_face_detector(self._config.detector)
        )
        self._quality = quality_assessor if quality_assessor is not None else LaplacianFaceQuality()
        self._aligner = aligner if aligner is not None else DefaultFaceAligner()
        self._embedder = embedder
        self._gallery = gallery if gallery is not None else MemoryIdentityGallery()
        self._associator = MultiSignalIdentityAssociator(self._config)

    @property
    def gallery(self) -> BaseIdentityGallery:
        return self._gallery

    def process(self, packet: FramePacket, track_result: TrackResult) -> IdentityResult:
        start_time = time.perf_counter()
        cam_id = packet.camera_id

        # 1. Detect faces from tracks
        face_crops = self._detector.detect_faces(packet, track_result)
        associated_identities: List[AssociatedIdentity] = []

        for crop in face_crops:
            # 2. Quality validation
            crop.quality_score = self._quality.assess_quality(crop)
            crop.is_valid = crop.quality_score >= self._config.min_quality_score

            history = self._associator.get_history(cam_id, crop.track_id)

            match: Optional[IdentityMatch] = None
            if crop.is_valid and self._embedder is not None:
                # 3. Alignment & Embedding
                aligned = self._aligner.align_face(crop)
                embedding = self._embedder.embed(aligned)

                if embedding is not None:
                    # 4. Gallery Search
                    match = self._gallery.search(embedding, self._config.similarity_threshold)

            if match is None:
                match = IdentityMatch(identity_id="UNKNOWN", name="Unknown Person", similarity_score=0.0, is_known=False)

            # 5. Multi-Signal Track-to-Identity Association
            assoc = history.update(
                match=match,
                quality_score=crop.quality_score,
                config=self._config,
                timestamp=packet.timestamp,
            )

            # Privacy & Biometric Data Release
            if not self._config.store_face_crops:
                crop.crop_img = None  # Release image tensor memory reference

            associated_identities.append(assoc)

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        return IdentityResult(
            camera_id=cam_id,
            frame_id=packet.frame_id,
            timestamp=packet.timestamp,
            frame_number=packet.frame_number,
            dimensions=packet.dimensions,
            identities=associated_identities,
            processing_time_ms=elapsed_ms,
            metadata={"engine": "IdentityEngine"},
        )


class MockFaceEmbedder(BaseFaceEmbedder):
    def __init__(self, dimension: int = 512, model_version: str = "mock-v1.0") -> None:
        self._dim = dimension
        self._version = model_version

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def model_version(self) -> str:
        return self._version

    def embed(self, crop: FaceCrop) -> Optional[FaceEmbedding]:
        if crop.crop_img is None or not crop.is_valid:
            return None
        # Deterministic vector derived from track_id
        vec = np.zeros(self._dim, dtype=np.float32)
        vec[crop.track_id % self._dim] = 1.0
        return FaceEmbedding(
            face_id=crop.face_id,
            embedding=vec,
            dimension=self._dim,
            model_version=self._version,
            norm=1.0,
        )


class MockIdentityEngine(IdentityEngine):
    """
    Mock Identity Engine for fast unit testing without neural weights.
    """

    def __init__(self, config: Optional[IdentityConfig] = None) -> None:
        cfg = config if config is not None else IdentityConfig(use_mock=True)
        embedder = MockFaceEmbedder()
        gallery = MemoryIdentityGallery()

        # Seed mock gallery identity
        mock_vec = np.zeros(512, dtype=np.float32)
        mock_vec[1] = 1.0  # Maps track 1
        gallery.add_identity(identity_id="ID_001_ALICE", name="Alice Smith", embedding=mock_vec, model_version="mock-v1.0")

        super().__init__(
            config=cfg,
            face_detector=MockFaceDetector(),
            quality_assessor=LaplacianFaceQuality(min_area=10, target_variance=1.0),  # Permissive quality for synthetic frames
            embedder=embedder,
            gallery=gallery,
        )
