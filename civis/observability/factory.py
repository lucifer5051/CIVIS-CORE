from typing import Optional

from civis.observability.base import BaseObservabilityEngine
from civis.observability.engine import MockObservabilityEngine, ObservabilityEngine
from civis.observability.models import ObservabilityConfig


def create_observability_engine(config: Optional[ObservabilityConfig] = None) -> BaseObservabilityEngine:
    """
    Factory function to instantiate the CIVIS Observability, Metrics & Diagnostics Engine.
    """
    cfg = config if config is not None else ObservabilityConfig()
    if cfg.use_mock:
        return MockObservabilityEngine(cfg)
    return ObservabilityEngine(cfg)
