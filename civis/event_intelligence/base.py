from abc import ABC, abstractmethod
from typing import Optional

from civis.behavior.models import BehaviorResult
from civis.event_intelligence.models import (
    EventIntelligenceConfig,
    EventIntelligenceResult,
)
from civis.identity.models import IdentityResult
from civis.tracking.models import TrackResult


class BaseEventIntelligenceEngine(ABC):
    """
    Abstract Base Class for CIVIS Event Intelligence Engines.
    Consumes BehaviorResult, optional IdentityResult, and optional TrackResult.
    """

    def __init__(self, config: EventIntelligenceConfig) -> None:
        self._config = config

    @property
    def config(self) -> EventIntelligenceConfig:
        return self._config

    @abstractmethod
    def process(
        self,
        behavior_result: BehaviorResult,
        identity_result: Optional[IdentityResult] = None,
        track_result: Optional[TrackResult] = None,
    ) -> EventIntelligenceResult:
        """Evaluate data-driven rules over temporal observation streams and emit correlated events."""
        pass

    @abstractmethod
    def reset(self, camera_id: Optional[str] = None) -> None:
        """Reset temporal correlation buffers and active event lifecycles."""
        pass
