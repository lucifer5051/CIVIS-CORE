from typing import Any, Dict
from fastapi import APIRouter, Body, Depends, HTTPException, status

from civis.api.dependencies import APIDependencies


def create_config_router(deps: APIDependencies, auth_dep: Any) -> APIRouter:
    r = APIRouter(prefix="/config", tags=["Configuration & Policies"], dependencies=[Depends(auth_dep)])

    @r.get("", summary="Get entire active configuration")
    async def get_config() -> Dict[str, Any]:
        cfg_mgr = deps.get_config_engine()
        if not cfg_mgr:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Config manager unavailable")

        return cfg_mgr.get().model_dump()

    @r.get("/snapshot", summary="Get current immutable sanitized configuration snapshot")
    async def get_snapshot() -> Dict[str, Any]:
        cfg_mgr = deps.get_config_engine()
        if not cfg_mgr:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Config manager unavailable")

        snap = cfg_mgr.create_snapshot(sanitize_secrets=True)
        return {
            "snapshot_id": snap.snapshot_id,
            "timestamp": snap.timestamp,
            "version": snap.version,
            "checksum": snap.checksum,
            "config_data": snap.config_data,
        }

    @r.get("/{section}", summary="Get specific subsystem configuration section")
    async def get_config_section(section: str) -> Dict[str, Any]:
        cfg_mgr = deps.get_config_engine()
        if not cfg_mgr:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Config manager unavailable")

        try:
            sec = cfg_mgr.get_section(section)
            if hasattr(sec, "model_dump"):
                return sec.model_dump()
            elif isinstance(sec, dict):
                return sec
            return {"value": sec}
        except KeyError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Configuration section '{section}' not found")

    @r.post("/validate", summary="Validate proposed configuration without mutating active state")
    async def validate_config(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        cfg_mgr = deps.get_config_engine()
        if not cfg_mgr:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Config manager unavailable")

        res = cfg_mgr.update(payload, apply_now=False)
        return {
            "valid": res.success,
            "validation_errors": res.validation_errors,
            "requires_restart": res.requires_restart,
        }

    @r.patch("/{section}", summary="Apply safe runtime configuration update to subsystem section")
    async def update_config_section(section: str, payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        cfg_mgr = deps.get_config_engine()
        if not cfg_mgr:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Config manager unavailable")

        res = cfg_mgr.update_section(section, payload)
        if not res.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Configuration update rejected: {', '.join(res.validation_errors)}",
            )

        return {
            "success": True,
            "applied_changes": res.applied_changes,
            "requires_restart": res.requires_restart,
        }

    return r
