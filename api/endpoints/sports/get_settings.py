from fastapi import APIRouter
from fastapi.responses import JSONResponse
from helpers.config import read_settings

router = APIRouter()


@router.get("/settings")
async def get_sports_settings():
    settings = read_settings()
    return JSONResponse(settings.get("sports", {}))
