from fastapi import APIRouter
from .logo import router as logo_router
from .nearby import router as nearby_router
from .route import router as route_router
from .settings import router as settings_router

router = APIRouter(prefix="/flight", tags=["flight"])
router.include_router(logo_router)
router.include_router(nearby_router)
router.include_router(route_router)
router.include_router(settings_router)
