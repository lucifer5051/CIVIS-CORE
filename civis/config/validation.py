from typing import List, Tuple

from civis.config.models import CIVISConfig

VALID_DEVICES = ("cpu", "cuda", "cuda:0", "cuda:1", "cuda:2", "cuda:3", "mps")


def validate_civis_config(config: CIVISConfig) -> Tuple[bool, List[str]]:
    """
    Performs comprehensive cross-subsystem validation.
    """
    errors: List[str] = []

    # 1. Device Validation
    dev = config.device.lower()
    if not (dev in VALID_DEVICES or dev.startswith("cuda:")):
        errors.append(f"Invalid compute device '{config.device}'. Must be one of {VALID_DEVICES} or 'cuda:<N>'")

    # 2. Camera Configuration Validation
    seen_cams = set()
    for idx, cam in enumerate(config.cameras):
        if not cam.camera_id:
            errors.append(f"Camera at index {idx} has an empty camera_id")
        elif cam.camera_id in seen_cams:
            errors.append(f"Duplicate camera_id '{cam.camera_id}' detected")
        seen_cams.add(cam.camera_id)

        if not str(cam.source).strip():
            errors.append(f"Camera '{cam.camera_id}' has an empty stream source")

    # 3. Detection & Re-ID Thresholds
    if hasattr(config.detection, "conf_threshold"):
        thresh = config.detection.conf_threshold
        if not (0.0 <= thresh <= 1.0):
            errors.append(f"Detection confidence threshold ({thresh}) must be between 0.0 and 1.0")

    if hasattr(config.reid, "similarity_threshold"):
        r_thresh = config.reid.similarity_threshold
        if not (0.0 <= r_thresh <= 1.0):
            errors.append(f"Re-ID similarity threshold ({r_thresh}) must be between 0.0 and 1.0")

    # 4. Observability Thresholds
    if config.observability.min_acceptable_fps <= 0:
        errors.append(f"Observability min_acceptable_fps ({config.observability.min_acceptable_fps}) must be > 0")

    # 5. Policy Priority Validation
    for p in config.policies:
        if not (1 <= p.priority <= 100):
            errors.append(f"Policy '{p.policy_id}' priority ({p.priority}) must be between 1 and 100")

    is_valid = len(errors) == 0
    return is_valid, errors
