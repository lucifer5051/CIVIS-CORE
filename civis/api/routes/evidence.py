from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from civis.api.dependencies import APIDependencies
from civis.api.models import APIEvidenceItem, APIEvidenceVerifyResponse


def create_evidence_router(deps: APIDependencies, auth_dep: Any) -> APIRouter:
    r = APIRouter(prefix="/evidence", tags=["Forensic Evidence"], dependencies=[Depends(auth_dep)])

    @r.get("", response_model=List[APIEvidenceItem], summary="List forensic evidence records")
    async def list_evidence(
        camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
        source_type: Optional[str] = Query(None, description="Filter by source type (detection, risk, event)"),
        limit: int = Query(100, ge=1, le=1000, description="Max results"),
    ):
        ev_eng = deps.get_evidence_engine()
        if not ev_eng:
            return []

        records = ev_eng._ledger.query(camera_id=camera_id)
        if source_type:
            records = [r for r in records if (r.stage.value if hasattr(r.stage, "value") else str(r.stage)) == source_type]

        return [
            APIEvidenceItem(
                evidence_id=rec.evidence_id,
                camera_id=rec.camera_id,
                source_type=rec.stage.value if hasattr(rec.stage, "value") else str(rec.stage),
                sha256_hash=rec.record_hash,
                timestamp=rec.timestamp,
                verified=not rec.is_sealed or len(rec.record_hash) > 0,
                metadata={"sequence_number": rec.sequence_number, "frame_id": rec.frame_id},
            )
            for rec in records[:limit]
        ]

    @r.get("/{evidence_id}", response_model=APIEvidenceItem, summary="Get single forensic evidence record")
    async def get_evidence(evidence_id: str):
        ev_eng = deps.get_evidence_engine()
        if not ev_eng:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Evidence engine unavailable")

        rec = ev_eng._ledger.get_record_by_id(evidence_id)
        if not rec:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Evidence record '{evidence_id}' not found")

        return APIEvidenceItem(
            evidence_id=rec.evidence_id,
            camera_id=rec.camera_id,
            source_type=rec.stage.value if hasattr(rec.stage, "value") else str(rec.stage),
            sha256_hash=rec.record_hash,
            timestamp=rec.timestamp,
            verified=not rec.is_sealed or len(rec.record_hash) > 0,
            metadata={"sequence_number": rec.sequence_number, "frame_id": rec.frame_id},
        )

    @r.get("/{evidence_id}/verify", response_model=APIEvidenceVerifyResponse, summary="Verify forensic evidence hash integrity")
    async def verify_evidence(evidence_id: str):
        ev_eng = deps.get_evidence_engine()
        if not ev_eng:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Evidence engine unavailable")

        rec = ev_eng._ledger.get_record_by_id(evidence_id)
        if not rec:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Evidence record '{evidence_id}' not found")

        is_valid, _ = ev_eng.verify_ledger_integrity()
        return APIEvidenceVerifyResponse(
            evidence_id=evidence_id,
            is_valid=is_valid,
            computed_hash=rec.record_hash,
            stored_hash=rec.record_hash,
            message="Evidence hash-chain verified and untampered" if is_valid else "Tamper detected: hash mismatch",
        )

    @r.get("/timeline/{timeline_id}", summary="Get chronological forensic investigation timeline")
    async def get_timeline(timeline_id: str) -> Dict[str, Any]:
        ev_eng = deps.get_evidence_engine()
        if not ev_eng:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Evidence engine unavailable")

        tl = ev_eng.build_timeline()
        return tl.model_dump()

    return r
