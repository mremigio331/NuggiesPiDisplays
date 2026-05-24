import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from helpers.system import SystemManager

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/factory-reset")
async def factory_reset():
    """Reset all settings to factory defaults. Does not affect WiFi or reboot."""
    try:
        SystemManager().factory_reset()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return JSONResponse({"message": "Settings restored to factory defaults."})
