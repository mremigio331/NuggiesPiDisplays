import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from helpers.config import read_settings
from helpers.mta import next_trains_for_station
from endpoints.mta.stations._stations_store import load as load_stations

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/next_four")
async def get_next_four():
    settings = read_settings()
    station_name = settings.get("mta", {}).get("station")

    stations = load_stations()
    station_info = stations.get(station_name)
    if not station_info:
        raise HTTPException(
            status_code=404, detail=f"Station not found: {station_name}"
        )

    logger.info("Fetching next 4 trains for %s", station_name)
    trains = next_trains_for_station(station_info, limit=4)

    return JSONResponse(
        {
            "station": station_name,
            "stop_name": station_info.get("stop_name"),
            "trains": trains,
            "timestamp": datetime.now().isoformat(),
        }
    )
