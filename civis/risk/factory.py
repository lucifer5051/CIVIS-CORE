from typing import Optional

from civis.risk.base import BaseRiskEngine
from civis.risk.engine import MockRiskEngine, RiskEngine
from civis.risk.models import RiskEngineConfig


def create_risk_engine(config: Optional[RiskEngineConfig] = None) -> BaseRiskEngine:
    """
    Factory method to instantiate a CIVIS Risk Engine.
    """
    cfg = config if config is not None else RiskEngineConfig()
    if cfg.use_mock:
        return MockRiskEngine(cfg)
    return RiskEngine(cfg)
