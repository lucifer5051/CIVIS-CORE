from abc import ABC, abstractmethod
from typing import Optional

from civis.behavior.models import BehaviorResult
from civis.event_intelligence.models import EventIntelligenceResult
from civis.identity.models import IdentityResult
from civis.risk.models import RiskAssessmentResult, RiskEngineConfig
from civis.tracking.models import TrackResult


class BaseRiskEngine(ABC):
    """
    Abstract Base Class for CIVIS Risk Assessment Engines.
    Consumes EventIntelligenceResult, optional BehaviorResult, IdentityResult, and TrackResult.
    """

    def __init__(self, config: RiskEngineConfig) -> None:
        self._config = config

    @property
    def config(self) -> RiskEngineConfig:
        return self._config

    @abstractmethod
    def assess(
        self,
        event_intelligence_result: EventIntelligenceResult,
        behavior_result: Optional[BehaviorResult] = None,
        identity_result: Optional[IdentityResult] = None,
        track_result: Optional[TrackResult] = None,
    ) -> RiskAssessmentResult:
        """
        Evaluate risk policies across events, behaviors, identities, and tracks,
        producing continuous risk scores, discrete severity levels, and deduplicated alerts.
        """
        pass

    @abstractmethod
    def reset(self, camera_id: Optional[str] = None) -> None:
        """Reset active assessments, memory buffers, and alert throttle history."""
        pass
