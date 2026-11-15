from fastapi import APIRouter
from .timers import router as timers_router

router = APIRouter(tags=["timers"])
# The prefix goes on include_router: the routes use "" for /timers itself, and
# FastAPI refuses an empty path unless the include supplies the prefix.
router.include_router(timers_router, prefix="/timers")
