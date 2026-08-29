import logging
from typing import Dict, List, Optional, Tuple
import numpy as np

from civis.behavior.models import BehaviorObservation, BehaviorEvent
from civis.event_intelligence.models import ConfidenceAggregation, EvidenceItem
from civis.identity.models import AssociatedIdentity

logger = logging.getLogger(__name__)


class ConfidenceAggregator:
    """
    Computes overall event confidence while preserving individually visible evidence confidence values.
    Supports AVERAGE, MIN, MAX, and WEIGHTED aggregation modes.
    """

    @staticmethod
    def aggregate(
        evidence_chain: List[EvidenceItem],
        mode: ConfidenceAggregation = ConfidenceAggregation.AVERAGE,
    ) -> float:
        if not evidence_chain:
            return 0.0

        confidences = [e.confidence for e in evidence_chain]

        if mode == ConfidenceAggregation.MIN:
            return float(min(confidences))
        elif mode == ConfidenceAggregation.MAX:
            return float(max(confidences))
        elif mode == ConfidenceAggregation.WEIGHTED:
            # Weight recent evidence items slightly higher
            weights = np.linspace(0.5, 1.0, len(confidences))
            return float(np.average(confidences, weights=weights))
        else:
            # Default AVERAGE
            return float(sum(confidences) / len(confidences))


class TrackTemporalObservationBuffer:
    """
    Maintains a sliding temporal window of observations for a track.
    """

    def __init__(self, camera_id: str, track_id: int, window_seconds: float = 60.0) -> None:
        self.camera_id = camera_id
        self.track_id = track_id
        self.window_seconds = window_seconds
        self.behavior_observations: List[Tuple[float, BehaviorObservation]] = []
        self.behavior_events: List[Tuple[float, BehaviorEvent]] = []
        self.identity_history: List[Tuple[float, AssociatedIdentity]] = []

    def add_behavior_obs(self, timestamp: float, obs: BehaviorObservation) -> None:
        self.behavior_observations.append((timestamp, obs))
        self._trim(timestamp)

    def add_behavior_event(self, timestamp: float, evt: BehaviorEvent) -> None:
        self.behavior_events.append((timestamp, evt))
        self._trim(timestamp)

    def add_identity(self, timestamp: float, ident: AssociatedIdentity) -> None:
        self.identity_history.append((timestamp, ident))
        self._trim(timestamp)

    def _trim(self, current_time: float) -> None:
        cutoff = current_time - self.window_seconds
        self.behavior_observations = [item for item in self.behavior_observations if item[0] >= cutoff]
        self.behavior_events = [item for item in self.behavior_events if item[0] >= cutoff]
        self.identity_history = [item for item in self.identity_history if item[0] >= cutoff]
