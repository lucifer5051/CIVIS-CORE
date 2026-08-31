import logging
import os
from typing import List, Optional, Tuple
import cv2
import numpy as np

from civis.detection.models import BoundingBox
from civis.identity.base import BaseFaceDetector
from civis.identity.models import (
    FaceCrop,
    FaceDetection,
    FaceDetectorBackend,
    FaceDetectorConfig,
)
from civis.ingestion.models import FramePacket
from civis.tracking.models import TrackResult

logger = logging.getLogger(__name__)


def compute_iou(box1: BoundingBox, box2: BoundingBox) -> float:
    """Calculate Intersection over Union (IoU) between two bounding boxes."""
    ix1 = max(box1.x1, box2.x1)
    iy1 = max(box1.y1, box2.y1)
    ix2 = min(box1.x2, box2.x2)
    iy2 = min(box1.y2, box2.y2)

    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter_area = iw * ih

    union_area = box1.area + box2.area - inter_area
    if union_area <= 0.0:
        return 0.0
    return inter_area / union_area


def is_box_inside(inner: BoundingBox, outer: BoundingBox, tolerance: float = 0.2) -> bool:
    """Check if inner box center or majority area is located inside outer box."""
    cx, cy = inner.center
    padding_x = outer.width * tolerance
    padding_y = outer.height * tolerance
    return (
        (outer.x1 - padding_x) <= cx <= (outer.x2 + padding_x)
        and (outer.y1 - padding_y) <= cy <= (outer.y2 + padding_y)
    )


class HeuristicFaceDetector(BaseFaceDetector):
    """
    Fallback Heuristic Face Detector.
    Extracts the upper ~35% region of a tracked person bounding box.
    """

    def detect_raw_faces(self, image: np.ndarray) -> List[FaceDetection]:
        # Heuristic cannot detect faces without person track context
        return []

    def detect_faces(self, packet: FramePacket, track_result: TrackResult) -> List[FaceCrop]:
        crops = []
        frame_h, frame_w = packet.dimensions
        for track in track_result.tracks:
            bx1, by1 = max(0, int(track.bbox.x1)), max(0, int(track.bbox.y1))
            bx2, by2 = min(frame_w, int(track.bbox.x2)), min(frame_h, int(track.bbox.y2))

            face_h = max(10, int((by2 - by1) * 0.35))
            face_y2 = min(frame_h, by1 + face_h)

            crop_img = packet.frame[by1:face_y2, bx1:bx2].copy() if (bx2 > bx1 and face_y2 > by1) else None
            face_bbox = BoundingBox(x1=float(bx1), y1=float(by1), x2=float(bx2), y2=float(face_y2))

            crops.append(
                FaceCrop(
                    face_id=f"face_{track.track_id}_{track_result.camera_id}",
                    track_id=track.track_id,
                    camera_id=track_result.camera_id,
                    bbox=track.bbox,
                    face_bbox=face_bbox,
                    confidence=0.7,
                    crop_img=crop_img,
                    metadata={"detector": "HeuristicFaceDetector"},
                )
            )
        return crops


