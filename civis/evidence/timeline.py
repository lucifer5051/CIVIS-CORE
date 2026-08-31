import uuid
from typing import List, Optional

from civis.evidence.models import EvidenceRecord, InvestigationTimeline


class TimelineBuilder:
    """
    Synthesizes chronological multi-camera investigation timelines from evidence records.
    """

    @classmethod
    def build_timeline(
        cls,
        records: List[EvidenceRecord],
        title: str = "Incident Investigation Timeline",
    ) -> InvestigationTimeline:
        timeline_id = f"tl_{uuid.uuid4().hex[:8]}"

        if not records:
            return InvestigationTimeline(
                timeline_id=timeline_id,
                title=title,
                start_timestamp=0.0,
                end_timestamp=0.0,
                involved_cameras=[],
                involved_entities=[],
                total_records=0,
                records=[],
                integrity_verified=True,
                summary="Empty investigation timeline.",
            )

        # Sort chronologically
        sorted_records = sorted(records, key=lambda r: (r.timestamp, r.sequence_number))

        start_ts = sorted_records[0].timestamp
        end_ts = sorted_records[-1].timestamp
        cameras = sorted(list({r.camera_id for r in sorted_records}))
        
        entities = set()
        for r in sorted_records:
            if r.global_entity_id:
                entities.add(r.global_entity_id)
            if r.identity_id and r.identity_id not in ("UNKNOWN", "", "None"):
                entities.add(r.identity_id)
            elif r.track_id is not None:
                entities.add(f"{r.camera_id}#T{r.track_id}")

        # Construct narrative summary
        summary_lines = [
            f"Investigation Timeline '{title}' (ID: {timeline_id}):",
            f"Duration: {start_ts:.1f}s -> {end_ts:.1f}s (Span: {end_ts - start_ts:.1f}s)",
            f"Cameras: {', '.join(cameras)} | Entities: {', '.join(sorted(list(entities)))}",
            f"Total Evidence Events Logged: {len(sorted_records)}",
        ]

        # Highlight high-severity entries
        high_risk_records = [r for r in sorted_records if r.is_high_risk]
        if high_risk_records:
            summary_lines.append(f"High-Impact Events ({len(high_risk_records)}):")
            for hr in high_risk_records:
                desc = hr.payload.get("name") or hr.payload.get("event_type") or hr.stage.value
                summary_lines.append(
                    f"  - [{hr.timestamp:.2f}s] {hr.camera_id} [{hr.severity.upper() if hr.severity else 'RISK'}]: {desc}"
                )

        return InvestigationTimeline(
            timeline_id=timeline_id,
            title=title,
            start_timestamp=start_ts,
            end_timestamp=end_ts,
            involved_cameras=cameras,
            involved_entities=sorted(list(entities)),
            total_records=len(sorted_records),
            records=sorted_records,
            integrity_verified=True,
            summary="\n".join(summary_lines),
        )
