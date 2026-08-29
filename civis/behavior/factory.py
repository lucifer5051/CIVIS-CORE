from civis.behavior.base import BaseBehaviorEngine
from civis.behavior.engine import BehaviorEngine, MockBehaviorEngine
from civis.behavior.models import BehaviorConfig


def create_behavior_engine(config: BehaviorConfig) -> BaseBehaviorEngine:
    """
    Factory helper to instantiate BehaviorEngine based on configuration.
    Returns MockBehaviorEngine if config.use_mock is True.
    """
    if config.use_mock:
        return MockBehaviorEngine(config)
    return BehaviorEngine(config)
