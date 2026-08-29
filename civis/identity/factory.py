from civis.identity.engine import IdentityEngine, MockIdentityEngine
from civis.identity.models import IdentityConfig


def create_identity_engine(config: IdentityConfig) -> IdentityEngine:
    """
    Factory helper to instantiate IdentityEngine based on configuration.
    Returns MockIdentityEngine if config.use_mock is True.
    """
    if config.use_mock:
        return MockIdentityEngine(config)
    return IdentityEngine(config)
