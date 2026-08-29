import cv2
import numpy as np

from civis.identity.base import BaseFaceQuality
from civis.identity.models import FaceCrop


class LaplacianFaceQuality(BaseFaceQuality):
    """
    Face quality validator measuring Laplacian sharpness variance and resolution bounds.
    """

    def __init__(self, min_area: int = 1600, target_variance: float = 100.0) -> None:
        self._min_area = min_area
        self._target_variance = target_variance

    def assess_quality(self, crop: FaceCrop) -> float:
        if crop.crop_img is None or crop.crop_img.size == 0:
            return 0.0

        height, width = crop.crop_img.shape[:2]
        area = width * height

        # Resolution score penalty for tiny crops
        res_score = min(1.0, area / float(self._min_area))

        # Sharpness score via Laplacian variance
        try:
            gray = cv2.cvtColor(crop.crop_img, cv2.COLOR_BGR2GRAY)
            lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            sharpness_score = min(1.0, lap_var / self._target_variance)
        except Exception:
            sharpness_score = 0.0

        # Weighted quality score
        quality = 0.5 * res_score + 0.5 * sharpness_score
        return float(np.clip(quality, 0.0, 1.0))