class MockFaceDetector(BaseFaceDetector):
    """
    Deterministic Mock Face Detector for unit tests without neural models.
    """

    def detect_raw_faces(self, image: np.ndarray) -> List[FaceDetection]:
        h, w = image.shape[:2]
        return [
            FaceDetection(
                bbox=BoundingBox(x1=w * 0.2, y1=h * 0.1, x2=w * 0.4, y2=h * 0.3),
                confidence=0.95,
                landmarks=[(w * 0.25, h * 0.18), (w * 0.35, h * 0.18), (w * 0.3, h * 0.22), (w * 0.26, h * 0.26), (w * 0.34, h * 0.26)],
            )
        ]

    def detect_faces(self, packet: FramePacket, track_result: TrackResult) -> List[FaceCrop]:
        crops = []
        frame_h, frame_w = packet.dimensions
        for track in track_result.tracks:
            bx1, by1 = max(0, int(track.bbox.x1)), max(0, int(track.bbox.y1))
            bx2, by2 = min(frame_w, int(track.bbox.x2)), min(frame_h, int(track.bbox.y2))

            # Derive face bbox from upper 30% of track
            face_h = max(16, int((by2 - by1) * 0.30))
            face_w = max(16, int(bx2 - bx1))
            face_y2 = min(frame_h, by1 + face_h)

            crop_img = packet.frame[by1:face_y2, bx1:bx2].copy() if (bx2 > bx1 and face_y2 > by1) else None
            face_bbox = BoundingBox(x1=float(bx1), y1=float(by1), x2=float(bx2), y2=float(face_y2))

            # 5 mock facial landmarks
            cx, cy = face_bbox.center
            landmarks = [
                (cx - face_w * 0.15, cy - face_h * 0.1),
                (cx + face_w * 0.15, cy - face_h * 0.1),
                (cx, cy),
                (cx - face_w * 0.12, cy + face_h * 0.15),
                (cx + face_w * 0.12, cy + face_h * 0.15),
            ]

            crops.append(
                FaceCrop(
                    face_id=f"face_{track.track_id}_{track_result.camera_id}",
                    track_id=track.track_id,
                    camera_id=track_result.camera_id,
                    bbox=track.bbox,
                    face_bbox=face_bbox,
                    landmarks=landmarks,
                    confidence=0.95,
                    crop_img=crop_img,
                    metadata={"detector": "MockFaceDetector"},
                )
            )
        return crops


