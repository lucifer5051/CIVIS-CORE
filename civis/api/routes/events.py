from typing import Any, List, Optional
from fastapi import APIRouter, Depends, Query

from civis.api.dependencies import APIDependencies
from civis.api.models import APIBehaviorEventItem, APICorrelatedEventItem


def create_events_router(deps: APIDependencies, auth_dep: Any) -> APIRouter:
    r = APIRouter(tags=["Analytics - Events"], dependencies=[Depends(auth_dep)])

    @r.get("/behavior/events", response_model=List[APIBehaviorEventItem], summary="Get detected behavioral events")
    async def get_behavior_events(
        camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
        behavior_type: Optional[str] = Query(None, description="Filter by behavior type (e.g. loitering, running)"),
        limit: int = Query(100, ge=1, le=1000, description="Max results"),
    ):
        raw_items = deps.in_memory_analytics.get("behavior_events", [])
        filtered = []
        for b in raw_items:
            if camera_id and b.get("camera_id") != camera_id:
                continue
            if behavior_type and b.get("behavior_type") != behavior_type:
                continue
            filtered.append(APIBehaviorEventItem(**b))
            if len(filtered) >= limit:
                break
        return filtered

    @r.get("/events", response_model=List[APICorrelatedEventItem], summary="Get correlated complex situational events")
    async def get_correlated_events(
        camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
        severity: Optional[str] = Query(None, description="Filter by severity level"),
        limit: int = Query(100, ge=1, le=1000, description="Max results"),
    ):
        raw_items = deps.in_memory_analytics.get("events", [])
        filtered = []
        for e in raw_items:
            if camera_id and e.get("camera_id") != camera_id:
                continue
            if severity and e.get("severity") != severity:
                continue
            filtered.append(APICorrelatedEventItem(**e))
            if len(filtered) >= limit:
                break
        return filtered

    return r
