"""
Face Recognition & Identity Association Subsystem for CIVIS.
"""

from civis.identity.models import (
    IdentityState,
    FaceCrop,
    FaceEmbedding,
    IdentityMatch,
    AssociatedIdentity,
    IdentityResult,
    IdentityConfig,
)
from civis.identity.base import (
    BaseFaceDetector,
    BaseFaceQuality,
    BaseFaceAligner,
    BaseFaceEmbedder,
    BaseIdentityGallery,
)
from civis.identity.quality import LaplacianFaceQuality
from civis.identity.gallery import MemoryIdentityGallery
from civis.identity.association import MultiSignalIdentityAssociator
from civis.identity.engine import IdentityEngine, MockIdentityEngine
from civis.identity.factory import create_identity_engine

__all__ = [
    "IdentityState",
    "FaceCrop",
    "FaceEmbedding",
    "IdentityMatch",
    "AssociatedIdentity",
    "IdentityResult",
    "IdentityConfig",
    "BaseFaceDetector",
    "BaseFaceQuality",
    "BaseFaceAligner",
    "BaseFaceEmbedder",
    "BaseIdentityGallery",
    "LaplacianFaceQuality",
    "MemoryIdentityGallery",
    "MultiSignalIdentityAssociator",
    "IdentityEngine",
    "MockIdentityEngine",
    "create_identity_engine",
]
