import logging
from enum import Enum
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from constants import DISPLAY_MODES
from helpers.config import read_settings, write_settings
from helpers.process import start_display

logger = logging.getLogger(__name__)
router = APIRouter()

DisplayModeEnum = Enum("DisplayModeEnum", {m: m for m in DISPLAY_MODES}, type=str)


class DisplayMode(BaseModel):
    mode: DisplayModeEnum


@router.post("/display")
async def switch_display(body: DisplayMode):
    try:
        pid = start_display(body.mode.value)
        settings = read_settings()
        settings["active_display"] = body.mode.value
        write_settings(settings)
        logger.info(f"Switched display to {body.mode.value} (pid {pid})")
        return JSONResponse({"active_display": body.mode.value, "pid": pid})
    except Exception as e:
        logger.exception(f"Failed to switch display to {body.mode.value}")
        raise HTTPException(status_code=500, detail=str(e))
