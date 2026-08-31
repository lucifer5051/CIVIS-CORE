from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status

from civis.api.dependencies import APIDependencies
from civis.api.models import APICameraActionResponse, APICameraStatusResponse


def create_cameras_router(deps: APIDependencies, auth_dep: Any) -> APIRouter:
    r = APIRouter(prefix="/cameras", tags=["Cameras"], dependencies=[Depends(auth_dep)])

    @r.get("", response_model=List[APICameraStatusResponse], summary="List all camera stream statuses")
    async def list_cameras():
        rt = deps.get_runtime_engine()
        if not rt:
            return []

        health = rt.get_health()
        response = []
        for cam_id, h in health.camera_health.items():
            response.append(APICameraStatusResponse(
                camera_id=cam_id,
                is_running=h.state.value == "running" if hasattr(h.state, "value") else (h.state == "running"),
                is_paused=h.state.value == "paused" if hasattr(h.state, "value") else (h.state == "paused"),
                processed_frames=h.frames_processed,
                dropped_frames=h.frames_dropped,
                current_fps=h.current_fps,
                error_count=h.error_count,
            ))
        return response

    @r.get("/{camera_id}", response_model=APICameraStatusResponse, summary="Get single camera stream status")
    async def get_camera(camera_id: str):
        rt = deps.get_runtime_engine()
        if not rt:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Runtime engine unavailable")

        health = rt.get_health()
        h = health.camera_health.get(camera_id)
        if not h:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Camera '{camera_id}' not found")

        return APICameraStatusResponse(
            camera_id=camera_id,
            is_running=h.state.value == "running" if hasattr(h.state, "value") else (h.state == "running"),
            is_paused=h.state.value == "paused" if hasattr(h.state, "value") else (h.state == "paused"),
            processed_frames=h.frames_processed,
            dropped_frames=h.frames_dropped,
            current_fps=h.current_fps,
            error_count=h.error_count,
        )

    @r.post("/{camera_id}/start", response_model=APICameraActionResponse, summary="Start a camera stream")
    async def start_camera(camera_id: str):
        rt = deps.get_runtime_engine()
        if not rt:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Runtime engine unavailable")

        cam = rt.get_camera_runtime(camera_id)
        if not cam:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Camera '{camera_id}' not found")

        cam.start()
        return APICameraActionResponse(
            camera_id=camera_id,
            action="start",
            success=True,
            message="Camera started successfully",
        )

    @r.post("/{camera_id}/stop", response_model=APICameraActionResponse, summary="Stop a camera stream")
    async def stop_camera(camera_id: str):
        rt = deps.get_runtime_engine()
        if not rt:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Runtime engine unavailable")

        cam = rt.get_camera_runtime(camera_id)
        if not cam:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Camera '{camera_id}' not found")

        cam.stop()
        return APICameraActionResponse(
            camera_id=camera_id,
            action="stop",
            success=True,
            message="Camera stopped successfully",
        )

    @r.post("/{camera_id}/pause", response_model=APICameraActionResponse, summary="Pause a camera stream")
    async def pause_camera(camera_id: str):
        rt = deps.get_runtime_engine()
        if not rt:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Runtime engine unavailable")

        cam = rt.get_camera_runtime(camera_id)
        if not cam:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Camera '{camera_id}' not found")

        cam.pause()
        return APICameraActionResponse(
            camera_id=camera_id,
            action="pause",
            success=True,
            message="Camera paused successfully",
        )

    @r.post("/{camera_id}/resume", response_model=APICameraActionResponse, summary="Resume a camera stream")
    async def resume_camera(camera_id: str):
        rt = deps.get_runtime_engine()
        if not rt:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Runtime engine unavailable")

        cam = rt.get_camera_runtime(camera_id)
        if not cam:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Camera '{camera_id}' not found")

        cam.resume()
        return APICameraActionResponse(
            camera_id=camera_id,
            action="resume",
            success=True,
            message="Camera resumed successfully",
        )

    return r
