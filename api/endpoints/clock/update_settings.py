import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from helpers.config import read_settings, write_settings
from .ws_manager import manager

logger = logging.getLogger(__name__)
router = APIRouter()


class ClockSettings(BaseModel):
    # Ordered list of IANA timezones to show. The display goes down this list.
    timezones: Optional[List[str]] = None
    # "focus" shows one timezone at a time (big time + date + tz abbr).
    # "multi" shows up to three at a time, divided into thirds.
    display_mode: Optional[str] = None
    # Seconds each timezone (focus) or page of three (multi) stays on screen.
    cycle_seconds: Optional[int] = None
    color: Optional[List[int]] = None
    # "solid" uses `color`; "rainbow" (aka Caitlin Mode) animates a horizontal
    # rainbow that slides to the right.
    color_mode: Optional[str] = None
    use_24h: Optional[bool] = None


def _validate_timezones(zones) -> List[str]:
    from zoneinfo import ZoneInfo

    if not isinstance(zones, list) or len(zones) == 0:
        raise HTTPException(
            status_code=422, detail="timezones must be a non-empty list"
        )
    # De-duplicate while preserving order and validate each IANA name.
    seen = set()
    cleaned = []
    for z in zones:
        if not isinstance(z, str) or z in seen:
            continue
        try:
            ZoneInfo(z)
        except Exception:
            raise HTTPException(status_code=422, detail=f"Invalid timezone: {z}")
        seen.add(z)
        cleaned.append(z)
    if not cleaned:
        raise HTTPException(
            status_code=422, detail="timezones must contain at least one valid zone"
        )
    return cleaned


@router.put("/settings")
async def update_settings(body: ClockSettings):
    updates = body.model_dump(exclude_none=True)

    if "timezones" in updates:
        updates["timezones"] = _validate_timezones(updates["timezones"])

    if "display_mode" in updates and updates["display_mode"] not in ("focus", "multi"):
        raise HTTPException(
            status_code=422, detail="display_mode must be 'focus' or 'multi'"
        )

    if "cycle_seconds" in updates:
        cs = updates["cycle_seconds"]
        if not isinstance(cs, int) or not (1 <= cs <= 3600):
            raise HTTPException(
                status_code=422,
                detail="cycle_seconds must be an int between 1 and 3600",
            )

    if "color_mode" in updates and updates["color_mode"] not in ("solid", "rainbow"):
        raise HTTPException(
            status_code=422, detail="color_mode must be 'solid' or 'rainbow'"
        )

    if "color" in updates:
        c = updates["color"]
        if len(c) != 3 or not all(isinstance(v, int) and 0 <= v <= 255 for v in c):
            raise HTTPException(
                status_code=422, detail="color must be [r, g, b] with values 0-255"
            )

    settings = read_settings()
    clock = settings.get("clock", {})
    clock.update(updates)
    settings["clock"] = clock
    write_settings(settings)
    logger.info(f"Clock settings updated: {list(updates.keys())}")

    await manager.broadcast(clock)
    return JSONResponse(clock)
