from civis.event_intelligence.base import BaseEventIntelligenceEngine
from civis.event_intelligence.engine import (
    EventIntelligenceEngine,
    MockEventIntelligenceEngine,
)
from civis.event_intelligence.models import EventIntelligenceConfig


def create_event_intelligence_engine(config: EventIntelligenceConfig) -> BaseEventIntelligenceEngine:
    """
    Factory helper to instantiate EventIntelligenceEngine based on configuration.
    Returns MockEventIntelligenceEngine if config.use_mock is True.
    """
    if config.use_mock:
        return MockEventIntelligenceEngine(config)
    return EventIntelligenceEngine(config)
