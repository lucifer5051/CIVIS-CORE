import logging
import time
from typing import List, Optional
import numpy as np
from sahi.prediction import ObjectPrediction
from sahi.postprocess.combine import NMSPostprocess
from sahi.slicing import slice_image

from civis.detection.base import BaseDetector
from civis.detection.models import (
    BoundingBox,
    Detection,
    DetectionMode,
    DetectionResult,
    DetectorConfig,
    SAHIConfig,
)
from civis.ingestion.models import FramePacket

logger = logging.getLogger(__name__)


class SAHIDetector(BaseDetector):
    """
    SAHI (Slicing Aided Hyper Inference) Adapter for CIVIS.
    Wraps any BaseDetector (such as YOLO12Detector or MockDetector) to perform
    tiled sliced inference for high-resolution small-object detection.
    """

    def __init__(self, base_detector: BaseDetector, sahi_config: Optional[SAHIConfig] = None) -> None:
        cfg = sahi_config if sahi_config is not None else SAHIConfig()
        super().__init__(base_detector.config)
        self._base_detector = base_detector
        self._sahi_config = cfg

    @property
    def sahi_config(self) -> SAHIConfig:
        return self._sahi_config

    @property
    def base_detector(self) -> BaseDetector:
        return self._base_detector

    def detect(self, packet: FramePacket) -> DetectionResult:
        start_time = time.perf_counter()
        mode = self._sahi_config.mode

        # Mode 1: Full-Frame Mode
        if mode == DetectionMode.FULL_FRAME:
            res = self._base_detector.detect(packet)
            res.metadata["sahi_mode"] = mode.value
            return res

        all_detections: List[Detection] = []
        slice_count = 0

        # Mode 3: Hybrid Mode - Include Full-Frame Detection
        if mode == DetectionMode.HYBRID:
            full_frame_res = self._base_detector.detect(packet)
            all_detections.extend(full_frame_res.detections)

        # Mode 2 & 3: Sliced Inference
        sliced_detections, slice_count = self._run_sliced_inference(packet)
        all_detections.extend(sliced_detections)

        # Merge overlapping detections using official SAHI NMSPostprocess
        merged_detections = self._merge_detections(all_detections, packet.dimensions)

        inference_time_ms = (time.perf_counter() - start_time) * 1000.0

        return DetectionResult(
            camera_id=packet.camera_id,
            frame_id=packet.frame_id,
            timestamp=packet.timestamp,
            frame_number=packet.frame_number,
            dimensions=packet.dimensions,
            detections=merged_detections,
            inference_time_ms=inference_time_ms,
            metadata={
                "engine": "SAHIDetector",
                "base_engine": self._base_detector.__class__.__name__,
                "sahi_mode": mode.value,
                "slice_count": slice_count,
                "slice_height": self._sahi_config.slice_height,
                "slice_width": self._sahi_config.slice_width,
                "overlap_height_ratio": self._sahi_config.overlap_height_ratio,
                "overlap_width_ratio": self._sahi_config.overlap_width_ratio,
            },
        )

    def _run_sliced_inference(self, packet: FramePacket) -> tuple[List[Detection], int]:
        slice_result = slice_image(
            image=packet.frame,
            slice_height=self._sahi_config.slice_height,
            slice_width=self._sahi_config.slice_width,
            overlap_height_ratio=self._sahi_config.overlap_height_ratio,
            overlap_width_ratio=self._sahi_config.overlap_width_ratio,
            verbose=0,
        )

        slice_detections: List[Detection] = []
        slice_count = len(slice_result.images)

        for i in range(slice_count):
            crop_frame = slice_result.images[i]
            shift_x, shift_y = slice_result.starting_pixels[i]

            crop_packet = FramePacket.create(
                camera_id=packet.camera_id,
                frame_number=packet.frame_number,
                frame=crop_frame,
                timestamp=packet.timestamp,
                metadata={"slice_idx": i, "shift": (shift_x, shift_y)},
            )

            crop_res = self._base_detector.detect(crop_packet)

            # Map local crop coordinates (bx1, by1, bx2, by2) to global frame space
            for det in crop_res.detections:
                global_x1 = float(shift_x + det.bbox.x1)
                global_y1 = float(shift_y + det.bbox.y1)
                global_x2 = float(shift_x + det.bbox.x2)
                global_y2 = float(shift_y + det.bbox.y2)

                global_bbox = BoundingBox(x1=global_x1, y1=global_y1, x2=global_x2, y2=global_y2)
                slice_detections.append(
                    Detection(
                        class_id=det.class_id,
                        class_name=det.class_name,
                        confidence=det.confidence,
                        bbox=global_bbox,
                        metadata={"sliced": True, "slice_idx": i},
                    )
                )

        return slice_detections, slice_count

    def _merge_detections(self, detections: List[Detection], dimensions: tuple[int, int]) -> List[Detection]:
        if not detections:
            return []

        # Convert CIVIS Detections to SAHI ObjectPredictions for NMS merging
        object_predictions = []
        for det in detections:
            obj_pred = ObjectPrediction(
                bbox=[det.bbox.x1, det.bbox.y1, det.bbox.x2, det.bbox.y2],
                category_id=det.class_id,
                category_name=det.class_name,
                score=det.confidence,
            )
            object_predictions.append(obj_pred)

        # Apply official SAHI NMSPostprocess
        postprocessor = NMSPostprocess(
            match_metric="IOU",
            match_threshold=self._sahi_config.postprocess_match_threshold,
        )

        merged_object_predictions = postprocessor(object_predictions)

        # Convert back to CIVIS Detection objects
        merged_detections: List[Detection] = []
        for obj in merged_object_predictions:
            x1, y1, x2, y2 = obj.bbox.to_xyxy()
            merged_detections.append(
                Detection(
                    class_id=obj.category.id,
                    class_name=obj.category.name,
                    confidence=float(obj.score.value),
                    bbox=BoundingBox(x1=float(x1), y1=float(y1), x2=float(x2), y2=float(y2)),
                    metadata={"merged_by": "SAHI_NMS"},
                )
            )

        return merged_detections
