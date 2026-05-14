import logging
from enum import Enum
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from helpers.config import read_settings, write_settings
from helpers.process import start_display

logger = logging.getLogger(__name__)
router = APIRouter()


class DisplayModeEnum(str, Enum):
    stocks = "stocks"
    mta = "mta"
    clock = "clock"
    weather = "weather"


class DisplayMode(BaseModel):
    mode: DisplayModeEnum


@router.post("/display")
async def switch_display(body: DisplayMode):
    try:
        pid = start_display(body.mode.value)
        settings = read_settings()
        settings["active_display"] = body.mode.value
        write_settings(settings)
        logger.info("Switched display to %s (pid %s)", body.mode.value, pid)
        return JSONResponse({"active_display": body.mode.value, "pid": pid})
    except Exception as e:
        logger.exception("Failed to switch display to %s", body.mode.value)
        raise HTTPException(status_code=500, detail=str(e))
