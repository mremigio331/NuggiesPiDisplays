import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from helpers.config import read_settings
from ._lock import with_active_lock

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/settings")
async def get_settings():
    settings = read_settings()
    return JSONResponse(with_active_lock(settings.get("weather", {})))
