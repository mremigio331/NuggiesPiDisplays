import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from helpers.config import read_settings, write_settings
from .data import invalidate_cache

logger = logging.getLogger(__name__)
router = APIRouter()


class WeatherSettings(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    city_label: Optional[str] = None
    use_ip_location: Optional[bool] = None
    units: Optional[str] = None
    cycle_duration: Optional[int] = None


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

    settings = read_settings()
    weather = settings.get("weather", {})
    weather.update(updates)

    # If the user set a manual lat/lon, switch off IP-based location
    if "latitude" in updates or "longitude" in updates:
        weather.setdefault("use_ip_location", False)

    settings["weather"] = weather
    write_settings(settings)

    # Force a fresh weather fetch on the next /weather/data call
    invalidate_cache()

    logger.info(f"Weather settings updated: {list(updates.keys())}")
    return JSONResponse(weather)
