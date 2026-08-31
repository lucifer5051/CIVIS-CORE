import time
from typing import Dict, List, Optional

from civis.observability.models import (
    DiagnosticFinding,
    DiagnosticSeverity,
    ErrorRecord,
    SystemHealthSnapshot,
    SystemHealthStatus,
)
from civis.runtime.models import RuntimeHealth, RuntimeState


class SystemHealthAggregator:
    """
    Synthesizes multi-source operational signals into unified SystemHealthSnapshot.
    """

    @classmethod
    def aggregate(
        cls,
        runtime_health: Optional[RuntimeHealth],
        findings: List[DiagnosticFinding],
        errors: List[ErrorRecord],
        uptime_seconds: float = 0.0,
    ) -> SystemHealthSnapshot:
        now = time.time()
        active_cams = runtime_health.active_cameras if runtime_health else 0
        total_cams = runtime_health.total_cameras if runtime_health else 0
        cam_statuses = (
            {cid: h.state.value for cid, h in runtime_health.camera_health.items()}
            if runtime_health
            else {}
        )

        # Deterministic Status Calculation
        status = SystemHealthStatus.HEALTHY

        # 1. Critical/Error check
        has_critical_findings = any(
            f.severity in (DiagnosticSeverity.ERROR, DiagnosticSeverity.CRITICAL)
            for f in findings
        )
        has_runtime_error = (
            runtime_health is not None
            and (runtime_health.state == RuntimeState.ERROR or runtime_health.total_errors >= 10)
        )

        if has_critical_findings or has_runtime_error:
            status = SystemHealthStatus.UNHEALTHY
        elif findings or (runtime_health and any(h.error_count > 0 for h in runtime_health.camera_health.values())):
            status = SystemHealthStatus.DEGRADED

        return SystemHealthSnapshot(
            status=status,
            timestamp=now,
            uptime_seconds=uptime_seconds,
            active_cameras=active_cams,
            total_cameras=total_cams,
            camera_statuses=cam_statuses,
            diagnostic_findings=findings,
            active_error_count=len(errors),
            metadata={"evaluation_engine": "SystemHealthAggregator"},
        )
