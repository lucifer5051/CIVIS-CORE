import time
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException

from civis.api.dependencies import APIDependencies
from civis.api.models import APIHealthResponse

router = APIRouter(prefix="/health", tags=["Health"])


def create_health_router(deps: APIDependencies, auth_dep: Any) -> APIRouter:
    r = APIRouter(prefix="/health", tags=["Health"], dependencies=[Depends(auth_dep)])

    @r.get("", response_model=APIHealthResponse, summary="Get high-level system health")
    async def get_health():
        obs = deps.get_observability_engine()
        rt = deps.get_runtime_engine()

        status = "HEALTHY"
        active_cams = 0
        total_cams = 0
        uptime = 0.0

        rt_health = rt.get_health() if rt else None
        if rt_health:
            active_cams = rt_health.active_cameras
            total_cams = rt_health.total_cameras
            uptime = rt_health.uptime_seconds

        if obs:
            snap = obs.get_system_health(rt_health)
            status = snap.status.value if hasattr(snap.status, "value") else str(snap.status)

        return APIHealthResponse(
            status=status,
            uptime_seconds=uptime,
            timestamp=time.time(),
            active_cameras=active_cams,
            total_cameras=total_cams,
        )

    @r.get("/liveness", summary="Process liveness probe for container orchestrators")
    async def get_liveness() -> Dict[str, Any]:
        return {
            "status": "alive",
            "timestamp": time.time(),
        }

    @r.get("/readiness", summary="Readiness probe verifying subsystem availability")
    async def get_readiness() -> Dict[str, Any]:
        rt = deps.get_runtime_engine()
        obs = deps.get_observability_engine()
        cfg = deps.get_config_engine()

        is_ready = bool(rt and obs and cfg)
        return {
            "status": "ready" if is_ready else "not_ready",
            "timestamp": time.time(),
            "subsystems": {
                "runtime": rt is not None,
                "observability": obs is not None,
                "config": cfg is not None,
                "evidence": deps.get_evidence_engine() is not None,
            },
        }

    @r.get("/detailed", summary="Get detailed health & diagnostics snapshot")
    async def get_detailed_health() -> Dict[str, Any]:
        obs = deps.get_observability_engine()
        rt = deps.get_runtime_engine()

        rt_health = rt.get_health() if rt else None
        obs_snap = obs.get_system_health(rt_health) if obs else None

        result: Dict[str, Any] = {
            "timestamp": time.time(),
            "runtime": {
                "state": rt_health.state.value if hasattr(rt_health.state, "value") else str(rt_health.state),
                "total_cameras": rt_health.total_cameras,
                "active_cameras": rt_health.active_cameras,
                "total_frames_received": rt_health.total_frames_received,
                "total_frames_processed": rt_health.total_frames_processed,
                "total_frames_dropped": rt_health.total_frames_dropped,
                "total_errors": rt_health.total_errors,
                "uptime_seconds": rt_health.uptime_seconds,
            } if rt_health else {},
            "observability": {
                "status": obs_snap.status.value if hasattr(obs_snap.status, "value") else str(obs_snap.status),
                "uptime_seconds": obs_snap.uptime_seconds,
                "active_cameras": obs_snap.active_cameras,
                "total_cameras": obs_snap.total_cameras,
                "camera_statuses": obs_snap.camera_statuses,
                "active_error_count": obs_snap.active_error_count,
            } if obs_snap else {},
        }
        return result

    @r.get("/metrics", summary="Prometheus-formatted plaintext metrics exposition")
    async def get_metrics():
        from fastapi.responses import PlainTextResponse
        obs = deps.get_observability_engine()
        rt = deps.get_runtime_engine()

        lines = [
            "# HELP civis_up System availability flag (1 = up)",
            "# TYPE civis_up gauge",
            "civis_up 1",
        ]

        if rt:
            health = rt.get_health()
            lines.extend([
                "# HELP civis_active_cameras Number of currently active camera streams",
                "# TYPE civis_active_cameras gauge",
                f"civis_active_cameras {health.active_cameras}",
                "# HELP civis_frames_processed_total Total video frames processed",
                "# TYPE civis_frames_processed_total counter",
                f"civis_frames_processed_total {health.total_frames_processed}",
                "# HELP civis_frames_dropped_total Total video frames dropped under load",
                "# TYPE civis_frames_dropped_total counter",
                f"civis_frames_dropped_total {health.total_frames_dropped}",
                "# HELP civis_errors_total Total pipeline execution errors",
                "# TYPE civis_errors_total counter",
                f"civis_errors_total {health.total_errors}",
            ])

        return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")

    return r
