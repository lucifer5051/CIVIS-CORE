from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from civis.config.models import (
    CIVISConfig,
    ConfigDiff,
    ConfigSnapshot,
    ConfigUpdateResult,
)


class BaseConfigManager(ABC):
    """
    Abstract interface for CIVIS centralized configuration management.
    """

    @abstractmethod
    def get(self) -> CIVISConfig:
        """Returns the active CIVISConfig model."""
        pass

    @abstractmethod
    def get_section(self, section_name: str) -> Any:
        """Returns a specific subsystem configuration model by name."""
        pass

    @abstractmethod
    def update(self, updates: Dict[str, Any], apply_now: bool = True) -> ConfigUpdateResult:
        """Safely updates configuration with pre-validation and rollback on error."""
        pass

    @abstractmethod
    def update_section(self, section_name: str, values: Dict[str, Any]) -> ConfigUpdateResult:
        """Updates a specific subsystem configuration section."""
        pass

    @abstractmethod
    def create_snapshot(self, sanitize_secrets: bool = True) -> ConfigSnapshot:
        """Creates an immutable, cryptographically-hashed configuration snapshot."""
        pass

    @abstractmethod
    def diff(self, snapshot_a: ConfigSnapshot, snapshot_b: ConfigSnapshot) -> ConfigDiff:
        """Computes deterministic diff between two configuration snapshots."""
        pass

    @abstractmethod
    def validate(self, config: Optional[CIVISConfig] = None) -> Tuple[bool, List[str]]:
        """Validates configuration against global and cross-subsystem rules."""
        pass

    @abstractmethod
    def reset_to_defaults(self) -> None:
        """Resets active configuration to baseline defaults."""
        pass
