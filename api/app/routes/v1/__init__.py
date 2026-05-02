from fastapi import APIRouter

from .datasets import router as datasets_router
from .workflows import router as workflows_router

router = APIRouter(prefix="/v1")
router.include_router(datasets_router)
router.include_router(workflows_router)
