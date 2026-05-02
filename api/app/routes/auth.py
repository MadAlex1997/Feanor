import jwt
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..auth import verify_token

router = APIRouter()


@router.get("/auth/verify")
async def verify(request: Request):
    """
    Traefik forwardAuth target. Returns 200 + forwarded headers on valid JWT,
    401 on missing/invalid token. Must remain on the public (no-auth) router.
    """
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        return JSONResponse(
            status_code=401,
            content={"error": "missing or malformed Authorization header"},
        )

    token = authorization[len("Bearer "):]
    try:
        claims = await verify_token(token)
    except jwt.InvalidTokenError as exc:
        return JSONResponse(status_code=401, content={"error": str(exc)})

    subject = claims.get("sub", "")
    roles = claims.get("realm_access", {}).get("roles", [])

    return JSONResponse(
        status_code=200,
        content={"ok": True},
        headers={
            "X-Feanor-Subject": subject,
            "X-Feanor-Roles": ",".join(roles),
        },
    )
