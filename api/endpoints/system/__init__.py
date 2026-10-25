from fastapi import APIRouter
from .status import router as status_router
from .display import router as display_router
from .start import router as start_router
from .stop import router as stop_router
from .restart import router as restart_router
from .restart_api import router as restart_api_router
from .restart_display import router as restart_display_router
from .restart_website import router as restart_website_router
from .restart_wifi_service import router as restart_wifi_service_router
from .update import router as update_router
from .update_app import router as update_app_router
from .update_log import router as update_log_router
from .display_overlay import router as display_overlay_router
from .user_guide import router as user_guide_router
from .factory_reset import router as factory_reset_router
from .geolocate import router as geolocate_router
from .factory_reset_wifi import router as factory_reset_wifi_router
from .force_wifi_portal import router as force_wifi_portal_router
from .dev_mode import router as dev_mode_router
from .forget_wifi import router as forget_wifi_router
from .get_log_level import router as get_log_level_router
from .update_log_level import router as update_log_level_router
from .check_update import router as check_update_router
from .update_status import router as update_status_router
from .update_stage import router as update_stage_router
from .logs import router as logs_router

router = APIRouter(prefix="/system", tags=["system"])
router.include_router(status_router)
router.include_router(display_router)
router.include_router(start_router)
router.include_router(stop_router)
router.include_router(restart_router)
router.include_router(restart_api_router)
router.include_router(restart_display_router)
router.include_router(restart_website_router)
router.include_router(restart_wifi_service_router)
router.include_router(update_router)
router.include_router(update_app_router)
router.include_router(update_log_router)
router.include_router(display_overlay_router)
router.include_router(user_guide_router)
router.include_router(check_update_router)
router.include_router(update_status_router)
router.include_router(update_stage_router)
router.include_router(factory_reset_router)
router.include_router(geolocate_router)
router.include_router(factory_reset_wifi_router)
router.include_router(force_wifi_portal_router)
router.include_router(dev_mode_router)
router.include_router(forget_wifi_router)
router.include_router(get_log_level_router)
router.include_router(update_log_level_router)
router.include_router(logs_router)
