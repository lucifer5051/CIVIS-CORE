from abc import ABC, abstractmethod
from typing import Optional

from civis.behavior.models import BehaviorConfig, BehaviorResult
from civis.identity.models import IdentityResult
from civis.tracking.models import TrackResult


class BaseBehaviorEngine(ABC):
    """
    Abstract Base Class for CIVIS Behavior Analysis Engines.
    Consumes TrackResult and optional IdentityResult payloads.
    """

    def __init__(self, config: BehaviorConfig) -> None:
        self._config = config

    @property
    def config(self) -> BehaviorConfig:
        return self._config

    @abstractmethod
    def process(
        self,
        track_result: TrackResult,
        identity_result: Optional[IdentityResult] = None,
    ) -> BehaviorResult:
        """Process tracking and identity payloads to analyze behaviors and emit events."""
        pass

    @abstractmethod
    def reset(self, camera_id: Optional[str] = None) -> None:
        """Reset temporal trajectory and cooldown memories."""
        pass
