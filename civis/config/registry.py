from typing import Any, Callable, Dict, Optional

from civis.config.models import CIVISConfig


class ConfigRegistry:
    """
    Subsystem configuration registry allowing dynamic section lookup and extensibility.
    """

    def __init__(self, config: CIVISConfig) -> None:
        self._config = config
        self._custom_sections: Dict[str, Any] = {}

    def get(self, section_name: str) -> Any:
        """Retrieves a configuration section by name."""
        name = section_name.lower().strip()
        if hasattr(self._config, name):
            return getattr(self._config, name)
        if name in self._custom_sections:
            return self._custom_sections[name]
        raise KeyError(f"Configuration section '{section_name}' is not registered.")

    def register_custom(self, section_name: str, section_value: Any) -> None:
        """Registers an additional custom configuration section."""
        self._custom_sections[section_name.lower().strip()] = section_value

    def list_sections(self) -> Dict[str, Any]:
        """Returns all registered configuration sections."""
        builtins = {
            k: v for k, v in self._config.model_dump().items()
        }
        builtins.update(self._custom_sections)
        return builtins
