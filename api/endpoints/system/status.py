import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from helpers.config import read_settings
from helpers.process import is_running

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/status")
async def get_status():
    settings = read_settings()
    return JSONResponse(
        {"active_display": settings.get("active_display"), "running": is_running()}
    )
