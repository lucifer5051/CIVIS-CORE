from typing import Any, List, Optional
from fastapi import APIRouter, Depends, Query

from civis.api.dependencies import APIDependencies
from civis.api.models import APIDetectionItem


def create_detections_router(deps: APIDependencies, auth_dep: Any) -> APIRouter:
    r = APIRouter(prefix="/detections", tags=["Analytics - Detections"], dependencies=[Depends(auth_dep)])

    @r.get("", response_model=List[APIDetectionItem], summary="Get latest detections with filtering")
    async def get_detections(
        camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
        class_name: Optional[str] = Query(None, description="Filter by class name"),
        min_confidence: Optional[float] = Query(0.0, description="Min confidence score"),
        limit: int = Query(100, ge=1, le=1000, description="Max results"),
    ):
        raw_items = deps.in_memory_analytics.get("detections", [])
        filtered = []
        for d in raw_items:
            if camera_id and d.get("camera_id") != camera_id:
                continue
            if class_name and d.get("class_name") != class_name:
                continue
            if d.get("confidence", 0.0) < min_confidence:
                continue
            filtered.append(APIDetectionItem(**d))
            if len(filtered) >= limit:
                break
        return filtered

    return r
