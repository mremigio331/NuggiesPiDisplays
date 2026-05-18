from fastapi import APIRouter
from fastapi.responses import JSONResponse
from .get_current import router as get_current_router
from .get_enabled import router as get_enabled_router
from .set_current import router as set_current_router
from .force_change import router as force_change_router
from .set_enabled import router as set_enabled_router
from ._stations_store import load

router = APIRouter(prefix="/stations", tags=["mta"])


@router.get("")
async def get_all_stations():
    return JSONResponse(list(load().keys()))


router.include_router(get_current_router)
router.include_router(get_enabled_router)
router.include_router(set_current_router)
router.include_router(force_change_router)
router.include_router(set_enabled_router)
