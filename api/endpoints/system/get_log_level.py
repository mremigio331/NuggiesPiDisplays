import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from helpers.config import read_settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/log-level")
async def get_log_level():
    level = read_settings().get("log_level", "INFO")
    logger.debug(f"Log level queried: {level}")
    return JSONResponse({"log_level": level})
