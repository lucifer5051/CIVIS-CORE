from typing import List
from civis.risk.models import RiskAssessment, RiskContribution


class RiskExplainabilityEngine:
    """
    Synthesizes structured, transparent, human-readable explanations
    detailing why a specific risk score and severity level were assigned.
    """

    @classmethod
    def generate_explanation(cls, assessment: RiskAssessment) -> str:
        """
        Generates a multi-line explanatory narrative for a RiskAssessment.
        """
        lines: List[str] = []
        sev_str = assessment.severity.value.upper()
        cat_str = assessment.category.value.replace("_", " ").title()
        entity_name = assessment.identity_id if assessment.identity_id not in ("UNKNOWN", "") else f"Track #{assessment.track_id}"

        lines.append(
            f"[{sev_str} RISK (Score: {assessment.severity_score:.1f}/100, Confidence: {assessment.confidence * 100:.1f}%)]"
        )
        lines.append(f"Threat Category: {cat_str} | Entity: {entity_name} on Camera: {assessment.camera_id}")
        lines.append(f"State: {assessment.state.value.upper()} | Peak Score: {assessment.peak_severity_score:.1f}")

        if assessment.contributions:
            lines.append("Contributing Risk Signals:")
            for idx, c in enumerate(assessment.contributions, 1):
                lines.append(
                    f"  {idx}. {c.name} (Base: {c.base_score:.1f}, Effective: {c.effective_score:.1f}, Conf: {c.confidence:.2f})"
                )
                if c.applied_multipliers:
                    for m in c.applied_multipliers:
                        lines.append(f"     * Multiplier x{m['multiplier']:.2f}: {m.get('description', m.get('condition_type'))}")

        active_duration = max(0.0, assessment.last_updated_timestamp - assessment.start_timestamp)
        if active_duration > 0.0:
            lines.append(f"Temporal Persistence: Sustained for {active_duration:.1f}s")

        num_evidence = len(assessment.evidence_chain)
        lines.append(f"Evidence Audit Trail: {num_evidence} verified upstream evidence items linked.")

        return "\n".join(lines)
