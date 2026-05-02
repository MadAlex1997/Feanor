from fastapi import APIRouter

from .datasets import router as datasets_router
from .executions import router as executions_router
from .templates import router as templates_router
from .workflows import router as workflows_router

router = APIRouter(prefix="/v1")
router.include_router(datasets_router)
router.include_router(workflows_router)
router.include_router(executions_router)
router.include_router(templates_router)
