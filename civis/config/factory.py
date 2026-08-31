from typing import Any, Dict, Optional

from civis.config.base import BaseConfigManager
from civis.config.engine import ConfigEngine, MockConfigEngine


def create_config_engine(
    config_path: Optional[str] = None,
    config_dict: Optional[Dict[str, Any]] = None,
    use_env: bool = True,
    use_mock: bool = False,
) -> BaseConfigManager:
    """
    Factory function to instantiate the CIVIS Centralized Configuration Engine.
    """
    if use_mock:
        return MockConfigEngine(config_dict)
    return ConfigEngine(
        config_path=config_path,
        config_dict=config_dict,
        use_env=use_env,
    )
