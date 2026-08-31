"""
Face Recognition & Identity Association Subsystem for CIVIS.
"""

from civis.identity.models import (
    IdentityState,
    FaceCrop,
    FaceDetection,
    FaceDetectorBackend,
    FaceDetectorConfig,
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
from civis.identity.face_detector import (
    HeuristicFaceDetector,
    MockFaceDetector,
    YuNetFaceDetector,
    SCRFDFaceDetector,
    create_face_detector,
)
from civis.identity.quality import LaplacianFaceQuality
from civis.identity.gallery import MemoryIdentityGallery
from civis.identity.association import MultiSignalIdentityAssociator
from civis.identity.engine import IdentityEngine, MockIdentityEngine, DefaultFaceDetector
from civis.identity.factory import create_identity_engine

__all__ = [
    "IdentityState",
    "FaceCrop",
    "FaceDetection",
    "FaceDetectorBackend",
    "FaceDetectorConfig",
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
    "HeuristicFaceDetector",
    "MockFaceDetector",
    "YuNetFaceDetector",
    "SCRFDFaceDetector",
    "DefaultFaceDetector",
    "create_face_detector",
    "LaplacianFaceQuality",
    "MemoryIdentityGallery",
    "MultiSignalIdentityAssociator",
    "IdentityEngine",
    "MockIdentityEngine",
    "create_identity_engine",
]
