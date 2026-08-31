from typing import Optional

from civis.runtime.base import BasePipelineRuntime
from civis.runtime.engine import MockRuntimeEngine, RuntimeEngine
from civis.runtime.models import PipelineRuntimeConfig


def create_runtime_engine(config: Optional[PipelineRuntimeConfig] = None) -> BasePipelineRuntime:
    """
    Factory function to instantiate the CIVIS Pipeline Runtime Orchestration Engine.
    """
    cfg = config if config is not None else PipelineRuntimeConfig()
    if cfg.use_mock:
        return MockRuntimeEngine(cfg)
    return RuntimeEngine(cfg)
