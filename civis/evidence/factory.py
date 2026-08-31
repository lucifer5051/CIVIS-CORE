from typing import Optional

from civis.evidence.base import BaseEvidenceEngine
from civis.evidence.engine import EvidenceEngine, MockEvidenceEngine
from civis.evidence.models import EvidenceEngineConfig


def create_evidence_engine(config: Optional[EvidenceEngineConfig] = None) -> BaseEvidenceEngine:
    """
    Factory function to instantiate a CIVIS Forensic Evidence Engine.
    """
    cfg = config if config is not None else EvidenceEngineConfig()
    if cfg.use_mock:
        return MockEvidenceEngine(cfg)
    return EvidenceEngine(cfg)
