from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class DiagnosticSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class SystemHealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"


@dataclass
class LogRecord:
    timestamp: float
    level: LogLevel
    component: str
    message: str
    camera_id: Optional[str] = None
    stage: Optional[str] = None
    event_type: Optional[str] = None
    error_details: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": round(self.timestamp, 4),
            "level": self.level.value,
            "component": self.component,
            "camera_id": self.camera_id,
            "stage": self.stage,
            "event_type": self.event_type,
            "message": self.message,
            "error_details": self.error_details,
            "metadata": self.metadata,
        }


@dataclass
class LatencySummary:
    count: int
    min_ms: float
    max_ms: float
    mean_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float


@dataclass
class DiagnosticFinding:
    finding_id: str
    severity: DiagnosticSeverity
    component: str
    message: str
    metric_value: float
    threshold: float
    timestamp: float = field(default_factory=time.time)
    camera_id: Optional[str] = None
    stage: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "severity": self.severity.value,
            "component": self.component,
            "camera_id": self.camera_id,
            "stage": self.stage,
            "message": self.message,
            "metric_value": self.metric_value,
            "threshold": self.threshold,
            "timestamp": round(self.timestamp, 4),
            "metadata": self.metadata,
        }


@dataclass
class ErrorRecord:
    error_type: str
    component: str
    camera_id: Optional[str]
    stage: Optional[str]
    count: int = 1
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    latest_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_type": self.error_type,
            "component": self.component,
            "camera_id": self.camera_id,
            "stage": self.stage,
            "count": self.count,
            "first_seen": round(self.first_seen, 4),
            "last_seen": round(self.last_seen, 4),
            "latest_message": self.latest_message,
        }


@dataclass
class SystemHealthSnapshot:
    status: SystemHealthStatus
    timestamp: float
    uptime_seconds: float
    active_cameras: int
    total_cameras: int
    camera_statuses: Dict[str, str] = field(default_factory=dict)
    diagnostic_findings: List[DiagnosticFinding] = field(default_factory=list)
    active_error_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OperationalReport:
    report_id: str
    generated_at: float
    system_status: SystemHealthStatus
    runtime_summary: Dict[str, Any]
    throughput_metrics: Dict[str, Any]
    latency_percentiles: Dict[str, LatencySummary]
    queue_statistics: Dict[str, Any]
    active_errors: List[ErrorRecord]
    diagnostic_findings: List[DiagnosticFinding]
    alert_statistics: Dict[str, Any]


class ObservabilityConfig(BaseModel):
    min_acceptable_fps: float = Field(default=15.0, ge=1.0, description="FPS below which warning finding triggers")
    max_stage_latency_ms: float = Field(default=50.0, ge=1.0, description="Stage latency threshold for degradation")
    max_queue_utilization_pct: float = Field(default=80.0, ge=10.0, le=100.0)
    max_error_count_threshold: int = Field(default=5, ge=1)
    frame_drop_warning_pct: float = Field(default=5.0, ge=0.5, le=100.0)
    rolling_sample_size: int = Field(default=200, ge=10, le=5000)
    max_log_buffer_size: int = Field(default=1000, ge=50)
    use_mock: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)
