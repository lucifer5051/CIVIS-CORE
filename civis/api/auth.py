import hmac
import secrets
from typing import Optional
from fastapi import Header, HTTPException, Security, status
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_auth_dependency(auth_enabled: bool, expected_key: str):
    """
    Returns a dependency callable that performs constant-time API key validation.
    """
    async def verify_api_key(x_api_key: Optional[str] = Security(api_key_header)) -> Optional[str]:
        if not auth_enabled:
            return None

        if not x_api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing required API key header 'X-API-Key'",
            )

        # Constant-time comparison to prevent timing attacks
        if not secrets.compare_digest(x_api_key.encode("utf-8"), expected_key.encode("utf-8")):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key provided",
            )

        return x_api_key

    return verify_api_key
