from fastapi import APIRouter
from .get_settings import router as get_settings_router
from .update_settings import router as update_settings_router
from .search import router as search_router
from .now import router as now_router
from .info import router as info_router
from .chart import (
    router as chart_router,
)  # must come after info/now (avoids /{symbol}/* collision)

router = APIRouter(prefix="/stonks", tags=["stonks"])
router.include_router(get_settings_router)
router.include_router(update_settings_router)
router.include_router(search_router)
router.include_router(now_router)
router.include_router(info_router)
router.include_router(chart_router)
