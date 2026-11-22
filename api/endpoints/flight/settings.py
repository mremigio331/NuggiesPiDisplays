import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from helpers.config import (
    FLIGHT_LABEL_MAX,
    FLIGHT_RADIUS_MAX,
    FLIGHT_RADIUS_MIN,
    FLIGHT_UNITS,
    read_flight,
    write_flight,
)
from helpers.flights import invalidate

logger = logging.getLogger(__name__)
router = APIRouter()


class FlightSettings(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_label: Optional[str] = None
    radius: Optional[int] = None
    units: Optional[str] = None
    # True removes the saved spot (the board goes back to "Update settings").
    clear_location: Optional[bool] = None
    # True shows only planes flying for an airline.
    airlines_only: Optional[bool] = None


@router.get("/settings")
def get_settings():
    return JSONResponse(read_flight())


@router.put("/settings")
def update_settings(body: FlightSettings):
    updates = body.model_dump(exclude_none=True)
    flight = read_flight()

    has_lat, has_lon = "latitude" in updates, "longitude" in updates
    if has_lat != has_lon:
        raise HTTPException(
            status_code=422, detail="latitude and longitude must be set together"
        )
    if has_lat:
        if not -90 <= updates["latitude"] <= 90:
            raise HTTPException(
                status_code=422, detail="latitude must be between -90 and 90"
            )
        if not -180 <= updates["longitude"] <= 180:
            raise HTTPException(
                status_code=422, detail="longitude must be between -180 and 180"
            )
        flight["latitude"] = updates["latitude"]
        flight["longitude"] = updates["longitude"]
        # A new spot replaces the old label unless one comes with it.
        flight["location_label"] = updates.get("location_label", "")[:FLIGHT_LABEL_MAX]
    elif "location_label" in updates:
        flight["location_label"] = updates["location_label"][:FLIGHT_LABEL_MAX]

    if updates.get("clear_location"):
        flight.update(latitude=None, longitude=None, location_label="")

    if "airlines_only" in updates:
        flight["airlines_only"] = updates["airlines_only"]

    if "units" in updates:
        if updates["units"] not in FLIGHT_UNITS:
            raise HTTPException(
                status_code=422, detail=f"units must be one of {list(FLIGHT_UNITS)}"
            )
        flight["units"] = updates["units"]

    if "radius" in updates:
        if not FLIGHT_RADIUS_MIN <= updates["radius"] <= FLIGHT_RADIUS_MAX:
            raise HTTPException(
                status_code=422,
                detail=f"radius must be between {FLIGHT_RADIUS_MIN} and {FLIGHT_RADIUS_MAX}",
            )
        flight["radius"] = updates["radius"]

    saved = write_flight(flight)
    invalidate()  # the next /nearby fetches for the new spot right away
    logger.info(f"Flight settings updated: {list(updates.keys())}")
    return JSONResponse(saved)
