import logging
import time
from typing import List, Optional
import numpy as np
import torch

from civis.detection.base import BaseDetector
from civis.detection.models import BoundingBox, Detection, DetectionResult, DetectorConfig
from civis.ingestion.models import FramePacket

logger = logging.getLogger(__name__)


class YOLO12Detector(BaseDetector):
    """
    YOLO12 Detection Engine implementation using Ultralytics framework.
    Consumes FramePacket objects directly from the ingestion module.
    """

    def __init__(self, config: DetectorConfig) -> None:
        super().__init__(config)
        self._device = self._resolve_device(config.device)
        self._model = self._load_model(config.model_path)

    def _resolve_device(self, requested_device: str) -> str:
        req = requested_device.lower().strip()
        cuda_ok = torch.cuda.is_available()

        if req in ("auto", ""):
            device = "cuda:0" if cuda_ok else "cpu"
        elif req in ("cuda", "gpu", "0", "cuda:0"):
            if not cuda_ok:
                logger.warning(
                    "CUDA explicitly requested but torch.cuda.is_available() is False. "
                    "Ensure torch+cu124 (or matching) is installed. Falling back to CPU."
                )
                device = "cpu"
            else:
                device = "cuda:0"
        else:
            device = requested_device  # cpu or explicit device string

        if cuda_ok and device.startswith("cuda"):
            gpu_name = torch.cuda.get_device_name(0)
            vram_mb = torch.cuda.get_device_properties(0).total_memory // (1024 * 1024)
            logger.info(
                "[GPU] INFERENCE DEVICE : %s | %s | VRAM: %d MB",
                device, gpu_name, vram_mb
            )
        else:
            logger.info("[CPU] INFERENCE DEVICE : cpu (CUDA unavailable or not selected)")

        return device

    def _load_model(self, model_path: str):
        from ultralytics import YOLO
        import numpy as np

        logger.info("Loading YOLO model: %s  →  device: %s", model_path, self._device)
        model = YOLO(model_path)

        # GPU warmup: run one dummy inference so CUDA kernels are compiled
        # before live frames arrive. Not counted as real inference time.
        if self._device.startswith("cuda"):
            try:
                dummy = np.zeros((640, 640, 3), dtype=np.uint8)
                model.predict(source=dummy, device=self._device, verbose=False, imgsz=640)
                logger.info("[GPU] Model warmup complete. YOLO ready on %s.", self._device)
            except Exception as exc:
                logger.warning("GPU warmup failed (non-fatal): %s", exc)
        else:
            logger.info("[CPU] Model loaded. No GPU warmup needed.")

        return model

    def detect(self, packet: FramePacket) -> DetectionResult:
        start_time = time.perf_counter()

        results = self._model.predict(
            source=packet.frame,
            conf=self._config.conf_threshold,
            iou=self._config.iou_threshold,
            imgsz=self._config.imgsz,
            device=self._device,
            classes=self._config.classes,
            verbose=False,
        )

        detections: List[Detection] = []

        for r in results:
            boxes = r.boxes
            if boxes is None:
                continue
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                conf = float(box.conf[0].item())
                cls_id = int(box.cls[0].item())
                cls_name = r.names.get(cls_id, str(cls_id)) if hasattr(r, "names") and r.names else str(cls_id)

                detections.append(
                    Detection(
                        class_id=cls_id,
                        class_name=cls_name,
                        confidence=conf,
                        bbox=BoundingBox(x1=float(x1), y1=float(y1), x2=float(x2), y2=float(y2)),
                    )
                )

        inference_time_ms = (time.perf_counter() - start_time) * 1000.0

        return DetectionResult(
            camera_id=packet.camera_id,
            frame_id=packet.frame_id,
            timestamp=packet.timestamp,
            frame_number=packet.frame_number,
            dimensions=packet.dimensions,
            detections=detections,
            inference_time_ms=inference_time_ms,
            metadata={
                "engine": "YOLO12Detector",
                "model_path": self._config.model_path,
                "device": self._device,
            },
        )
