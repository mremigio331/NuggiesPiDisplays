import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from ._stations_store import load

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/enabled")
async def get_enabled_stations():
    stations = load()
    return JSONResponse(
        [name for name, info in stations.items() if info.get("enabled", True)]
    )
