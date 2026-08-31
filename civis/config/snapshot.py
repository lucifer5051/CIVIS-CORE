import copy
import hashlib
import json
import time
import uuid
from typing import Any, Dict, Tuple

from civis.config.models import ConfigDiff, ConfigSnapshot

SECRET_PATTERNS = ("password", "secret", "token", "api_key", "private_key", "auth_key", "credentials")


def canonical_json_bytes(data: Any) -> bytes:
    def _default(obj: Any) -> Any:
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        elif hasattr(obj, "__dict__"):
            return obj.__dict__
        elif isinstance(obj, (set, tuple)):
            return list(obj)
        return str(obj)

    return json.dumps(
        data,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
        default=_default,
    ).encode("utf-8")


def redact_secrets(data: Any) -> Any:
    """
    Recursively redacts sensitive values matching security patterns.
    """
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            k_lower = str(k).lower()
            if any(pat in k_lower for pat in SECRET_PATTERNS):
                sanitized[k] = "******"
            else:
                sanitized[k] = redact_secrets(v)
        return sanitized
    elif isinstance(data, list):
        return [redact_secrets(item) for item in data]
    return data


def compute_config_hash(config_dict: Dict[str, Any]) -> str:
    """Computes deterministic SHA-256 checksum of canonical serialized configuration."""
    raw_bytes = canonical_json_bytes(config_dict)
    return hashlib.sha256(raw_bytes).hexdigest()


def compute_config_diff(dict_a: Dict[str, Any], dict_b: Dict[str, Any], prefix: str = "") -> ConfigDiff:
    """
    Recursively compares dict_a (baseline) and dict_b (target), returning added, removed, and changed keys.
    """
    added: Dict[str, Any] = {}
    removed: Dict[str, Any] = {}
    changed: Dict[str, Tuple[Any, Any]] = {}

    all_keys = set(dict_a.keys()).union(set(dict_b.keys()))

    for key in sorted(all_keys):
        path = f"{prefix}.{key}" if prefix else str(key)

        if key not in dict_a:
            added[path] = dict_b[key]
        elif key not in dict_b:
            removed[path] = dict_a[key]
        else:
            val_a = dict_a[key]
            val_b = dict_b[key]

            if isinstance(val_a, dict) and isinstance(val_b, dict):
                sub_diff = compute_config_diff(val_a, val_b, prefix=path)
                added.update(sub_diff.added)
                removed.update(sub_diff.removed)
                changed.update(sub_diff.changed)
            elif val_a != val_b:
                changed[path] = (val_a, val_b)

    return ConfigDiff(added=added, removed=removed, changed=changed)


def create_snapshot(
    config_dict: Dict[str, Any],
    version: str = "1.0.0",
    sanitize: bool = True,
) -> ConfigSnapshot:
    data_to_store = redact_secrets(copy.deepcopy(config_dict)) if sanitize else copy.deepcopy(config_dict)
    checksum = compute_config_hash(data_to_store)
    snapshot_id = f"cfg_snap_{uuid.uuid4().hex[:8]}"

    return ConfigSnapshot(
        snapshot_id=snapshot_id,
        timestamp=time.time(),
        version=version,
        checksum=checksum,
        config_data=data_to_store,
        is_sanitized=sanitize,
    )
