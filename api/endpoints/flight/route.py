import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from helpers.flight_routes import get_route
from helpers.flights import find_plane

logger = logging.getLogger(__name__)
router = APIRouter()


# Plain `def`: a route lookup may call adsb.lol, so it runs in the thread pool.
@router.get("/route")
def route(hex: str):
    """From/to airports for a plane in the last /nearby answer, by ICAO hex.

    The website calls this when a plane is tapped. Answers are cached per
    callsign for a day, so tapping the same flight again costs nothing.
    `route` is null for private planes and flights adsb.lol has no route for.
    """
    plane = find_plane(hex)
    if not plane:
        return JSONResponse({"hex": hex, "route": None, "found": False})
    return JSONResponse({"hex": plane["hex"], "route": get_route(plane), "found": True})
