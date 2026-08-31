from typing import Any, List, Optional
from fastapi import APIRouter, Depends, Query

from civis.api.dependencies import APIDependencies
from civis.api.models import APITrackItem


def create_tracks_router(deps: APIDependencies, auth_dep: Any) -> APIRouter:
    r = APIRouter(prefix="/tracks", tags=["Analytics - Tracks"], dependencies=[Depends(auth_dep)])

    @r.get("", response_model=List[APITrackItem], summary="Get latest active tracks with filtering")
    async def get_tracks(
        camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
        track_id: Optional[int] = Query(None, description="Filter by track ID"),
        limit: int = Query(100, ge=1, le=1000, description="Max results"),
    ):
        raw_items = deps.in_memory_analytics.get("tracks", [])
        filtered = []
        for t in raw_items:
            if camera_id and t.get("camera_id") != camera_id:
                continue
            if track_id is not None and t.get("track_id") != track_id:
                continue
            filtered.append(APITrackItem(**t))
            if len(filtered) >= limit:
                break
        return filtered

    return r
