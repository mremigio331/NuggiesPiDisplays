import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from helpers.system import SystemManager

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/restart-display")
async def restart_display():
    """Stop and restart the active display process."""
    logger.info("Display restart requested")
    try:
        mode = SystemManager().restart_display()
        return JSONResponse({"message": "display restarted", "active_display": mode})
    except Exception as e:
        logger.exception("Failed to restart display")
        raise HTTPException(status_code=500, detail=str(e))
