import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from helpers.config import read_settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/settings")
async def get_settings():
    settings = read_settings()
    return JSONResponse(settings.get("stocks", {}))
