from typing import Any, Callable, Dict, Optional
from civis.config.base import BaseConfigManager
from civis.evidence.base import BaseEvidenceEngine
from civis.observability.base import BaseObservabilityEngine
from civis.risk.base import BaseRiskEngine
from civis.runtime.base import BasePipelineRuntime


class APIDependencies:
    """
    Subsystem dependency container for FastAPI routes.
    """

    def __init__(
        self,
        runtime_engine: Optional[BasePipelineRuntime] = None,
        observability_engine: Optional[BaseObservabilityEngine] = None,
        config_engine: Optional[BaseConfigManager] = None,
        evidence_engine: Optional[BaseEvidenceEngine] = None,
        risk_engine: Optional[BaseRiskEngine] = None,
    ) -> None:
        self.runtime_engine = runtime_engine
        self.observability_engine = observability_engine
        self.config_engine = config_engine
        self.evidence_engine = evidence_engine
        self.risk_engine = risk_engine
        self.in_memory_analytics: Dict[str, list] = {
            "detections": [],
            "tracks": [],
            "identities": [],
            "reid_entities": [],
            "behavior_events": [],
            "events": [],
            "risks": [],
            "alerts": [],
        }

    def get_runtime_engine(self) -> Optional[BasePipelineRuntime]:
        return self.runtime_engine

    def get_observability_engine(self) -> Optional[BaseObservabilityEngine]:
        return self.observability_engine

    def get_config_engine(self) -> Optional[BaseConfigManager]:
        return self.config_engine

    def get_evidence_engine(self) -> Optional[BaseEvidenceEngine]:
        return self.evidence_engine

    def get_risk_engine(self) -> Optional[BaseRiskEngine]:
        return self.risk_engine
