from fastapi import APIRouter
from .trains import router as trains_router
from .stations import router as stations_router
from .configs import router as configs_router

router = APIRouter(prefix="/mta")
router.include_router(trains_router)
router.include_router(stations_router)
router.include_router(configs_router)
