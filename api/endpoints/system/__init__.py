from fastapi import APIRouter
from .status import router as status_router
from .display import router as display_router
from .start import router as start_router
from .stop import router as stop_router
from .restart import router as restart_router
from .update import router as update_router
from .update_app import router as update_app_router
from .factory_reset import router as factory_reset_router
from .factory_reset_wifi import router as factory_reset_wifi_router
from .dev_mode import router as dev_mode_router
from .forget_wifi import router as forget_wifi_router
from .get_log_level import router as get_log_level_router
from .update_log_level import router as update_log_level_router

router = APIRouter(prefix="/system", tags=["system"])
router.include_router(status_router)
router.include_router(display_router)
router.include_router(start_router)
router.include_router(stop_router)
router.include_router(restart_router)
router.include_router(update_router)
router.include_router(update_app_router)
router.include_router(factory_reset_router)
router.include_router(factory_reset_wifi_router)
router.include_router(dev_mode_router)
router.include_router(forget_wifi_router)
router.include_router(get_log_level_router)
router.include_router(update_log_level_router)
