import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from ._stations_store import load

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/")
async def get_all_stations():
    return JSONResponse(list(load().keys()))
