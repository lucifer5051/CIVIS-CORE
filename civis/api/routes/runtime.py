from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status

from civis.api.dependencies import APIDependencies
from civis.api.models import APIRuntimeStatusResponse


def create_runtime_router(deps: APIDependencies, auth_dep: Any) -> APIRouter:
    r = APIRouter(prefix="/runtime", tags=["Runtime Orchestration"], dependencies=[Depends(auth_dep)])

    @r.get("/status", response_model=APIRuntimeStatusResponse, summary="Get full runtime orchestration status")
    async def get_runtime_status():
        rt = deps.get_runtime_engine()
        if not rt:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Runtime engine unavailable")

        health = rt.get_health()

        return APIRuntimeStatusResponse(
            state=health.state.value if hasattr(health.state, "value") else str(health.state),
            uptime_seconds=health.uptime_seconds,
            active_cameras=health.active_cameras,
            total_cameras=health.total_cameras,
            per_camera_status={
                cam_id: {
                    "is_running": h.state.value == "running" if hasattr(h.state, "value") else (h.state == "running"),
                    "is_paused": h.state.value == "paused" if hasattr(h.state, "value") else (h.state == "paused"),
                    "processed_frames": h.frames_processed,
                    "dropped_frames": h.frames_dropped,
                }
                for cam_id, h in health.camera_health.items()
            },
        )

    @r.post("/start", summary="Start runtime pipeline engine")
    async def start_runtime() -> Dict[str, Any]:
        rt = deps.get_runtime_engine()
        if not rt:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Runtime engine unavailable")

        rt.start()
        return {"status": "started", "message": "Pipeline runtime execution started"}

    @r.post("/stop", summary="Stop runtime pipeline engine")
    async def stop_runtime() -> Dict[str, Any]:
        rt = deps.get_runtime_engine()
        if not rt:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Runtime engine unavailable")

        rt.stop()
        return {"status": "stopped", "message": "Pipeline runtime execution stopped"}

    return r
