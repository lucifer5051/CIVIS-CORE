from typing import Any, List, Optional
from fastapi import APIRouter, Depends, Query

from civis.api.dependencies import APIDependencies
from civis.api.models import APIRiskAlertItem, APIRiskAssessmentItem


def create_risks_router(deps: APIDependencies, auth_dep: Any) -> APIRouter:
    r = APIRouter(prefix="/risks", tags=["Analytics - Risks"], dependencies=[Depends(auth_dep)])

    @r.get("", response_model=List[APIRiskAssessmentItem], summary="Get explainable risk assessments")
    async def get_risks(
        camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
        severity: Optional[str] = Query(None, description="Filter by risk severity (low, medium, high, critical)"),
        limit: int = Query(100, ge=1, le=1000, description="Max results"),
    ):
        raw_items = deps.in_memory_analytics.get("risks", [])
        filtered = []
        for rsk in raw_items:
            if camera_id and rsk.get("camera_id") != camera_id:
                continue
            if severity and rsk.get("severity") != severity:
                continue
            filtered.append(APIRiskAssessmentItem(**rsk))
            if len(filtered) >= limit:
                break
        return filtered

    @r.get("/alerts", response_model=List[APIRiskAlertItem], summary="Get deduplicated actionable risk alerts")
    async def get_risk_alerts(
        camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
        severity: Optional[str] = Query(None, description="Filter by alert severity"),
        limit: int = Query(100, ge=1, le=1000, description="Max results"),
    ):
        raw_items = deps.in_memory_analytics.get("alerts", [])
        filtered = []
        for alt in raw_items:
            if camera_id and alt.get("camera_id") != camera_id:
                continue
            if severity and alt.get("severity") != severity:
                continue
            filtered.append(APIRiskAlertItem(**alt))
            if len(filtered) >= limit:
                break
        return filtered

    return r
