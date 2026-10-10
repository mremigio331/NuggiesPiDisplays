import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from helpers.geolocation import get_ip_geolocation

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/geolocate")
async def geolocate():
    """Suggest a location and timezone from the device's public IP.

    Read-only: this does NOT persist anything to settings. The clock and
    weather settings pages (and the first-run setup flow) call this to
    pre-fill a suggestion the user can accept.

    Returns ``{latitude, longitude, city_label, timezone}``.
    """
    loc = get_ip_geolocation()
    if not loc:
        raise HTTPException(
            status_code=503, detail="Could not determine location from IP"
        )
    return JSONResponse(loc)
