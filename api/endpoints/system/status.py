import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from helpers.config import active_cycle, read_settings
from helpers.process import is_running

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/status")
async def get_status():
    settings = read_settings()
    cycle = active_cycle()
    return JSONResponse(
        {
            "active_display": settings.get("active_display"),
            "running": is_running(),
            "cycle_name": cycle["name"] if cycle else None,
        }
    )
