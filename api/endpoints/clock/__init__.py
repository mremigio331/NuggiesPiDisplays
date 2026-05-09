from fastapi import APIRouter
from .get_settings import router as get_settings_router
from .update_settings import router as update_settings_router
from .get_timezones import router as get_timezones_router
from .ws import router as ws_router

router = APIRouter(prefix="/clock", tags=["clock"])
router.include_router(get_settings_router)
router.include_router(update_settings_router)
router.include_router(get_timezones_router)
router.include_router(ws_router)
