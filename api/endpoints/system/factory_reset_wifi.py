import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from helpers.system import SystemManager

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/factory-reset-wifi")
async def factory_reset_wifi():
    """Reset settings, mark WiFi for wipe on next boot, then reboot."""
    try:
        SystemManager().factory_reset_wifi()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return JSONResponse(
        {
            "message": "Factory reset complete. Pi is rebooting — connect to NuggiesSetup WiFi to reconfigure."
        }
    )
