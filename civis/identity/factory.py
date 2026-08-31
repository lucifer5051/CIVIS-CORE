from typing import Optional
from civis.identity.engine import IdentityEngine, MockIdentityEngine
from civis.identity.models import IdentityConfig
from civis.identity.sface_embedder import SFaceFaceEmbedder


def create_identity_engine(config: Optional[IdentityConfig] = None) -> IdentityEngine:
    """
    Factory helper to instantiate IdentityEngine based on configuration.
    Returns MockIdentityEngine if config.use_mock is True.
    """
    cfg = config or IdentityConfig()
    if getattr(cfg, "use_mock", False):
        return MockIdentityEngine(cfg)
    embedder = SFaceFaceEmbedder()
    return IdentityEngine(cfg, embedder=embedder)
