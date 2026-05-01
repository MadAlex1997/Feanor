import os
import asyncpg
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..schemas import APIResponse, Meta

router = APIRouter()


def _meta(request: Request) -> Meta:
    return Meta(request_id=request.state.request_id)


@router.get("/health", response_model=APIResponse[dict])
async def health(request: Request):
    return APIResponse(data={"status": "ok"}, meta=_meta(request))


@router.get("/ready", response_model=APIResponse[dict])
async def ready(request: Request):
    meta = _meta(request)
    try:
        conn = await asyncpg.connect(os.environ["DATABASE_URL"])
        await conn.execute("SELECT 1")
        await conn.close()
        return APIResponse(data={"status": "ok"}, meta=meta)
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content=APIResponse(data=None, error=str(exc), meta=meta).model_dump(),
        )
