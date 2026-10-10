import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from helpers.system import SystemManager

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/restart-api")
async def restart_api():
    """Restart the API process (prod: systemd unit; dev: no-op, uvicorn --reload)."""
    logger.info("API restart requested")
    SystemManager().restart_api()
    return JSONResponse({"message": "restarting api"})
