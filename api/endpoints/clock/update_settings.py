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
    timezone: Optional[str] = None
    timezone_auto: Optional[bool] = None
    color: Optional[List[int]] = None
    use_24h: Optional[bool] = None


@router.put("/settings")
async def update_settings(body: ClockSettings):
    updates = body.model_dump(exclude_none=True)

    if "timezone" in updates:
        try:
            from zoneinfo import ZoneInfo

            ZoneInfo(updates["timezone"])
        except Exception:
            raise HTTPException(
                status_code=422, detail=f"Invalid timezone: {updates['timezone']}"
            )

    if "color" in updates:
        c = updates["color"]
        if len(c) != 3 or not all(isinstance(v, int) and 0 <= v <= 255 for v in c):
            raise HTTPException(
                status_code=422, detail="color must be [r, g, b] with values 0-255"
            )

    # A manual timezone pick turns auto-detect off, unless the caller is
    # explicitly setting timezone_auto in the same request.
    if "timezone" in updates and "timezone_auto" not in updates:
        updates["timezone_auto"] = False

    settings = read_settings()
    clock = settings.get("clock", {})
    clock.update(updates)
    settings["clock"] = clock
    write_settings(settings)
    logger.info(f"Clock settings updated: {list(updates.keys())}")

    # If the user just switched auto-detect on (without also setting a manual
    # timezone), resolve the timezone from IP right away so the toggle takes
    # effect immediately instead of waiting for the next boot.
    if updates.get("timezone_auto") is True and "timezone" not in updates:
        from .auto_timezone import auto_detect_timezone

        await auto_detect_timezone()
        clock = read_settings().get("clock", {})
        return JSONResponse(clock)

    await manager.broadcast(clock)
    return JSONResponse(clock)
