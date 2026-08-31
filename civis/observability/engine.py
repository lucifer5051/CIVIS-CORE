import threading
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from civis.observability.base import BaseObservabilityEngine
from civis.observability.diagnostics import DiagnosticEngine
from civis.observability.health import SystemHealthAggregator
from civis.observability.logging import StructuredLogger
from civis.observability.metrics import MetricsRegistry
from civis.observability.models import (
    DiagnosticFinding,
    ErrorRecord,
    LogLevel,
    LogRecord,
    ObservabilityConfig,
    OperationalReport,
    SystemHealthSnapshot,
)
from civis.observability.profiler import PipelineProfiler
from civis.runtime.base import BasePipelineRuntime
from civis.runtime.events import RuntimeEvent, RuntimeEventType
from civis.runtime.models import RuntimeHealth, RuntimeMetrics


class ObservabilityEngine(BaseObservabilityEngine):
    """
    Unified Observability, Monitoring & Operational Diagnostics Engine for CIVIS.
    Provides structured logging, metrics, latency percentiles, error aggregation,
    and automatic diagnostic threshold evaluation.
    """

    def __init__(self, config: Optional[ObservabilityConfig] = None) -> None:
        cfg = config if config is not None else ObservabilityConfig()
        super().__init__(cfg)

        self._start_time = time.time()
        self.logger = StructuredLogger(max_buffer_size=cfg.max_log_buffer_size)
        self.metrics = MetricsRegistry(default_sample_size=cfg.rolling_sample_size)
        self.profiler = PipelineProfiler(self.metrics)
        self.diagnostics = DiagnosticEngine(cfg)

        self._errors: Dict[Tuple[str, str, Optional[str], Optional[str]], ErrorRecord] = {}
        self._error_lock = threading.Lock()

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
        return self.logger.log(
            level=level,
            component=component,
            message=message,
            camera_id=camera_id,
            stage=stage,
            event_type=event_type,
            error_details=error_details,
            metadata=metadata,
        )

    def record_stage_latency(self, stage_name: str, latency_ms: float, camera_id: Optional[str] = None) -> None:
        self.profiler.record_latency(stage_name, latency_ms, camera_id)

    def record_error(
        self,
        error_type: str,
        component: str,
        message: str,
        camera_id: Optional[str] = None,
        stage: Optional[str] = None,
    ) -> ErrorRecord:
        key = (error_type, component, camera_id, stage)
        now = time.time()

        with self._error_lock:
            if key not in self._errors:
                record = ErrorRecord(
                    error_type=error_type,
                    component=component,
                    camera_id=camera_id,
                    stage=stage,
                    count=1,
                    first_seen=now,
                    last_seen=now,
                    latest_message=message,
                )
                self._errors[key] = record
            else:
                record = self._errors[key]
                record.count += 1
                record.last_seen = now
                record.latest_message = message

        self.metrics.counter(f"errors_total_{component}").inc()
        self.log(
            level=LogLevel.ERROR,
            component=component,
            message=message,
            camera_id=camera_id,
            stage=stage,
            error_details=error_type,
        )
        return record

    def get_active_errors(self) -> List[ErrorRecord]:
        with self._error_lock:
            return list(self._errors.values())

    def attach_runtime(self, runtime: BasePipelineRuntime) -> None:
        """
        Subscribes to operational runtime events to automatically track metrics and errors.
        """
        if not hasattr(runtime, "event_bus"):
            return

        def _handle_event(ev: RuntimeEvent) -> None:
            if ev.event_type == RuntimeEventType.FRAME_DROPPED:
                self.metrics.counter(f"frames_dropped_{ev.camera_id or 'global'}").inc()
                self.log(LogLevel.WARNING, "scheduler", ev.message, camera_id=ev.camera_id, event_type=ev.event_type.value)

            elif ev.event_type in (RuntimeEventType.STAGE_FAILED, RuntimeEventType.CAMERA_ERROR):
                self.record_error(
                    error_type=ev.event_type.value,
                    component="runtime",
                    message=ev.message,
                    camera_id=ev.camera_id,
                    stage=ev.stage_name,
                )

            elif ev.event_type == RuntimeEventType.CAMERA_STARTED:
                self.log(LogLevel.INFO, "runtime", ev.message, camera_id=ev.camera_id, event_type=ev.event_type.value)

        runtime.event_bus.subscribe(None, _handle_event)

    def evaluate_diagnostics(
        self,
        health: RuntimeHealth,
        metrics: RuntimeMetrics,
    ) -> List[DiagnosticFinding]:
        return self.diagnostics.evaluate(health, metrics)

    def get_system_health(self, runtime_health: Optional[RuntimeHealth] = None) -> SystemHealthSnapshot:
        findings: List[DiagnosticFinding] = []
        if runtime_health is not None:
            tot_recv = runtime_health.total_frames_received
            drop_rate = (runtime_health.total_frames_dropped / tot_recv * 100.0) if tot_recv > 0 else 0.0
            metrics = RuntimeMetrics(
                total_cameras=runtime_health.total_cameras,
                active_cameras=runtime_health.active_cameras,
                total_frames_received=runtime_health.total_frames_received,
                total_frames_processed=runtime_health.total_frames_processed,
                total_frames_dropped=runtime_health.total_frames_dropped,
                drop_rate_pct=round(drop_rate, 2),
                total_errors=runtime_health.total_errors,
                avg_pipeline_latency_ms=0.0,
                queue_utilization_pct={cid: round(h.queue_depth * 10.0, 1) for cid, h in runtime_health.camera_health.items()},
            )
            findings = self.evaluate_diagnostics(runtime_health, metrics)

        active_errors = self.get_active_errors()
        uptime = time.time() - self._start_time

        return SystemHealthAggregator.aggregate(
            runtime_health=runtime_health,
            findings=findings,
            errors=active_errors,
            uptime_seconds=round(uptime, 1),
        )

    def generate_operational_report(
        self,
        runtime_health: RuntimeHealth,
        runtime_metrics: RuntimeMetrics,
    ) -> OperationalReport:
        report_id = f"op_rep_{uuid.uuid4().hex[:8]}"
        now = time.time()

        findings = self.evaluate_diagnostics(runtime_health, runtime_metrics)
        errors = self.get_active_errors()
        health_snapshot = SystemHealthAggregator.aggregate(
            runtime_health=runtime_health,
            findings=findings,
            errors=errors,
            uptime_seconds=runtime_health.uptime_seconds,
        )

        stage_summaries = self.profiler.get_stage_summaries()

        return OperationalReport(
            report_id=report_id,
            generated_at=now,
            system_status=health_snapshot.status,
            runtime_summary={
                "state": runtime_health.state.value,
                "uptime_seconds": runtime_health.uptime_seconds,
                "total_cameras": runtime_health.total_cameras,
                "active_cameras": runtime_health.active_cameras,
            },
            throughput_metrics={
                "total_received": runtime_health.total_frames_received,
                "total_processed": runtime_health.total_frames_processed,
                "total_dropped": runtime_health.total_frames_dropped,
                "drop_rate_pct": runtime_metrics.drop_rate_pct,
                "per_camera_fps": runtime_metrics.per_camera_fps,
            },
            latency_percentiles=stage_summaries,
            queue_statistics={
                "queue_utilization_pct": runtime_metrics.queue_utilization_pct,
            },
            active_errors=errors,
            diagnostic_findings=findings,
            alert_statistics={
                "total_pipeline_errors": runtime_health.total_errors,
                "active_error_types": len(errors),
            },
        )

    def reset(self) -> None:
        self.logger.clear()
        self.metrics.reset()
        with self._error_lock:
            self._errors.clear()
        self._start_time = time.time()


class MockObservabilityEngine(ObservabilityEngine):
    """
    Deterministic Mock Observability Engine for testing without background overhead.
    """

    def __init__(self, config: Optional[ObservabilityConfig] = None) -> None:
        cfg = config if config is not None else ObservabilityConfig(use_mock=True)
        super().__init__(cfg)
