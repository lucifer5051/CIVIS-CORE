from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from civis.runtime.models import (
    CameraHealth,
    PipelineRuntimeConfig,
    RuntimeHealth,
    RuntimeMetrics,
    StageHealth,
    StageState,
)


class BasePipelineStage(ABC):
    """
    Abstract base class for a modular CIVIS pipeline stage.
    Provides standard execution, timing, error isolation, and health hooks.
    """

    def __init__(self, name: str, enabled: bool = True) -> None:
        self._name = name
        self._enabled = enabled
        self._state = StageState.IDLE if enabled else StageState.DISABLED
        self._total_processed: int = 0
        self._total_errors: int = 0
        self._last_latency_ms: float = 0.0
        self._total_latency_ms: float = 0.0
        self._last_error: Optional[str] = None
        self._last_success_timestamp: float = 0.0

    @property
    def name(self) -> str:
        return self._name

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value
        self._state = StageState.IDLE if value else StageState.DISABLED

    @property
    def state(self) -> StageState:
        return self._state

    def get_health(self) -> StageHealth:
        avg_lat = (self._total_latency_ms / self._total_processed) if self._total_processed > 0 else 0.0
        return StageHealth(
            stage_name=self._name,
            state=self._state,
            enabled=self._enabled,
            total_processed=self._total_processed,
            total_errors=self._total_errors,
            last_latency_ms=round(self._last_latency_ms, 2),
            avg_latency_ms=round(avg_lat, 2),
            last_error=self._last_error,
            last_success_timestamp=self._last_success_timestamp,
        )

    def record_success(self, latency_ms: float, timestamp: float) -> None:
        self._state = StageState.IDLE if self._enabled else StageState.DISABLED
        self._total_processed += 1
        self._last_latency_ms = latency_ms
        self._total_latency_ms += latency_ms
        self._last_success_timestamp = timestamp
        self._last_error = None

    def record_failure(self, error_msg: str) -> None:
        self._state = StageState.FAILED
        self._total_errors += 1
        self._last_error = error_msg

    @abstractmethod
    def process(self, context: Any) -> Any:
        """Processes the pipeline context and enriches it with the stage's output."""
        pass

    def reset(self) -> None:
        self._state = StageState.IDLE if self._enabled else StageState.DISABLED
        self._total_processed = 0
        self._total_errors = 0
        self._last_latency_ms = 0.0
        self._total_latency_ms = 0.0
        self._last_error = None
        self._last_success_timestamp = 0.0


class BasePipelineRuntime(ABC):
    """
    Abstract base class for the CIVIS multi-camera runtime engine.
    """

    def __init__(self, config: PipelineRuntimeConfig) -> None:
        self._config = config

    @property
    def config(self) -> PipelineRuntimeConfig:
        return self._config

    @abstractmethod
    def start(self) -> None:
        """Starts all camera pipelines and worker threads."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Gracefully stops all camera pipelines and releases resources."""
        pass

    @abstractmethod
    def pause(self) -> None:
        """Pauses frame processing across all cameras."""
        pass

    @abstractmethod
    def resume(self) -> None:
        """Resumes frame processing across all cameras."""
        pass

    @abstractmethod
    def get_health(self) -> RuntimeHealth:
        """Returns structured health information for all cameras and stages."""
        pass

    @abstractmethod
    def get_metrics(self) -> RuntimeMetrics:
        """Returns aggregate execution and throughput metrics."""
        pass
