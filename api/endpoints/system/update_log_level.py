import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from helpers.config import read_settings, write_settings
from helpers.logger import set_log_level

logger = logging.getLogger(__name__)
router = APIRouter()

_VALID_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR"}


@router.put("/log-level")
async def put_log_level(body: dict):
    level = str(body.get("log_level", "INFO")).upper()
    if level not in _VALID_LEVELS:
        return JSONResponse(
            {"error": f"log_level must be one of {_VALID_LEVELS}"}, status_code=400
        )
    settings = read_settings()
    settings["log_level"] = level
    write_settings(settings)
    set_log_level(level)
    logger.info(f"Log level changed to {level}")
    return JSONResponse({"log_level": level})
