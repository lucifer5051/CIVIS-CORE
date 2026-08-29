from typing import List
from civis.event_intelligence.models import EvidenceItem


class ExplainabilityEngine:
    """
    Generates human-readable explanations and evidence chain summaries.
    """

    @staticmethod
    def build_explanation(
        rule_name: str,
        camera_id: str,
        primary_track_id: int,
        primary_identity_id: str,
        evidence_chain: List[EvidenceItem],
        overall_confidence: float,
    ) -> str:
        if not evidence_chain:
            return f"Event '{rule_name}' triggered on camera '{camera_id}' for Track {primary_track_id}."

        lines = [
            f"Event '{rule_name}' detected on camera '{camera_id}' for Track {primary_track_id} (Identity: '{primary_identity_id}') with overall confidence {overall_confidence:.2f}.",
            "Evidence Chain:",
        ]

        for i, ev in enumerate(evidence_chain, start=1):
            lines.append(
                f"  {i}. [{ev.source_module.upper()}] {ev.description} (conf: {ev.confidence:.2f}, t={ev.timestamp:.1f}s)"
            )

        return "\n".join(lines)
