import copy
import json
import os
from typing import Any, Dict, Optional

from civis.config.environment import load_environment_overrides
from civis.config.models import CIVISConfig


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merges override dictionary into base dictionary."""
    result = copy.deepcopy(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = copy.deepcopy(v)
    return result


class ConfigLoader:
    """
    Deterministic layered configuration loader adhering to:
    Environment > Supplied Dict / File > Baseline Defaults.
    """

    @classmethod
    def load(
        cls,
        file_path: Optional[str] = None,
        data_dict: Optional[Dict[str, Any]] = None,
        env_prefix: str = "CIVIS_",
    ) -> CIVISConfig:
        merged: Dict[str, Any] = {}

        # 1. Load from file if provided
        if file_path and os.path.isfile(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                file_data = json.load(f)
                merged = deep_merge(merged, file_data)

        # 2. Layer explicit dict
        if data_dict:
            merged = deep_merge(merged, data_dict)

        # 3. Layer environment overrides
        env_overrides = load_environment_overrides(prefix=env_prefix)
        if env_overrides:
            merged = deep_merge(merged, env_overrides)

        # 4. Instantiate Pydantic model
        return CIVISConfig(**merged)
