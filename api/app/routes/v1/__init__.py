from fastapi import APIRouter

from .datasets import router as datasets_router

router = APIRouter(prefix="/v1")
router.include_router(datasets_router)
