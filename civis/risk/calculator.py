import math
from typing import List, Tuple
from civis.risk.models import RiskContribution


class RiskCalculator:
    """
    Mathematical calculation engine for scoring, multi-signal compounding,
    and confidence aggregation. Strictly guarantees score in [0.0, 100.0]
    and confidence in [0.0, 1.0].
    """

    @classmethod
    def calculate_compounded_risk(
        cls,
        contributions: List[RiskContribution],
    ) -> Tuple[float, float]:
        """
        Combines multiple risk contributions using sublinear saturation and independent probability pooling.
        Returns: (compounded_severity_score, aggregated_confidence)
        """
        if not contributions:
            return 0.0, 0.0

        scores = [max(0.0, min(100.0, c.effective_score)) for c in contributions]
        confidences = [max(0.0, min(1.0, c.confidence)) for c in contributions]

        if len(contributions) == 1:
            return round(scores[0], 2), round(confidences[0], 4)

        # 1. Asymptotic Multi-Signal Compounding for Severity
        max_score = max(scores)
        remaining_scores = [s for idx, s in enumerate(scores) if idx != scores.index(max_score)]

        residual_product = 1.0
        for s in remaining_scores:
            residual_product *= (1.0 - (s / 100.0))

        compounded_score = max_score + (100.0 - max_score) * (1.0 - residual_product)
        bounded_score = max(0.0, min(100.0, compounded_score))

        # 2. Independent Sensor/Signal Confidence Combination
        residual_conf = 1.0
        for c in confidences:
            residual_conf *= (1.0 - c)

        aggregated_conf = 1.0 - residual_conf
        bounded_conf = max(0.0, min(1.0, aggregated_conf))

        return round(bounded_score, 2), round(bounded_conf, 4)
