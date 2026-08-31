from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field


class RuntimeState(str, Enum):
    CREATED = "created"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class StageState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    DEGRADED = "degraded"
    FAILED = "failed"
    DISABLED = "disabled"


class DropPolicy(str, Enum):
    DROP_OLDEST = "drop_oldest"  # Discards oldest queued frame to stay real-time
    DROP_NEWEST = "drop_newest"  # Discards newly arriving frame
    BLOCK = "block"              # Blocks until queue space becomes available


class StageConfig(BaseModel):
    name: str
    enabled: bool = True
    max_retries: int = Field(default=0, ge=0, description="Max retries upon stage exception")
    timeout_seconds: float = Field(default=5.0, ge=0.1, description="Max execution timeout per frame")
    custom_params: Dict[str, Any] = Field(default_factory=dict)


class CameraRuntimeConfig(BaseModel):
    camera_id: str
    name: str = ""
    source: str = ""
    target_fps: float = Field(default=30.0, ge=1.0)
    frame_interval: int = Field(default=1, ge=1, description="Process every N-th frame (frame skip)")
    queue_size: int = Field(default=10, ge=1, description="Bounded frame queue capacity")
    drop_policy: DropPolicy = DropPolicy.DROP_OLDEST
    device: str = Field(default="cpu", description="Compute device: 'cpu' or 'cuda:0'")
    auto_reconnect: bool = True
    max_reconnect_attempts: int = Field(default=5, ge=0)
    reconnect_delay_seconds: float = Field(default=2.0, ge=0.1)


class PipelineRuntimeConfig(BaseModel):
    cameras: List[CameraRuntimeConfig] = Field(default_factory=list)
    stages: Dict[str, StageConfig] = Field(default_factory=dict)
    enable_cross_camera_reid: bool = True
    enable_evidence_logging: bool = True
    max_worker_threads: int = Field(default=4, ge=1)
    graceful_shutdown_timeout_sec: float = Field(default=5.0, ge=0.5)
    use_mock: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


@dataclass
class StageHealth:
    stage_name: str
    state: StageState
    enabled: bool
    total_processed: int = 0
    total_errors: int = 0
    last_latency_ms: float = 0.0
    avg_latency_ms: float = 0.0
    last_error: Optional[str] = None
    last_success_timestamp: float = 0.0


@dataclass
class CameraHealth:
    camera_id: str
    state: RuntimeState
    is_connected: bool
    frames_received: int = 0
    frames_processed: int = 0
    frames_dropped: int = 0
    error_count: int = 0
    reconnect_count: int = 0
    current_fps: float = 0.0
    avg_latency_ms: float = 0.0
    queue_depth: int = 0
    last_frame_timestamp: float = 0.0
    stages: Dict[str, StageHealth] = field(default_factory=dict)


@dataclass
class RuntimeHealth:
    state: RuntimeState
    total_cameras: int
    active_cameras: int
    total_frames_received: int
    total_frames_processed: int
    total_frames_dropped: int
    total_errors: int
    uptime_seconds: float
    camera_health: Dict[str, CameraHealth] = field(default_factory=dict)


@dataclass
class RuntimeMetrics:
    total_cameras: int
    active_cameras: int
    total_frames_received: int
    total_frames_processed: int
    total_frames_dropped: int
    drop_rate_pct: float
    total_errors: int
    avg_pipeline_latency_ms: float
    per_camera_fps: Dict[str, float] = field(default_factory=dict)
    per_stage_latency_ms: Dict[str, float] = field(default_factory=dict)
    queue_utilization_pct: Dict[str, float] = field(default_factory=dict)
