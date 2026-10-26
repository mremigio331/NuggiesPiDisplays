import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from constants import DISPLAY_MODES
from helpers.config import (
    read_schedule,
    write_schedule,
    schedule_mode_options,
    BRIGHTNESS_MIN,
    BRIGHTNESS_MAX,
    BRIGHTNESS_PRESETS,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class ScheduleRule(BaseModel):
    time: str  # "HH:MM" 24-hour, device-local
    # action: "mode" | "power" | "brightness". Defaults to "mode" so legacy
    # rules (just time+mode) keep working. All fields validated for real in
    # normalize_schedule; an invalid rule is dropped there rather than 500ing.
    action: Optional[str] = None
    mode: Optional[str] = None
    option: Optional[str] = None
    power: Optional[str] = None  # "on" | "off"
    brightness: Optional[int] = None  # 1-100


class Schedule(BaseModel):
    enabled: bool = False
    rules: list[ScheduleRule] = []


def _payload(schedule: dict) -> dict:
    """Schedule plus the UI's dropdown vocabularies, all backend-owned."""
    return {
        **schedule,
        "modes": DISPLAY_MODES,
        "mode_options": schedule_mode_options(),
        # What the UI needs to build the non-mode action controls.
        "actions": ["mode", "power", "brightness"],
        "power_options": ["on", "off"],
        "brightness": {
            "min": BRIGHTNESS_MIN,
            "max": BRIGHTNESS_MAX,
            "presets": [{"name": n, "value": v} for n, v in BRIGHTNESS_PRESETS.items()],
        },
    }


@router.get("/schedule")
async def get_schedule():
    return JSONResponse(_payload(read_schedule()))


@router.put("/schedule")
async def update_schedule(body: Schedule):
    try:
        saved = write_schedule(body.model_dump(exclude_none=True))
        logger.info(
            "Schedule updated: enabled=%s rules=%s",
            saved["enabled"],
            saved["rules"],
        )
        return JSONResponse(_payload(saved))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Failed to update schedule")
        raise HTTPException(status_code=500, detail=str(e))
