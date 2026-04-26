import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from helpers.process import stop_display, is_running

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/display/stop")
async def stop_display_endpoint():
    if not is_running():
        return JSONResponse(
            {"stopped": False, "message": "No display process was running"}
        )
    stop_display()
    logger.info("Display stopped via API")
    return JSONResponse({"stopped": True})
