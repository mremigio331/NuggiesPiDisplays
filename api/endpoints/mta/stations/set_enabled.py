import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from ._stations_store import load, save

logger = logging.getLogger(__name__)
router = APIRouter()


class EnabledBody(BaseModel):
    enabled: bool


@router.put("/{station_id}/enabled")
async def set_station_enabled(station_id: str, body: EnabledBody):
    stations = load()
    if station_id not in stations:
        raise HTTPException(status_code=404, detail=f"Station not found: {station_id}")
    stations[station_id]["enabled"] = body.enabled
    save(stations)
    logger.info(f"Station {station_id} enabled={body.enabled}")
    return JSONResponse({"station": station_id, "enabled": body.enabled})
