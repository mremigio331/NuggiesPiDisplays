import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from helpers.config import read_settings, write_settings
from ._stations_store import load

logger = logging.getLogger(__name__)
router = APIRouter()


class SetStationBody(BaseModel):
    station: str


@router.put("/current")
async def set_current_station(body: SetStationBody):
    stations = load()
    if body.station not in stations:
        raise HTTPException(
            status_code=404, detail=f"Station not found: {body.station}"
        )
    settings = read_settings()
    settings["mta"]["station"] = body.station
    write_settings(settings)
    logger.info("Current station set to %s", body.station)
    return JSONResponse({"station": body.station})
