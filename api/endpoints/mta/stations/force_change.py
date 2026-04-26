import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from helpers.config import read_settings, write_settings
from ._stations_store import load

logger = logging.getLogger(__name__)
router = APIRouter()


class ForceChangeBody(BaseModel):
    station: str = ""


@router.put("/force_change")
async def force_change_station(body: ForceChangeBody):
    if body.station:
        stations = load()
        if body.station not in stations:
            raise HTTPException(
                status_code=404, detail=f"Station not found: {body.station}"
            )
    settings = read_settings()
    settings["mta"]["force_change_station"] = body.station
    write_settings(settings)
    logger.info("Force change station set to '%s'", body.station)
    return JSONResponse({"force_change_station": body.station})
