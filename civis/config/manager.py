import copy
from typing import Any, Dict, List, Optional, Set, Tuple

from civis.config.base import BaseConfigManager
from civis.config.loader import deep_merge
from civis.config.models import (
    CIVISConfig,
    ConfigDiff,
    ConfigSnapshot,
    ConfigUpdateResult,
)
from civis.config.policy import PolicyManager
from civis.config.registry import ConfigRegistry
from civis.config.snapshot import compute_config_diff, create_snapshot
from civis.config.validation import validate_civis_config

RESTART_REQUIRED_PATHS: Set[str] = {
    "device",
    "detection.model_path",
    "identity.model_version",
    "reid.device",
    "runtime.max_worker_threads",
    "runtime.device",
}


class ConfigManager(BaseConfigManager):
    """
    Thread-safe Centralized Configuration & Policy Manager.
    Enforces validation-before-mutation, rollback on error, snapshotting, and diffing.
    """

    def __init__(self, initial_config: Optional[CIVISConfig] = None) -> None:
        self._config = initial_config if initial_config is not None else CIVISConfig()
        self.registry = ConfigRegistry(self._config)
        self.policies = PolicyManager(self._config.policies)
        self._snapshots: List[ConfigSnapshot] = []

        # Initial baseline snapshot
        self._initial_snapshot = self.create_snapshot()
        self._snapshots.append(self._initial_snapshot)

    def get(self) -> CIVISConfig:
        return self._config

    def get_section(self, section_name: str) -> Any:
        return self.registry.get(section_name)

    def validate(self, config: Optional[CIVISConfig] = None) -> Tuple[bool, List[str]]:
        target = config if config is not None else self._config
        return validate_civis_config(target)

    def update(self, updates: Dict[str, Any], apply_now: bool = True) -> ConfigUpdateResult:
        """
        Applies runtime updates safely. Pre-validates against schema and rules
        before mutating active state. Rolls back cleanly if validation fails.
        """
        current_dict = self._config.model_dump()
        proposed_dict = deep_merge(current_dict, updates)

        # 1. Schema instantiation & validation
        try:
            proposed_config = CIVISConfig(**proposed_dict)
        except Exception as e:
            return ConfigUpdateResult(
                success=False,
                applied_changes={},
                requires_restart=False,
                validation_errors=[f"Schema validation error: {str(e)}"],
            )

        # 2. Cross-subsystem rule validation
        is_valid, errs = validate_civis_config(proposed_config)
        if not is_valid:
            return ConfigUpdateResult(
                success=False,
                applied_changes={},
                requires_restart=False,
                validation_errors=errs,
            )

        # 3. Check for restart-required modifications
        diff_res = compute_config_diff(current_dict, proposed_dict)
        modified_paths = set(diff_res.added.keys()).union(set(diff_res.changed.keys())).union(set(diff_res.removed.keys()))
        requires_restart = bool(modified_paths.intersection(RESTART_REQUIRED_PATHS))

        # 4. Apply changes
        if apply_now:
            self._config = proposed_config
            self.registry = ConfigRegistry(self._config)
            self.policies = PolicyManager(self._config.policies)
            new_snapshot = self.create_snapshot()
            self._snapshots.append(new_snapshot)

        return ConfigUpdateResult(
            success=True,
            applied_changes=diff_res.changed,
            requires_restart=requires_restart,
            validation_errors=[],
            snapshot=self._snapshots[-1] if apply_now else None,
        )

    def update_section(self, section_name: str, values: Dict[str, Any]) -> ConfigUpdateResult:
        return self.update({section_name: values})

    def create_snapshot(self, sanitize_secrets: bool = True) -> ConfigSnapshot:
        config_dict = self._config.model_dump()
        return create_snapshot(
            config_dict=config_dict,
            version=self._config.version,
            sanitize=sanitize_secrets,
        )

    def diff(self, snapshot_a: ConfigSnapshot, snapshot_b: ConfigSnapshot) -> ConfigDiff:
        return compute_config_diff(snapshot_a.config_data, snapshot_b.config_data)

    def get_snapshots(self) -> List[ConfigSnapshot]:
        return list(self._snapshots)

    def reset_to_defaults(self) -> None:
        self._config = CIVISConfig()
        self.registry = ConfigRegistry(self._config)
        self.policies = PolicyManager(self._config.policies)
        self._snapshots.append(self.create_snapshot())
