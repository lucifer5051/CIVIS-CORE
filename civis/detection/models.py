from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field


class DetectionMode(str, Enum):
    FULL_FRAME = "full_frame"
    SLICED_ONLY = "sliced_only"
    HYBRID = "hybrid"
    AUTO = "auto"
    ADAPTIVE = "adaptive"


@dataclass
class BoundingBox:
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def center(self) -> Tuple[float, float]:
        return (self.x1 + self.width / 2.0, self.y1 + self.height / 2.0)

    @property
    def xywh(self) -> Tuple[float, float, float, float]:
        cx, cy = self.center
        return (cx, cy, self.width, self.height)

    def to_dict(self) -> Dict[str, float]:
        return {
            "x1": round(self.x1, 2),
            "y1": round(self.y1, 2),
            "x2": round(self.x2, 2),
            "y2": round(self.y2, 2),
            "width": round(self.width, 2),
            "height": round(self.height, 2),
        }


@dataclass
class Detection:
    class_id: int
    class_name: str
    confidence: float
    bbox: BoundingBox
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DetectionResult:
    camera_id: str
    frame_id: str
    timestamp: float
    frame_number: int
    dimensions: Tuple[int, int]  # (width, height)
    detections: List[Detection]
    inference_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def num_detections(self) -> int:
        return len(self.detections)


class SAHIConfig(BaseModel):
    slice_height: int = Field(default=320, ge=32, description="Slice height in pixels")
    slice_width: int = Field(default=320, ge=32, description="Slice width in pixels")
    overlap_height_ratio: float = Field(default=0.2, ge=0.0, lt=1.0, description="Height overlap ratio between slices")
    overlap_width_ratio: float = Field(default=0.2, ge=0.0, lt=1.0, description="Width overlap ratio between slices")
    mode: DetectionMode = Field(
        default=DetectionMode.HYBRID,
        description="Inference mode: full_frame, sliced_only, hybrid, auto, adaptive",
    )
    postprocess_match_threshold: float = Field(
        default=0.5, ge=0.0, le=1.0, description="NMS match threshold for merging overlapping slice predictions"
    )
    auto_min_dimension: int = Field(
        default=960, description="Minimum dimension to activate slicing when in AUTO/ADAPTIVE mode"
    )
    small_object_boost: bool = Field(
        default=True, description="Whether to prioritize low-confidence small objects in slices"
    )
    slice_conf_threshold: Optional[float] = Field(
        default=None, description="Optional slice-specific confidence threshold"
    )


class DetectorConfig(BaseModel):
    backend: str = Field(default="yolo12", description="Detector backend: 'yolo12', 'mock'")
    model_path: str = Field(default="yolo12n.pt", description="Path to YOLO12 weights or model name")
    conf_threshold: float = Field(default=0.25, ge=0.0, le=1.0, description="Confidence score threshold")
    iou_threshold: float = Field(default=0.45, ge=0.0, le=1.0, description="NMS IoU threshold")
    imgsz: int = Field(default=640, ge=32, description="Target input inference resolution")
    device: str = Field(default="cuda", description="Device hardware selection ('cuda', 'cpu', '0', etc.)")
    classes: Optional[List[int]] = Field(default=None, description="Optional class ID filter list")
    use_mock: bool = Field(default=False, description="Whether to use MockDetector for fast testing")
    sahi_config: Optional[SAHIConfig] = Field(default=None, description="Optional SAHI slicing configuration")
