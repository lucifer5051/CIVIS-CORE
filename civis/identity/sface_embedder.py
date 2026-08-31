import logging
import os
from typing import Optional
import cv2
import numpy as np

from civis.identity.base import BaseFaceEmbedder
from civis.identity.models import FaceCrop, FaceEmbedding

logger = logging.getLogger(__name__)


class SFaceFaceEmbedder(BaseFaceEmbedder):
    """
    OpenCV SFace Facial Feature Extractor (BSD-3-Clause / Apache-2.0 License).
    Extracts L2-normalized 128-dimensional facial embedding vectors from face crops
    using MobileFaceNet architecture (SFace).
    """

    def __init__(self, model_path: Optional[str] = None) -> None:
        self._dim = 128
        self._model_version = "sface-2021dec"
        self._recognizer = None

        resolved_path = model_path
        if not resolved_path or not os.path.exists(resolved_path):
            candidates = [
                "models/face_recognition_sface_2021dec.onnx",
                os.path.join(os.path.dirname(__file__), "..", "..", "models", "face_recognition_sface_2021dec.onnx"),
            ]
            for c in candidates:
                if os.path.exists(c):
                    resolved_path = os.path.abspath(c)
                    break

        if resolved_path and os.path.exists(resolved_path) and hasattr(cv2, "FaceRecognizerSF"):
            try:
                self._recognizer = cv2.FaceRecognizerSF.create(model=resolved_path, config="")
                logger.info("SFaceFaceEmbedder initialized with model: %s", resolved_path)
            except Exception as e:
                logger.warning("Failed to initialize cv2.FaceRecognizerSF (%s). Face embedding disabled.", e)
                self._recognizer = None
        else:
            logger.info("SFace model not found at %s. Face embedding disabled.", resolved_path)

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def model_version(self) -> str:
        return self._model_version

    def embed(self, crop: FaceCrop) -> Optional[FaceEmbedding]:
        if self._recognizer is None or crop.crop_img is None or crop.crop_img.size == 0:
            return None

        try:
            h, w = crop.crop_img.shape[:2]
            if h < 16 or w < 16:
                return None

            # SFace expects 112x112 input
            resized = cv2.resize(crop.crop_img, (112, 112), interpolation=cv2.INTER_LINEAR)
            raw_feat = self._recognizer.feature(resized)

            if raw_feat is None or raw_feat.size == 0:
                return None

            feat_vec = raw_feat.flatten().astype(np.float32)
            norm = float(np.linalg.norm(feat_vec))
            if norm > 0:
                feat_vec = feat_vec / norm

            return FaceEmbedding(
                face_id=crop.face_id,
                embedding=feat_vec,
                dimension=self._dim,
                model_version=self._model_version,
                norm=norm,
                metadata={"detector": crop.metadata.get("detector", "unknown")},
            )
        except Exception as e:
            logger.debug("Failed to extract face embedding: %s", e)
            return None
