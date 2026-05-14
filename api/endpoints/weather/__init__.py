from fastapi import APIRouter
from .data import router as data_router
from .geocode import router as geocode_router
from .get_settings import router as get_settings_router
from .update_settings import router as update_settings_router

router = APIRouter(prefix="/weather", tags=["weather"])
router.include_router(data_router)
router.include_router(geocode_router)
router.include_router(get_settings_router)
router.include_router(update_settings_router)
