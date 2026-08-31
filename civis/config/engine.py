from typing import Any, Dict, Optional

from civis.config.loader import ConfigLoader
from civis.config.manager import ConfigManager
from civis.config.models import CIVISConfig


class ConfigEngine(ConfigManager):
    """
    Primary Configuration & Policy Management Engine for CIVIS-CORE.
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        config_dict: Optional[Dict[str, Any]] = None,
        use_env: bool = True,
    ) -> None:
        env_pfx = "CIVIS_" if use_env else "__NO_ENV__"
        loaded_cfg = ConfigLoader.load(
            file_path=config_path,
            data_dict=config_dict,
            env_prefix=env_pfx,
        )
        super().__init__(loaded_cfg)


class MockConfigEngine(ConfigEngine):
    """
    Deterministic Mock Config Engine for testing without filesystem or env reliance.
    """

    def __init__(self, config_dict: Optional[Dict[str, Any]] = None) -> None:
        defaults = {
            "project_name": "CIVIS-CORE-MOCK",
            "environment": "testing",
            "device": "cpu",
            "detection": {"use_mock": True},
            "tracking": {"use_mock": True},
            "identity": {"use_mock": True},
            "reid": {"use_mock": True},
            "behavior": {"use_mock": True},
            "event_intelligence": {"use_mock": True},
            "risk": {"use_mock": True},
            "evidence": {"use_mock": True},
            "runtime": {"use_mock": True},
            "observability": {"use_mock": True},
        }
        if config_dict:
            defaults.update(config_dict)
        super().__init__(config_dict=defaults, use_env=False)
