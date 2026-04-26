import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from helpers.config import read_settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/current")
async def get_current_station():
    settings = read_settings()
    station = settings.get("mta", {}).get("station")
    return JSONResponse({"station": station})