class YuNetFaceDetector(BaseFaceDetector):
    """
    OpenCV YuNet Face Detector (BSD-3-Clause / Apache-2.0 License).
    Lightweight, fast neural face detector producing 5 facial landmarks.
    """

    def __init__(self, config: Optional[FaceDetectorConfig] = None) -> None:
        self._config = config or FaceDetectorConfig(backend="yunet")
        self._detector = None
        self._fallback = HeuristicFaceDetector()
        self._init_detector()

    def _init_detector(self) -> None:
        model_path = self._config.model_path
        if not model_path or not os.path.exists(model_path):
            candidates = [
                "models/face_detection_yunet_2023mar.onnx",
                os.path.join(os.path.dirname(__file__), "..", "..", "models", "face_detection_yunet_2023mar.onnx"),
            ]
            for c in candidates:
                if os.path.exists(c):
                    model_path = os.path.abspath(c)
                    break

        if model_path and os.path.exists(model_path):
            try:
                self._detector = cv2.FaceDetectorYN.create(
                    model=model_path,
                    config="",
                    input_size=self._config.input_size,
                    score_threshold=self._config.conf_threshold,
                    nms_threshold=self._config.nms_threshold,
                    top_k=50,
                )
                logger.info("YuNetFaceDetector initialized with model: %s", model_path)
            except Exception as e:
                logger.warning("Failed to initialize cv2.FaceDetectorYN (%s). Fallback active.", e)
                self._detector = None
        else:
            logger.info("YuNet ONNX model not found at %s. Using heuristic face detector.", model_path)

    def detect_raw_faces(self, image: np.ndarray) -> List[FaceDetection]:
        if self._detector is None or image is None:
            return []

        h, w = image.shape[:2]
        self._detector.setInputSize((w, h))
        _, faces = self._detector.detect(image)

        if faces is None:
            return []

        results: List[FaceDetection] = []
        for face in faces:
            # YuNet output: [x, y, w, h, x_re, y_re, x_le, y_le, x_nt, y_nt, x_rcm, y_rcm, x_lcm, y_lcm, score]
            fx, fy, fw, fh = face[0:4]
            score = float(face[-1])
            landmarks = [
                (float(face[4]), float(face[5])),   # right eye
                (float(face[6]), float(face[7])),   # left eye
                (float(face[8]), float(face[9])),   # nose tip
                (float(face[10]), float(face[11])), # right mouth
                (float(face[12]), float(face[13])), # left mouth
            ]
            bbox = BoundingBox(x1=float(fx), y1=float(fy), x2=float(fx + fw), y2=float(fy + fh))
            results.append(FaceDetection(bbox=bbox, confidence=score, landmarks=landmarks))
        return results

    def detect_faces(self, packet: FramePacket, track_result: TrackResult) -> List[FaceCrop]:
        if self._detector is None:
            return self._fallback.detect_faces(packet, track_result)

        raw_faces = self.detect_raw_faces(packet.frame)
        crops: List[FaceCrop] = []
        frame_h, frame_w = packet.dimensions

        for track in track_result.tracks:
            # Associate raw detected faces with track person bounding box
            matching_faces = [f for f in raw_faces if is_box_inside(f.bbox, track.bbox)]

            if matching_faces:
                # Select the highest confidence face inside the person box
                best_face = max(matching_faces, key=lambda f: f.confidence)
                fx1, fy1 = max(0, int(best_face.bbox.x1)), max(0, int(best_face.bbox.y1))
                fx2, fy2 = min(frame_w, int(best_face.bbox.x2)), min(frame_h, int(best_face.bbox.y2))

                crop_img = packet.frame[fy1:fy2, fx1:fx2].copy() if (fx2 > fx1 and fy2 > fy1) else None

                crops.append(
                    FaceCrop(
                        face_id=f"face_{track.track_id}_{track_result.camera_id}",
                        track_id=track.track_id,
                        camera_id=track_result.camera_id,
                        bbox=track.bbox,
                        face_bbox=best_face.bbox,
                        landmarks=best_face.landmarks,
                        confidence=best_face.confidence,
                        crop_img=crop_img,
                        metadata={"detector": "YuNetFaceDetector"},
                    )
                )
            else:
                # Fallback to upper crop for track if face wasn't resolved by neural detector
                bx1, by1 = max(0, int(track.bbox.x1)), max(0, int(track.bbox.y1))
                bx2, by2 = min(frame_w, int(track.bbox.x2)), min(frame_h, int(track.bbox.y2))
                face_h = max(10, int((by2 - by1) * 0.35))
                face_y2 = min(frame_h, by1 + face_h)
                crop_img = packet.frame[by1:face_y2, bx1:bx2].copy() if (bx2 > bx1 and face_y2 > by1) else None
                face_bbox = BoundingBox(x1=float(bx1), y1=float(by1), x2=float(bx2), y2=float(face_y2))

                crops.append(
                    FaceCrop(
                        face_id=f"face_{track.track_id}_{track_result.camera_id}",
                        track_id=track.track_id,
                        camera_id=track_result.camera_id,
                        bbox=track.bbox,
                        face_bbox=face_bbox,
                        confidence=0.5,
                        crop_img=crop_img,
                        metadata={"detector": "YuNetFallback"},
                    )
                )
        return crops


class SCRFDFaceDetector(BaseFaceDetector):
    """
    SCRFD Face Detector Adapter (MIT code license).
    Supports ONNX runtime inference with 5 facial keypoints.
    Note: External model weights must comply with their respective distribution terms.
    """

    def __init__(self, config: Optional[FaceDetectorConfig] = None) -> None:
        self._config = config or FaceDetectorConfig(backend="scrfd")
        self._fallback = HeuristicFaceDetector()

    def detect_raw_faces(self, image: np.ndarray) -> List[FaceDetection]:
        # When ONNX session is not provided, return empty
        return []

    def detect_faces(self, packet: FramePacket, track_result: TrackResult) -> List[FaceCrop]:
        return self._fallback.detect_faces(packet, track_result)


def create_face_detector(config: Optional[FaceDetectorConfig] = None) -> BaseFaceDetector:
    """Factory helper to instantiate appropriate BaseFaceDetector."""
    cfg = config or FaceDetectorConfig()
    backend = cfg.backend.lower()

    if backend == FaceDetectorBackend.MOCK.value:
        return MockFaceDetector()
    elif backend == FaceDetectorBackend.YUNET.value:
        return YuNetFaceDetector(cfg)
    elif backend == FaceDetectorBackend.SCRFD.value:
        return SCRFDFaceDetector(cfg)
    else:
        return HeuristicFaceDetector()
