"""
Runtime Orchestration & Pipeline Execution Subsystem for CIVIS.
"""

from civis.runtime.base import BasePipelineRuntime, BasePipelineStage
from civis.runtime.camera_runtime import CameraRuntime
from civis.runtime.coordinator import CrossCameraCoordinator
from civis.runtime.engine import MockRuntimeEngine, RuntimeEngine
from civis.runtime.events import RuntimeEvent, RuntimeEventBus, RuntimeEventType
from civis.runtime.factory import create_runtime_engine
from civis.runtime.health import HealthMonitor, RollingStats
from civis.runtime.models import (
    CameraHealth,
    CameraRuntimeConfig,
    DropPolicy,
    PipelineRuntimeConfig,
    RuntimeHealth,
    RuntimeMetrics,
    RuntimeState,
    StageConfig,
    StageHealth,
    StageState,
)
from civis.runtime.pipeline import (
    BehaviorStage,
    DetectionStage,
    EventIntelligenceStage,
    EvidenceStage,
    IdentityStage,
    PipelineContext,
    ReIDStage,
    RiskAssessmentStage,
    SequentialPipeline,
    TrackingStage,
)
from civis.runtime.scheduler import BoundedFrameQueue

__all__ = [
    "RuntimeState",
    "StageState",
    "DropPolicy",
    "StageConfig",
    "CameraRuntimeConfig",
    "PipelineRuntimeConfig",
    "StageHealth",
    "CameraHealth",
    "RuntimeHealth",
    "RuntimeMetrics",
    "RuntimeEventType",
    "RuntimeEvent",
    "RuntimeEventBus",
    "RollingStats",
    "HealthMonitor",
    "BoundedFrameQueue",
    "PipelineContext",
    "BasePipelineStage",
    "DetectionStage",
    "TrackingStage",
    "IdentityStage",
    "ReIDStage",
    "BehaviorStage",
    "EventIntelligenceStage",
    "RiskAssessmentStage",
    "EvidenceStage",
    "SequentialPipeline",
    "CrossCameraCoordinator",
    "CameraRuntime",
    "BasePipelineRuntime",
    "RuntimeEngine",
    "MockRuntimeEngine",
    "create_runtime_engine",
]
