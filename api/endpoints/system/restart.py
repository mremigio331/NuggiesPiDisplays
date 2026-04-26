import logging
import subprocess
from fastapi import APIRouter
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/restart")
async def restart():
    logger.info("Rebooting Pi")
    subprocess.run(["sudo", "reboot"])
    return JSONResponse({"message": "rebooting"})
