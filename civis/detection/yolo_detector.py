import logging
import time
from typing import List, Optional
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
        if requested_device.lower() in ("cuda", "gpu", "0") and not torch.cuda.is_available():
            logger.warning("CUDA requested for YOLO12 detector, but CUDA is unavailable. Falling back to CPU.")
            return "cpu"
        return requested_device

    def _load_model(self, model_path: str):
        from ultralytics import YOLO

        logger.info("Loading YOLO model from: %s on device: %s", model_path, self._device)
        model = YOLO(model_path)
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
