from fastapi import APIRouter
from fastapi.responses import JSONResponse
from helpers.update_check import get_status

router = APIRouter()


@router.get("/update-status")
async def update_status():
    """Return the cached update check result — no network call."""
    return JSONResponse(get_status().to_dict())
