import time
import uuid
from typing import Dict, List, Optional

from civis.observability.models import (
    DiagnosticFinding,
    DiagnosticSeverity,
    ObservabilityConfig,
)
from civis.runtime.models import RuntimeHealth, RuntimeMetrics, RuntimeState


class DiagnosticEngine:
    """
    Automated operational diagnostic engine. Evaluates runtime health against
    configured policies and generates structured DiagnosticFinding records.
    """

    def __init__(self, config: ObservabilityConfig) -> None:
        self.config = config

    def evaluate(
        self,
        health: RuntimeHealth,
        metrics: RuntimeMetrics,
        stage_latencies: Optional[Dict[str, float]] = None,
    ) -> List[DiagnosticFinding]:
        findings: List[DiagnosticFinding] = []

        # 1. Evaluate Cameras
        for cam_id, c_health in health.camera_health.items():
            # Check Low FPS
            if c_health.state == RuntimeState.RUNNING and c_health.frames_processed > 5:
                if c_health.current_fps > 0 and c_health.current_fps < self.config.min_acceptable_fps:
                    findings.append(DiagnosticFinding(
                        finding_id=f"diag_fps_{cam_id}_{uuid.uuid4().hex[:6]}",
                        severity=DiagnosticSeverity.WARNING,
                        component="camera_runtime",
                        camera_id=cam_id,
                        message=f"Camera {cam_id} throughput {c_health.current_fps:.1f} FPS is below threshold {self.config.min_acceptable_fps:.1f} FPS",
                        metric_value=c_health.current_fps,
                        threshold=self.config.min_acceptable_fps,
                    ))

            # Check Queue Depth & Utilization
            q_util = metrics.queue_utilization_pct.get(cam_id, 0.0)
            if q_util >= self.config.max_queue_utilization_pct:
                findings.append(DiagnosticFinding(
                    finding_id=f"diag_queue_{cam_id}_{uuid.uuid4().hex[:6]}",
                    severity=DiagnosticSeverity.WARNING,
                    component="bounded_queue",
                    camera_id=cam_id,
                    message=f"Camera {cam_id} frame queue utilization is high ({q_util:.1f}% >= {self.config.max_queue_utilization_pct:.1f}%)",
                    metric_value=q_util,
                    threshold=self.config.max_queue_utilization_pct,
                ))

            # Check Camera Errors
            if c_health.error_count >= self.config.max_error_count_threshold:
                findings.append(DiagnosticFinding(
                    finding_id=f"diag_err_{cam_id}_{uuid.uuid4().hex[:6]}",
                    severity=DiagnosticSeverity.ERROR,
                    component="camera_runtime",
                    camera_id=cam_id,
                    message=f"Camera {cam_id} encountered {c_health.error_count} repeated errors",
                    metric_value=float(c_health.error_count),
                    threshold=float(self.config.max_error_count_threshold),
                ))

            # Check Stage Latencies on this camera
            for stg_name, s_health in c_health.stages.items():
                if s_health.avg_latency_ms > self.config.max_stage_latency_ms:
                    findings.append(DiagnosticFinding(
                        finding_id=f"diag_lat_{cam_id}_{stg_name}_{uuid.uuid4().hex[:6]}",
                        severity=DiagnosticSeverity.WARNING,
                        component="pipeline_stage",
                        camera_id=cam_id,
                        stage=stg_name,
                        message=f"Stage '{stg_name}' latency on {cam_id} ({s_health.avg_latency_ms:.1f}ms) exceeds limit ({self.config.max_stage_latency_ms:.1f}ms)",
                        metric_value=s_health.avg_latency_ms,
                        threshold=self.config.max_stage_latency_ms,
                    ))

        # 2. Evaluate Global System Drop Rate
        if metrics.drop_rate_pct > self.config.frame_drop_warning_pct:
            findings.append(DiagnosticFinding(
                finding_id=f"diag_drop_global_{uuid.uuid4().hex[:6]}",
                severity=DiagnosticSeverity.WARNING,
                component="scheduler",
                message=f"System frame drop rate is elevated: {metrics.drop_rate_pct:.1f}% (limit: {self.config.frame_drop_warning_pct:.1f}%)",
                metric_value=metrics.drop_rate_pct,
                threshold=self.config.frame_drop_warning_pct,
            ))

        return findings
