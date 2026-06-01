import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from helpers.system import SystemManager

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/restart-wifi-service")
async def restart_wifi_service():
    logger.info("Restarting wifi service")
    SystemManager().wifi_service_restart()
    return JSONResponse({"message": "restarting"})
