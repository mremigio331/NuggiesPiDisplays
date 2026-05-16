import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from helpers.config import reset_settings
from helpers.process import stop_display

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/factory-reset")
async def factory_reset():
    """Reset all settings to factory defaults. Does not affect WiFi or reboot."""
    logger.info("Factory reset: restoring default settings")

    try:
        stop_display()
        logger.info("Display stopped")
    except Exception as e:
        logger.warning(f"Could not stop display (continuing): {e}")

    try:
        reset_settings()
    except Exception as e:
        logger.error(f"Failed to reset settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reset settings: {e}")

    logger.info("Factory reset complete")
    return JSONResponse({"message": "Settings restored to factory defaults."})
