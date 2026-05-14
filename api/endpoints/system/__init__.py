from fastapi import APIRouter
from .status import router as status_router
from .display import router as display_router
from .start import router as start_router
from .stop import router as stop_router
from .restart import router as restart_router
from .update import router as update_router
from .factory import router as factory_router
from .dev import router as dev_router

router = APIRouter(prefix="/system", tags=["system"])
router.include_router(status_router)
router.include_router(display_router)
router.include_router(start_router)
router.include_router(stop_router)
router.include_router(restart_router)
router.include_router(update_router)
router.include_router(factory_router)
router.include_router(dev_router)
