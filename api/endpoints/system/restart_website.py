import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from helpers.system import SystemManager

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/restart-website")
async def restart_website():
    """Restart the website (prod: rebuild bundle; dev: restart webpack dev server)."""
    logger.info("Website restart requested")
    action = SystemManager().restart_website()
    return JSONResponse({"message": "website restart triggered", "action": action})
