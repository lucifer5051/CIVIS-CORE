from typing import Any, List, Optional
from fastapi import APIRouter, Depends, Query

from civis.api.dependencies import APIDependencies
from civis.api.models import APIIdentityItem, APIReIDEntityItem


def create_identities_router(deps: APIDependencies, auth_dep: Any) -> APIRouter:
    r = APIRouter(tags=["Analytics - Identities & Re-ID"], dependencies=[Depends(auth_dep)])

    @r.get("/identities", response_model=List[APIIdentityItem], summary="Get verified facial identities")
    async def get_identities(
        camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
        identity_id: Optional[str] = Query(None, description="Filter by identity ID"),
        limit: int = Query(100, ge=1, le=1000, description="Max results"),
    ):
        raw_items = deps.in_memory_analytics.get("identities", [])
        filtered = []
        for item in raw_items:
            if camera_id and item.get("camera_id") != camera_id:
                continue
            if identity_id and item.get("identity_id") != identity_id:
                continue
            filtered.append(APIIdentityItem(**item))
            if len(filtered) >= limit:
                break
        return filtered

    @r.get("/reid/entities", response_model=List[APIReIDEntityItem], summary="Get cross-camera Re-ID global entities")
    async def get_reid_entities(
        global_id: Optional[str] = Query(None, description="Filter by Global Entity ID"),
        camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
        limit: int = Query(100, ge=1, le=1000, description="Max results"),
    ):
        raw_items = deps.in_memory_analytics.get("reid_entities", [])
        filtered = []
        for item in raw_items:
            if global_id and item.get("global_id") != global_id:
                continue
            if camera_id and item.get("camera_id") != camera_id:
                continue
            filtered.append(APIReIDEntityItem(**item))
            if len(filtered) >= limit:
                break
        return filtered

    return r
