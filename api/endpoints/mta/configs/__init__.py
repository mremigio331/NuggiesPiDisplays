from fastapi import APIRouter
from .get_configs import router as get_router
from .update_config import router as update_router

router = APIRouter(prefix="/configs", tags=["mta"])
router.include_router(get_router)
router.include_router(update_router)
