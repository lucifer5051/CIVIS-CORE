import json
import os
from typing import Any, Dict


def parse_env_value(val: str) -> Any:
    """Parses a string environment variable into typed Python primitives."""
    val_lower = val.strip().lower()
    if val_lower in ("true", "1", "yes", "on"):
        return True
    if val_lower in ("false", "0", "no", "off"):
        return False
    if val_lower in ("none", "null"):
        return None

    # Try integer
    try:
        return int(val)
    except ValueError:
        pass

    # Try float
    try:
        return float(val)
    except ValueError:
        pass

    # Try JSON
    if (val.startswith("{") and val.endswith("}")) or (val.startswith("[") and val.endswith("]")):
        try:
            return json.loads(val)
        except Exception:
            pass

    return val


def load_environment_overrides(prefix: str = "CIVIS_") -> Dict[str, Any]:
    """
    Extracts environment variables starting with CIVIS_ and constructs a nested dictionary.
    Supports double underscore '__' for nested keys:
    e.g. CIVIS_DETECTION__CONFIDENCE_THRESHOLD=0.7 -> {"detection": {"confidence_threshold": 0.7}}
    or single underscore fallback:
    CIVIS_DEVICE=cuda:0 -> {"device": "cuda:0"}
    """
    overrides: Dict[str, Any] = {}

    for env_key, env_val in os.environ.items():
        if not env_key.startswith(prefix):
            continue

        stripped = env_key[len(prefix):].lower()
        if not stripped:
            continue

        parsed_val = parse_env_value(env_val)

        # Check nested delimiter '__'
        if "__" in stripped:
            parts = stripped.split("__")
            curr = overrides
            for p in parts[:-1]:
                curr = curr.setdefault(p, {})
            curr[parts[-1]] = parsed_val
        else:
            # Check single underscore top-level mapping
            overrides[stripped] = parsed_val

    return overrides
