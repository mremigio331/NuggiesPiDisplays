from fastapi import APIRouter
from .nba import router as nba_router
from .mlb import router as mlb_router
from .nhl import router as nhl_router
from .football import router as football_router
from .soccer import router as soccer_router
from .locks import router as locks_router
from .favorites import router as favorites_router
from .teams import router as teams_router
from .now import router as now_router
from .get_settings import router as get_settings_router
from .update_settings import router as update_settings_router

router = APIRouter(prefix="/sports", tags=["sports"])
router.include_router(nba_router)
router.include_router(mlb_router)
router.include_router(nhl_router)
router.include_router(football_router)
router.include_router(soccer_router)
router.include_router(now_router)
router.include_router(locks_router)
router.include_router(favorites_router)
router.include_router(teams_router)
router.include_router(get_settings_router)
router.include_router(update_settings_router)
