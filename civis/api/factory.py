from typing import Optional

from civis.api.base import BaseAPIEngine
from civis.api.dependencies import APIDependencies
from civis.api.engine import APIEngine, MockAPIEngine
from civis.api.models import APIConfig


def create_api_engine(
    config: Optional[APIConfig] = None,
    dependencies: Optional[APIDependencies] = None,
    use_mock: bool = False,
) -> BaseAPIEngine:
    """
    Factory function to instantiate the CIVIS API Gateway Engine.
    """
    if use_mock or (config and config.use_mock):
        return MockAPIEngine(config=config)
    return APIEngine(config=config, dependencies=dependencies)
