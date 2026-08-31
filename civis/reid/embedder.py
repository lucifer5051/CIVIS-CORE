import logging
from typing import List, Optional
import cv2
import numpy as np
import torch

from civis.reid.base import BaseAppearanceEmbedder
from civis.reid.models import AppearanceEmbedding, ReIDEngineConfig
from civis.reid.osnet import build_osnet_x1_0

logger = logging.getLogger(__name__)


class OSNetEmbedder(BaseAppearanceEmbedder):
    """
    OSNet-based Person Appearance Feature Extractor.
    Extracts L2-normalized 512-d feature vectors from full-body person crops.
    """

    def __init__(self, config: Optional[ReIDEngineConfig] = None) -> None:
        cfg = config if config is not None else ReIDEngineConfig()
        self._config = cfg
        self._device = torch.device(cfg.device if torch.cuda.is_available() and cfg.device.startswith("cuda") else "cpu")
        self._model = build_osnet_x1_0(weights_path=cfg.weights_path).to(self._device)
        self._model.eval()

        # ImageNet normalization parameters
        self._mean = np.array([0.485, 0.456, 0.406], dtype=np.float32).reshape(1, 1, 3)
        self._std = np.array([0.229, 0.224, 0.225], dtype=np.float32).reshape(1, 1, 3)

    def _preprocess(self, crop: np.ndarray) -> Optional[torch.Tensor]:
        if crop is None or crop.size == 0:
            return None
        h, w = crop.shape[:2]
        if h < self._config.min_crop_height or w < self._config.min_crop_width:
            return None

        # Resize to standard Re-ID resolution (256, 128)
        resized = cv2.resize(crop, (128, 256), interpolation=cv2.INTER_LINEAR)
        if len(resized.shape) == 2:
            resized = cv2.cvtColor(resized, cv2.COLOR_GRAY2RGB)
        elif resized.shape[2] == 4:
            resized = cv2.cvtColor(resized, cv2.COLOR_BGRA2RGB)
        else:
            resized = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

        # Normalize [0, 1] then ImageNet mean/std
        img = resized.astype(np.float32) / 255.0
        img = (img - self._mean) / self._std
        # HWC -> CHW -> BCHW
        tensor = torch.from_numpy(img.transpose(2, 0, 1)).unsqueeze(0).to(self._device)
        return tensor

    def extract_embedding(
        self,
        crop_image: np.ndarray,
        camera_id: str,
        track_id: int,
        timestamp: float,
    ) -> Optional[AppearanceEmbedding]:
        tensor = self._preprocess(crop_image)
        if tensor is None:
            return None

        with torch.no_grad():
            feat = self._model(tensor, normalize=True)
            vec = feat.cpu().numpy().flatten()

        return AppearanceEmbedding(
            camera_id=camera_id,
            track_id=track_id,
            timestamp=timestamp,
            embedding=vec,
            dimension=512,
            quality_score=1.0,
            crop_dimensions=(crop_image.shape[1], crop_image.shape[0]),
        )

    def extract_batch(
        self,
        crops: List[np.ndarray],
        camera_ids: List[str],
        track_ids: List[int],
        timestamp: float,
    ) -> List[Optional[AppearanceEmbedding]]:
        tensors = []
        valid_indices = []

        for idx, crop in enumerate(crops):
            t = self._preprocess(crop)
            if t is not None:
                tensors.append(t)
                valid_indices.append(idx)

        results: List[Optional[AppearanceEmbedding]] = [None] * len(crops)
        if not tensors:
            return results

        batch = torch.cat(tensors, dim=0)
        with torch.no_grad():
            feats = self._model(batch, normalize=True).cpu().numpy()

        for f_idx, orig_idx in enumerate(valid_indices):
            vec = feats[f_idx]
            crop = crops[orig_idx]
            results[orig_idx] = AppearanceEmbedding(
                camera_id=camera_ids[orig_idx],
                track_id=track_ids[orig_idx],
                timestamp=timestamp,
                embedding=vec,
                dimension=512,
                quality_score=1.0,
                crop_dimensions=(crop.shape[1], crop.shape[0]),
            )

        return results


class MockAppearanceEmbedder(BaseAppearanceEmbedder):
    """
    Deterministic Mock Appearance Embedder for testing and simulation.
    Generates synthetic 512-d L2-normalized embeddings based on track identifiers and visual color signatures.
    """

    def __init__(self, config: Optional[ReIDEngineConfig] = None) -> None:
        self._config = config or ReIDEngineConfig(use_mock=True)

    def _generate_synthetic_vector(self, track_id: int, camera_id: str, crop: Optional[np.ndarray] = None) -> np.ndarray:
        # Seeded deterministic pseudo-random vector for consistent testing
        seed = abs(hash(f"track_{track_id}")) % (2**31 - 1)
        rng = np.random.RandomState(seed)
        vec = rng.randn(512).astype(np.float32)

        # Modulate slightly with mean color if crop is available
        if crop is not None and crop.size > 0:
            mean_color = crop.mean(axis=(0, 1)) / 255.0
            vec[:3] += mean_color.astype(np.float32)

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec

    def extract_embedding(
        self,
        crop_image: np.ndarray,
        camera_id: str,
        track_id: int,
        timestamp: float,
    ) -> Optional[AppearanceEmbedding]:
        if crop_image is not None and crop_image.size > 0:
            h, w = crop_image.shape[:2]
            if h < self._config.min_crop_height or w < self._config.min_crop_width:
                return None
            dims = (w, h)
        else:
            dims = (64, 128)

        vec = self._generate_synthetic_vector(track_id, camera_id, crop_image)
        return AppearanceEmbedding(
            camera_id=camera_id,
            track_id=track_id,
            timestamp=timestamp,
            embedding=vec,
            dimension=512,
            quality_score=1.0,
            crop_dimensions=dims,
        )

    def extract_batch(
        self,
        crops: List[np.ndarray],
        camera_ids: List[str],
        track_ids: List[int],
        timestamp: float,
    ) -> List[Optional[AppearanceEmbedding]]:
        return [
            self.extract_embedding(crops[i], camera_ids[i], track_ids[i], timestamp)
            for i in range(len(crops))
        ]
