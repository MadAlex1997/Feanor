import asyncio
import os
from functools import lru_cache

import jwt
from jwt import PyJWKClient


@lru_cache(maxsize=1)
def _jwks_client() -> PyJWKClient:
    base = os.environ.get("KEYCLOAK_URL", "http://keycloak:8080")
    realm = os.environ.get("KEYCLOAK_REALM", "feanor")
    url = f"{base}/realms/{realm}/protocol/openid-connect/certs"
    return PyJWKClient(url, cache_keys=True)


def _decode_token_sync(token: str) -> dict:
    client = _jwks_client()
    signing_key = client.get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        # Keycloak tokens may omit aud; role enforcement is the API's job.
        options={"verify_aud": False},
    )


async def verify_token(token: str) -> dict:
    """Verify a JWT bearer token. Returns decoded claims. Raises jwt.InvalidTokenError on failure."""
    return await asyncio.to_thread(_decode_token_sync, token)
