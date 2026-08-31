from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from civis.observability.models import (
    DiagnosticFinding,
    ErrorRecord,
    LogLevel,
    LogRecord,
    ObservabilityConfig,
    OperationalReport,
    SystemHealthSnapshot,
)
from civis.runtime.models import RuntimeHealth, RuntimeMetrics


class BaseObservabilityEngine(ABC):
    """
    Abstract base class for CIVIS Observability, Metrics & Diagnostics layer.
    """

    def __init__(self, config: ObservabilityConfig) -> None:
        self._config = config

    @property
    def config(self) -> ObservabilityConfig:
        return self._config

    @abstractmethod
    def log(
        self,
        level: LogLevel,
        component: str,
        message: str,
        camera_id: Optional[str] = None,
        stage: Optional[str] = None,
        event_type: Optional[str] = None,
        error_details: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> LogRecord:
        """Emits a typed structured log record."""
        pass

    @abstractmethod
    def record_stage_latency(self, stage_name: str, latency_ms: float, camera_id: Optional[str] = None) -> None:
        """Records latency observation for quantile profiling."""
        pass

    @abstractmethod
    def record_error(
        self,
        error_type: str,
        component: str,
        message: str,
        camera_id: Optional[str] = None,
        stage: Optional[str] = None,
    ) -> ErrorRecord:
        """Aggregates an error occurrence."""
        pass

    @abstractmethod
    def evaluate_diagnostics(self, health: RuntimeHealth, metrics: RuntimeMetrics) -> List[DiagnosticFinding]:
        """Evaluates operational health against configured threshold policies."""
        pass

    @abstractmethod
    def get_system_health(self, runtime_health: Optional[RuntimeHealth] = None) -> SystemHealthSnapshot:
        """Returns unified system health snapshot."""
        pass

    @abstractmethod
    def generate_operational_report(
        self,
        runtime_health: RuntimeHealth,
        runtime_metrics: RuntimeMetrics,
    ) -> OperationalReport:
        """Generates comprehensive JSON-serializable operational report."""
        pass

    @abstractmethod
    def reset(self) -> None:
        """Resets all rolling buffers and metric counters."""
        pass
