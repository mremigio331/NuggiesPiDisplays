import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from helpers.config import read_settings, write_settings
from .data import invalidate_cache
from ._lock import lock_expiry, with_active_lock

logger = logging.getLogger(__name__)
router = APIRouter()


class WeatherSettings(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    city_label: Optional[str] = None
    use_ip_location: Optional[bool] = None
    units: Optional[str] = None
    cycle_duration: Optional[int] = None
    # One-shot "show now": jump the display to this screen, then resume rotation.
    # The display clears it once consumed. Empty string clears it.
    force_view: Optional[str] = None
    # Pin the display to one screen for 1 hour (survives restarts).
    # Empty string unlocks and resumes the normal rotation.
    locked_view: Optional[str] = None


VALID_VIEWS = ("current", "hourly", "forecast", "sky")
# Only these change what Open-Meteo returns, so only these may refetch.
_DATA_KEYS = {"latitude", "longitude", "city_label", "use_ip_location", "units"}


@router.put("/settings")
async def update_settings(body: WeatherSettings):
    updates = body.model_dump(exclude_none=True)

    if "units" in updates and updates["units"] not in ("fahrenheit", "celsius"):
        raise HTTPException(
            status_code=422, detail="units must be 'fahrenheit' or 'celsius'"
        )

    if "cycle_duration" in updates and not (10 <= updates["cycle_duration"] <= 3600):
        raise HTTPException(
            status_code=422, detail="cycle_duration must be between 10 and 3600 seconds"
        )

    if updates.get("force_view") and updates["force_view"] not in VALID_VIEWS:
        raise HTTPException(
            status_code=422,
            detail=f"force_view must be one of {list(VALID_VIEWS)} or empty",
        )

    if updates.get("locked_view") and updates["locked_view"] not in VALID_VIEWS:
        raise HTTPException(
            status_code=422,
            detail=f"locked_view must be one of {list(VALID_VIEWS)} or empty",
        )

    settings = read_settings()
    weather = settings.get("weather", {})
    weather.update(updates)

    # A lock lasts LOCK_TTL (1 hour), then the rotation resumes by itself.
    if "locked_view" in updates:
        if updates["locked_view"]:
            weather["locked_until"] = lock_expiry()
        else:
            weather.pop("locked_until", None)

    # If the user set a manual lat/lon, switch off IP-based location
    if "latitude" in updates or "longitude" in updates:
        weather.setdefault("use_ip_location", False)

    settings["weather"] = weather
    write_settings(settings)

    # Force a fresh weather fetch on the next /weather/data call, but only when
    # the change affects the data (a "show now" must not cost an API call).
    if _DATA_KEYS & updates.keys():
        invalidate_cache()

    logger.info(f"Weather settings updated: {list(updates.keys())}")
    return JSONResponse(with_active_lock(weather))
