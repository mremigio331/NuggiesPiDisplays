import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from helpers.config import read_settings
from helpers.process import start_display, is_running

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/display/start")
async def start_display_endpoint():
    if is_running():
        return JSONResponse({"started": False, "message": "Display is already running"})
    settings = read_settings()
    mode = settings.get("active_display", "mta")
    try:
        pid = start_display(mode)
        logger.info(f"Display started via API: mode={mode} pid={pid}")
        return JSONResponse({"started": True, "active_display": mode, "pid": pid})
    except Exception as e:
        logger.exception(f"Failed to start display (mode={mode})")
        raise HTTPException(status_code=500, detail=str(e))
