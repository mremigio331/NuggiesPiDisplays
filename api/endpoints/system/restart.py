import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from helpers.system import SystemManager

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/restart")
async def restart():
    logger.info("Restart requested")
    SystemManager().reboot()
    return JSONResponse({"message": "rebooting"})
